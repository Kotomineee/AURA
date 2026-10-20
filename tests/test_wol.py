"""Unit tests of production functions extracted without third-party imports.

Run: python -m unittest discover -s tests -v
HTTP framework integration and hardware wake-up require separate validation.
"""
import ast
import ipaddress
import os
from pathlib import Path
import re
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


source = Path(__file__).resolve().parents[1] / "app" / "main.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
names = {"authorize", "wol_config", "wol_status", "wake_computer", "power_action"}
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
for node in functions:
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
env = dict(os=os, re=re, socket=socket, ipaddress=ipaddress,
           HTTPException=HTTPException, TOKEN="test-token", DRY_RUN=True)
import subprocess
env["subprocess"] = subprocess
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(source), "exec"), env)


class WolTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.dict(os.environ, {
            "WOL_MAC": "AA:BB:CC:DD:EE:02",
            "WOL_BROADCAST": "192.168.1.255", "WOL_PORT": "9"})
        self.settings.start()
        self.addCleanup(self.settings.stop)
        env["DRY_RUN"] = True
        self.req = SimpleNamespace(confirm=True)

    def test_authentication(self):
        for header in (None, "Bearer wrong"):
            with self.assertRaises(HTTPException) as caught:
                env["wake_computer"](self.req, header)
            self.assertEqual(caught.exception.status_code, 401)

    def test_confirmation(self):
        with self.assertRaises(HTTPException) as caught:
            env["wake_computer"](SimpleNamespace(confirm=False), "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 400)

    def test_invalid_configuration(self):
        for key, values in {
            "WOL_MAC": ["", "garbage", "FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"],
            "WOL_BROADCAST": ["hostname", "999.1.1.1"],
            "WOL_PORT": ["0", "65536", "abc"]
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), patch.dict(os.environ, {key: value}):
                    self.assertFalse(env["wol_status"]("Bearer test-token")["configured"])

    def test_simulation_sends_nothing(self):
        with patch.object(socket, "socket") as sender:
            result = env["wake_computer"](self.req, "Bearer test-token")
            sender.assert_not_called()
        self.assertIn("SIMULAÇÃO", result["message"])

    def test_packet_and_destination(self):
        env["DRY_RUN"] = False
        with patch.object(socket, "socket") as factory:
            sender = factory.return_value.__enter__.return_value
            env["wake_computer"](self.req, "Bearer test-token")
            sender.sendto.assert_called_once_with(
                bytes([255])*6 + bytes.fromhex("aabbccddee02")*16,
                ("192.168.1.255", 9))
            sender.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def test_network_failure(self):
        env["DRY_RUN"] = False
        with patch.object(socket, "socket", side_effect=OSError):
            with self.assertRaises(HTTPException) as caught:
                env["wake_computer"](self.req, "Bearer test-token")
        self.assertEqual(caught.exception.status_code, 502)

    def test_power_simulation(self):
        with patch.object(subprocess, "run") as run:
            for action in ("shutdown", "restart"):
                result = env["power_action"](SimpleNamespace(confirm=True, action=action), "Bearer test-token")
                self.assertIn("SIMULAÇÃO", result["message"])
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
