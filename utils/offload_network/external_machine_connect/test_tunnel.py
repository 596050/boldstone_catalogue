import argparse
import unittest
from pathlib import Path
from unittest.mock import patch

import tunnel


class TunnelTests(unittest.TestCase):
    def settings(self, role: str) -> tunnel.Settings:
        return tunnel.Settings(
            role=role,
            relay="user@relay.example",
            relay_port=2222,
            relay_bind_port=41080,
            local_port=8000,
            identity=Path("key file"),
            ssh="ssh",
            reconnect_delay=5,
            strict_host_key_checking="yes",
        )

    def test_external_uses_loopback_reverse_forward(self) -> None:
        command = tunnel.ssh_command(self.settings("external"))
        self.assertIn("127.0.0.1:41080:127.0.0.1:8000", command)
        self.assertIn("-R", command)

    def test_source_uses_loopback_local_forward(self) -> None:
        command = tunnel.ssh_command(self.settings("source"))
        self.assertIn("127.0.0.1:8000:127.0.0.1:41080", command)
        self.assertIn("-L", command)

    def test_invalid_port_is_rejected(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            tunnel.port("0")

    @patch("tunnel.shutil.which", return_value=None)
    def test_missing_ssh_is_reported(self, _which: object) -> None:
        with self.assertRaises(SystemExit):
            tunnel.resolve_ssh(None)


if __name__ == "__main__":
    unittest.main()
