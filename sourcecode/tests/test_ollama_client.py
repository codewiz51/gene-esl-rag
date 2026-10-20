"""ollama_client against the in-process mock server (no Studio needed)."""
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

from tests._support import quiet_logging

quiet_logging()
import config  # noqa: E402
import mock_ollama  # noqa: E402
import ollama_client  # noqa: E402
from errors import OllamaBadResponse, OllamaModelMissing, OllamaTimeout, OllamaUnavailable  # noqa: E402


class Client(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(mock_ollama.Handler):
            def log_message(self, *args):  # keep the test output clean
                pass

        class QuietServer(ThreadingHTTPServer):
            # Tests hang up on the server on purpose (timeouts, errors). On
            # macOS that surfaces as ConnectionResetError in the server's
            # thread, which socketserver prints as a traceback even though
            # every test passes. Ignore exactly those; report anything else.
            def handle_error(self, request, client_address):
                if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
                    return
                super().handle_error(request, client_address)

        cls.server = QuietServer(("127.0.0.1", 0), QuietHandler)
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        mock_ollama.STATE.update(mode="ok", calls=0, delay=0.0)

    def rt(self, model="pipeline-qwen38:latest", url=None, retries=2, timeout=5):
        return config.Runtime(machine="macbook", mode="client", base_url=url or self.url, model=model,
                              detected_by="test", connect_timeout=2, inactivity_timeout=timeout,
                              max_retries=retries, retry_backoff=[0, 0])

    def call(self, rt):
        return ollama_client.generate(rt, "This pass produces ONLY: ## Story\n", "t")

    def test_preflight_ok(self):
        self.assertIn("pipeline-qwen38:latest", ollama_client.preflight(self.rt()))

    def test_preflight_model_missing(self):
        with self.assertRaises(OllamaModelMissing):
            ollama_client.preflight(self.rt(model="nosuch:latest"))

    def test_preflight_unreachable(self):
        with self.assertRaises(OllamaUnavailable):
            ollama_client.preflight(self.rt(url="http://127.0.0.1:9"))

    def test_streamed_answer(self):
        result = self.call(self.rt())
        self.assertIn("# MONDAY", result.text)
        self.assertEqual((result.done_reason, result.attempts), ("stop", 1))
        self.assertTrue(result.thinking)

    def test_one_server_error_is_retried(self):
        result = self.call(self.rt(model="mock-flaky"))
        self.assertEqual(result.attempts, 2)

    def test_repeated_server_errors_give_up(self):
        with self.assertRaises(OllamaBadResponse):
            self.call(self.rt(model="mock-error500", retries=1))

    def test_empty_answer(self):
        with self.assertRaises(OllamaBadResponse):
            self.call(self.rt(model="mock-empty", retries=0))

    def test_silence_times_out(self):
        with self.assertRaises(OllamaTimeout):
            self.call(self.rt(model="mock-hang", retries=0, timeout=1))

    def test_unknown_model_on_generate(self):
        with self.assertRaises(OllamaModelMissing):
            self.call(self.rt(model="nosuch:latest", retries=0))


if __name__ == "__main__":
    unittest.main()
