#!/usr/bin/env python3
"""
errors.py

The pipeline's exception types. Every failure the pipeline expects is one
of these, so the orchestrators can print a plain message and exit with a
code that says what kind of problem it was, instead of a traceback.

Exit codes:
    0   success
    1   input problem (bad arguments, missing file, broken storyboard or
        template, resume mismatch) - fix the input and rerun
    2   Ollama problem (can't connect, model missing, timed out, bad
        response) - fix the Studio/network, then rerun with --resume
    3   the lesson was written, but it failed structural validation
        (missing day or section) - read the summary, fix by hand or rerun
    4   unexpected internal error (a bug) - details are in run.log
    130 interrupted with Ctrl-C - rerun with --resume
"""


class PipelineError(Exception):
    """Base class. exit_code is what the CLI exits with."""
    exit_code = 1


class InputError(PipelineError):
    """Bad command-line arguments or an input file that can't be used."""
    exit_code = 1


class TemplateError(InputError):
    """The lesson template is missing a rule block a pass needs."""


class ResumeError(InputError):
    """--resume can't continue the requested run."""


class OllamaError(PipelineError):
    """Anything that went wrong talking to Ollama."""
    exit_code = 2
    retryable = False


class OllamaUnavailable(OllamaError):
    """Could not connect, or the connection dropped."""
    retryable = True


class OllamaTimeout(OllamaError):
    """No data from Ollama for longer than the inactivity timeout."""
    retryable = True


class OllamaModelMissing(OllamaError):
    """The configured model is not installed on the Ollama server."""
    retryable = False


class OllamaBadResponse(OllamaError):
    """Ollama answered, but the answer can't be used."""

    def __init__(self, message, retryable=True):
        super().__init__(message)
        self.retryable = retryable


class ValidationFailed(PipelineError):
    """The lesson was written but is structurally incomplete."""
    exit_code = 3


UNEXPECTED_ERROR_EXIT = 4
INTERRUPTED_EXIT = 130
