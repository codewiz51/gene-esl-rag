#!/usr/bin/env python3
"""
ollama_client.py

The only module that talks to Ollama.

preflight(runtime)  - fast startup check: is Ollama reachable, and is the
                      model installed? Run before any generation so a dead
                      Studio fails in seconds, not 40 minutes into a run.
generate(...)       - one /api/generate call, streamed. Streaming lets the
                      timeout mean "no data for N seconds" instead of "the
                      whole answer took too long", and gives a progress
                      line while a long pass runs. Retries the failures
                      that can succeed on a second try; raises a typed
                      error (see errors.py) for everything else.
"""

import json
import logging
import time
from dataclasses import dataclass

try:
    import requests
except ImportError:  # pragma: no cover - environment problem, reported plainly
    raise SystemExit("ERROR: the 'requests' package is not installed for this python3. "
                     "Install it with:  python3 -m pip install requests")

import config
from errors import (OllamaBadResponse, OllamaModelMissing, OllamaTimeout,
                    OllamaUnavailable)

log = logging.getLogger("esl")


@dataclass
class GenerateResult:
    text: str
    thinking: str
    done_reason: str
    prompt_tokens: object
    response_tokens: object
    seconds: float
    first_data_seconds: float
    max_gap_seconds: float
    attempts: int
    raw_final: dict


def _unreachable_hint(runtime):
    if runtime.mode == "client":
        return ("Check that the Studio is awake and on the network, that Ollama is running there, "
                "that it listens on the network (OLLAMA_HOST=0.0.0.0), and that the IP is right "
                f"(--studio-ip, currently {runtime.base_url}).")
    return "Check that Ollama is running on this machine (open the Ollama app, or run 'ollama serve')."


def _model_names(tags_json):
    names = set()
    for m in tags_json.get("models", []) or []:
        for key in ("name", "model"):
            if m.get(key):
                names.add(m[key])
    return names


def _has_model(names, model):
    if model in names:
        return True
    if ":" not in model and f"{model}:latest" in names:
        return True
    return False


def preflight(runtime):
    """Raise OllamaUnavailable / OllamaModelMissing, or return the model list."""
    url = f"{runtime.base_url}/api/tags"
    log.debug(f"Preflight GET {url}")
    try:
        resp = requests.get(url, timeout=(runtime.connect_timeout, config.PREFLIGHT_TIMEOUT))
        resp.raise_for_status()
        tags = resp.json()
    except requests.exceptions.RequestException as e:
        raise OllamaUnavailable(f"Cannot reach Ollama at {runtime.base_url} ({e.__class__.__name__}). "
                                + _unreachable_hint(runtime)) from e
    except ValueError as e:
        raise OllamaUnavailable(f"{url} did not return JSON - is something other than Ollama on "
                                f"port {config.OLLAMA_PORT}?") from e

    names = _model_names(tags)
    if not _has_model(names, runtime.model):
        similar = sorted(n for n in names if runtime.model.split(":")[0].split("-")[-1] in n)
        hint = f" Similar installed models: {', '.join(similar)}." if similar else ""
        raise OllamaModelMissing(f"Model '{runtime.model}' is not installed on {runtime.base_url}.{hint} "
                                 f"Check with 'ollama list' on the Studio.")
    log.info(f"Ollama OK at {runtime.base_url}; model '{runtime.model}' is installed.")
    return names


def _is_read_timeout(exc):
    """requests reports a read timeout during streaming as a ConnectionError
    wrapping urllib3's ReadTimeoutError; find it anywhere in the chain."""
    seen = set()
    stack = [exc]
    while stack:
        e = stack.pop()
        if e is None or id(e) in seen:
            continue
        seen.add(id(e))
        if isinstance(e, requests.exceptions.Timeout):
            return True
        if e.__class__.__name__ in ("ReadTimeoutError", "ReadTimeout", "TimeoutError", "timeout"):
            return True
        stack.extend(a for a in getattr(e, "args", ()) if isinstance(a, BaseException))
        stack.append(e.__cause__)
        stack.append(e.__context__)
    return False


def _error_text(resp):
    try:
        return resp.json().get("error", "") or resp.text[:300]
    except ValueError:
        return resp.text[:300]


