"""Machine detection and endpoint resolution."""
import os
import unittest
from unittest import mock

from tests._support import quiet_logging

quiet_logging()
import config  # noqa: E402
from errors import InputError  # noqa: E402


def resolve(home, hostname, **kw):
    env = {k: v for k, v in os.environ.items() if k not in ("ESL_MACHINE", "ESL_STUDIO_IP")}
    with mock.patch.dict(os.environ, env, clear=True), \
         mock.patch("os.path.expanduser", return_value=home), \
         mock.patch("socket.gethostname", return_value=hostname):
        return config.resolve_runtime(**kw)


class Detection(unittest.TestCase):
    def test_macbook_is_client_of_studio(self):
        rt = resolve("/Users/Gene", "MacBook-Pro.local")
        self.assertEqual((rt.machine, rt.mode, rt.base_url), ("macbook", "client", "http://192.168.4.47:11434"))

    def test_studio_is_local(self):
        rt = resolve("/Users/gene", "studio.local")
        self.assertEqual((rt.machine, rt.mode, rt.base_url), ("studio", "local", "http://localhost:11434"))

    def test_home_and_hostname_disagree(self):
        with self.assertRaises(InputError):
            resolve("/Users/Gene", "studio.local")

    def test_unknown_machine(self):
        with self.assertRaises(InputError):
            resolve("/Users/nobody", "vm")

    def test_hostname_alone_is_enough(self):
        self.assertEqual(resolve("/Users/nobody", "studio.local").machine, "studio")


class Overrides(unittest.TestCase):
    def test_studio_ip_on_macbook(self):
        self.assertEqual(resolve("/Users/Gene", "MacBook-Pro.local", studio_ip="192.168.4.50").base_url,
                         "http://192.168.4.50:11434")

    def test_ip_with_port(self):
        self.assertEqual(resolve("/Users/Gene", "MacBook-Pro.local", studio_ip="127.0.0.1:11500").base_url,
                         "http://127.0.0.1:11500")

    def test_studio_ip_refused_on_studio(self):
        with self.assertRaises(InputError):
            resolve("/Users/gene", "studio.local", studio_ip="192.168.4.47")

    def test_machine_flag(self):
        self.assertEqual(resolve("/Users/nobody", "vm", machine="macbook").mode, "client")

    def test_timeout(self):
        self.assertEqual(resolve("/Users/gene", "studio.local", timeout=30).inactivity_timeout, 30)
        with self.assertRaises(InputError):
            resolve("/Users/gene", "studio.local", timeout=0)

    def test_default_model(self):
        self.assertEqual(resolve("/Users/gene", "studio.local").model, "pipeline-qwen38:latest")


if __name__ == "__main__":
    unittest.main()
