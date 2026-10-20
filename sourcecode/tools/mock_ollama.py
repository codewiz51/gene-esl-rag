#!/usr/bin/env python3
"""
mock_ollama.py - a fake Ollama server for testing the pipeline's plumbing
(error handling, retries, checkpoints, --resume) without the Studio and
without spending 40 minutes of real generation.

It answers /api/tags and /api/generate (streaming) and writes well-formed
but meaningless lesson text, shaped like whatever pass is asking.

Run it, then point the pipeline at it:
    python3 tools/mock_ollama.py --port 11500 &
    ESL_STUDIO_IP=127.0.0.1:11500 ...      (see --help; or edit config)

Easiest: run the pipeline with  --machine macbook --studio-ip 127.0.0.1:11500

Failure modes, chosen with --mode (or per request with the model name
"mock-<mode>"):
    ok        normal answers (default)
    hang      send one chunk, then go silent forever (tests --timeout)
    error500  HTTP 500 on every generate call (tests retries)
    flaky     HTTP 500 on the first generate call only, then ok
    empty     finish with an empty response (tests empty-answer retry)
    dropday   leave SUNDAY out of every pass (tests coverage retry)
    badreview self-review returns a cut-off week (tests the review guard)
    failat:N  HTTP 500 on generate call number N and after (tests --resume)

Not a test of lesson QUALITY - only of the pipeline around the model.
"""

import argparse
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
MAIN_SECTIONS = ["Warmup", "Vocabulary", "Story", "Grammar", "Examples", "Translation Practice", "Student Questions"]
FIVE_SECTIONS = ["Vocabulary Review", "Grammar Focus", "Mini Story", "Translation Practice", "Student Questions"]
INSTALLED = ["pipeline-qwen38:latest", "gene-qwen38:latest", "qwen3.8:27b-mlx"]

STATE = {"mode": "ok", "calls": 0, "delay": 0.0}


def body_for(section):
    if section == "Story":
        return ("**English:**\nMarisol feels a little off today. She tells Letia.\n\n"
                "**Spanish:**\nMarisol no se siente bien del todo hoy. Se lo cuenta a Letia.")
    if section in ("Warmup", "Student Questions"):
        return "1. How do you ___ today? (sentirse)\n2. Who ___ you the news? (contar)"
    if section == "Grammar":
        return ('Usamos "feel" para hablar de cómo estamos.\n\nPattern Practice:\n'
                "1. I ___ tired. (sentirse)")
    if section == "Vocabulary":
        return "- light-headed – mareada\n- warning sign – señal de alerta"
    if section == "Translation Practice":
        return "Spanish → English\n\n1. Me siento mareada.\n\nEnglish → Spanish\n\n1. I feel tired."
    return f"1. Mock {section.lower()} line with acentos: está, sí."


def week(sections, days=DAYS, sep=False):
    parts = []
    for d in days:
        block = [f"# {d}", ""]
        for s in sections:
            block += [f"## {s}", "", body_for(s), ""]
        parts.append("\n".join(block).strip())
    return ("\n\n---\n\n" if sep else "\n\n").join(parts) + "\n"


def answer(prompt, mode):
    days = DAYS[:-1] if mode == "dropday" else DAYS
    m = re.search(r"#BEGIN (?:FIVE_MINUTE_)?WEEK_TO_REVIEW\n(.*)\n#END (?:FIVE_MINUTE_)?WEEK_TO_REVIEW", prompt, re.S)
    if m:
        text = m.group(1)
        if mode == "badreview":
            return text[: len(text) // 3]
        return text
    if "#BEGIN MONDAY_STORY\n" in prompt:
        return week(FIVE_SECTIONS, days, sep=True)
    if "_GRAMMAR_ENGLISH" in prompt:
        return week(["Grammar"], days)
    line = re.search(r"This pass produces ONLY: (.*)", prompt)
    if line:
        wanted = [s for s in MAIN_SECTIONS if f"## {s}" in line.group(1)]
        return week(wanted, days)
    return "I don't recognise this prompt."


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("mock_ollama: " + (fmt % a) + "\n")

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json(200, {"models": [{"name": n, "model": n} for n in INSTALLED]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/generate":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or b"{}")
        model = req.get("model", "")
        mode = STATE["mode"]
        if model.startswith("mock-"):
            mode = model[len("mock-"):]
        elif model not in INSTALLED:
            return self._json(404, {"error": f"model '{model}' not found"})

        STATE["calls"] += 1
        n = STATE["calls"]
        if mode == "error500" or (mode == "flaky" and n == 1):
            return self._json(500, {"error": "mock server error"})
        if mode.startswith("failat:") and n >= int(mode.split(":")[1]):
            return self._json(500, {"error": f"mock failure at call {n}"})

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunk(obj):
            data = (json.dumps(obj) + "\n").encode()
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
            self.wfile.flush()

        try:
            chunk({"model": model, "thinking": "Let me think. ", "response": "", "done": False})
            if mode == "hang":
                time.sleep(3600)
                return
            text = "" if mode == "empty" else answer(req.get("prompt", ""), mode)
            for piece in re.findall(r"\S+\s*|\s+", text):
                chunk({"model": model, "response": piece, "done": False})
                if STATE["delay"]:
                    time.sleep(STATE["delay"])
            chunk({"model": model, "response": "", "done": True, "done_reason": "stop",
                   "prompt_eval_count": len(req.get("prompt", "")) // 4, "eval_count": len(text) // 4,
                   "total_duration": 1, "load_duration": 0, "prompt_eval_duration": 0, "eval_duration": 1})
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=11500)
    ap.add_argument("--mode", default="ok")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds between streamed words")
    a = ap.parse_args()
    STATE["mode"], STATE["delay"] = a.mode, a.delay
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    print(f"mock_ollama listening on 127.0.0.1:{a.port}, mode={a.mode}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