def _one_attempt(runtime, prompt, label):
    url = f"{runtime.base_url}/api/generate"
    data = {
        "model": runtime.model,
        "prompt": prompt,
        "stream": True,
        "options": runtime.options,
    }
    start = time.monotonic()
    first_data = None
    last_beat = start
    last_chunk = None
    max_gap = 0.0
    response_parts, thinking_parts = [], []
    final = None

    try:
        resp = requests.post(url, json=data, stream=True,
                             timeout=(runtime.connect_timeout, runtime.inactivity_timeout))
    except requests.exceptions.ConnectTimeout as e:
        raise OllamaUnavailable(f"Timed out connecting to {runtime.base_url}. " + _unreachable_hint(runtime)) from e
    except requests.exceptions.RequestException as e:
        if _is_read_timeout(e):
            raise OllamaTimeout(f"No reply from Ollama within {runtime.inactivity_timeout:g}s "
                                f"(label={label}).") from e
        raise OllamaUnavailable(f"Cannot reach Ollama at {runtime.base_url} ({e.__class__.__name__}). "
                                + _unreachable_hint(runtime)) from e

    with resp:
        if resp.status_code == 404:
            msg = _error_text(resp)
            if "model" in msg.lower():
                raise OllamaModelMissing(f"Ollama says: {msg}")
            raise OllamaBadResponse(f"HTTP 404 from {url}: {msg}", retryable=False)
        if 400 <= resp.status_code < 500:
            raise OllamaBadResponse(f"HTTP {resp.status_code} from Ollama: {_error_text(resp)}", retryable=False)
        if resp.status_code >= 500:
            raise OllamaBadResponse(f"HTTP {resp.status_code} from Ollama: {_error_text(resp)}", retryable=True)

        try:
            for line in resp.iter_lines():
                if not line:
                    continue
                now = time.monotonic()
                if last_chunk is not None:
                    max_gap = max(max_gap, now - last_chunk)
                last_chunk = now
                if first_data is None:
                    first_data = now - start
                    log.info(f"  first data after {first_data:.0f}s")
                try:
                    obj = json.loads(line)
                except ValueError:
                    raise OllamaBadResponse(f"Ollama sent a line that is not JSON: {line[:200]!r}")
                if obj.get("error"):
                    raise OllamaBadResponse(f"Ollama reported an error mid-response: {obj['error']}")
                if obj.get("thinking"):
                    thinking_parts.append(obj["thinking"])
                if obj.get("response"):
                    response_parts.append(obj["response"])
                if now - last_beat >= config.HEARTBEAT_SECONDS:
                    last_beat = now
                    log.info(f"  ... {label}: {now - start:.0f}s, "
                             f"{len(thinking_parts)} thinking / {len(response_parts)} response tokens so far")
                if obj.get("done"):
                    final = obj
                    break
        except requests.exceptions.RequestException as e:
            if _is_read_timeout(e):
                raise OllamaTimeout(f"Ollama went silent for more than {runtime.inactivity_timeout:g}s "
                                    f"(label={label}, {time.monotonic() - start:.0f}s into the call).") from e
            raise OllamaUnavailable(f"Connection to Ollama dropped mid-response (label={label}): "
                                    f"{e.__class__.__name__}. " + _unreachable_hint(runtime)) from e

    if final is None:
        raise OllamaBadResponse(f"Ollama's stream ended before it said it was done (label={label}).")

    text = "".join(response_parts)
    if not text.strip():
        raise OllamaBadResponse(f"Ollama returned an empty response (label={label}, "
                                f"done_reason={final.get('done_reason')}).")

    return GenerateResult(
        text=text,
        thinking="".join(thinking_parts),
        done_reason=final.get("done_reason", "unknown"),
        prompt_tokens=final.get("prompt_eval_count", "?"),
        response_tokens=final.get("eval_count", "?"),
        seconds=time.monotonic() - start,
        first_data_seconds=first_data or 0.0,
        max_gap_seconds=max_gap,
        attempts=1,
        raw_final=final,
    )


def context_share(prompt_tokens, response_tokens, num_ctx):
    """Share of num_ctx used by one call (prompt + response, thinking
    included), rounded to 3 places; None if any number is unknown."""
    if not all(isinstance(n, int) and n >= 0 for n in (prompt_tokens, response_tokens)):
        return None
    if not isinstance(num_ctx, int) or num_ctx <= 0:
        return None
    return round((prompt_tokens + response_tokens) / num_ctx, 3)


def context_warning(label, prompt_tokens, response_tokens, num_ctx, ratio=None):
    """
    Early warning, before the hard limit: a message when one call used at
    least config.CONTEXT_WARN_RATIO of the context window, else None. Most of
    a long call is thinking, which counts against the same window as the
    lesson text.
    """
    ratio = config.CONTEXT_WARN_RATIO if ratio is None else ratio
    share = context_share(prompt_tokens, response_tokens, num_ctx)
    if share is None or share < ratio:
        return None
    return (f"{label}: used {prompt_tokens + response_tokens:,} of {num_ctx:,} context tokens "
            f"({share:.0%}; thinking counts). Close to the limit - at 100% the output is cut off "
            f"(done_reason=length).")


def generate(runtime, prompt, label, debug_dir=None, timings=None):
    """
    One model call with retries. Returns GenerateResult; raises an
    OllamaError subclass when it can't get a usable answer.

    debug_dir: if given, writes debug_<label>_metadata.txt and (if the
               model returned one) debug_<label>_thinking.txt there.
    timings:   optional list; a dict with this call's timing is appended,
               for the run summary and manifest.
    """
    attempts = 1 + max(0, runtime.max_retries)
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            log.info(f"Calling {runtime.model} (label={label}, attempt {attempt}/{attempts}) ...")
            result = _one_attempt(runtime, prompt, label)
            result.attempts = attempt
            break
        except (OllamaUnavailable, OllamaTimeout, OllamaBadResponse, OllamaModelMissing) as e:
            last_error = e
            if not e.retryable or attempt == attempts:
                raise
            wait = runtime.retry_backoff[min(attempt - 1, len(runtime.retry_backoff) - 1)] \
                if runtime.retry_backoff else 0
            log.warning(f"{label}: {e} - retrying in {wait}s (attempt {attempt + 1}/{attempts}).")
            time.sleep(wait)
    else:  # pragma: no cover - loop always breaks or raises
        raise last_error

    log.info(f"Ollama finished (label={label}): done_reason={result.done_reason}, "
             f"prompt_tokens={result.prompt_tokens}, response_tokens={result.response_tokens}, "
             f"{result.seconds:.0f}s (first data {result.first_data_seconds:.0f}s, "
             f"longest pause {result.max_gap_seconds:.1f}s)")
    if result.done_reason == "length":
        log.warning(f"{label}: Ollama stopped because it ran out of context/token budget "
                    f"(done_reason=length) - the output is probably cut off.")
    else:
        warning = context_warning(label, result.prompt_tokens, result.response_tokens,
                                  runtime.options.get("num_ctx"))
        if warning:
            log.warning(warning)

    if timings is not None:
        timings.append({
            "label": label,
            "seconds": round(result.seconds, 1),
            "first_data_seconds": round(result.first_data_seconds, 1),
            "max_gap_seconds": round(result.max_gap_seconds, 1),
            "prompt_tokens": result.prompt_tokens,
            "response_tokens": result.response_tokens,
            "done_reason": result.done_reason,
            "attempts": result.attempts,
            "context_used": context_share(result.prompt_tokens, result.response_tokens,
                                          runtime.options.get("num_ctx")),
        })

    if debug_dir:
        with open(f"{debug_dir}/debug_{label}_metadata.txt", "w", encoding="utf-8") as f:
            for key in ("done", "done_reason", "prompt_eval_count", "eval_count",
                        "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
                f.write(f"{key}: {result.raw_final.get(key, '(not present)')}\n")
            f.write(f"wall_seconds: {result.seconds:.1f}\n")
            f.write(f"first_data_seconds: {result.first_data_seconds:.1f}\n")
            f.write(f"max_gap_seconds: {result.max_gap_seconds:.1f}\n")
            f.write(f"attempts: {result.attempts}\n")
        if result.thinking:
            with open(f"{debug_dir}/debug_{label}_thinking.txt", "w", encoding="utf-8") as f:
                f.write(result.thinking)

    if result.thinking:
        log.debug(f"{label}: thinking trace ~{len(result.thinking.split())} words")
    return result
