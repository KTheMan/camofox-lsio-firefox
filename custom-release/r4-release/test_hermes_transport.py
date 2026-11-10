"""Run in an isolated test container; exercises production client functions
against a local dummy HTTP server without importing any Hermes profile/state.
"""
import ast
import json
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
import unittest
import requests

seen = []
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/redirect':
            self.send_response(302); self.send_header('Location', '/echo'); self.end_headers(); return
        seen.append(self.headers.get('Authorization'))
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(b'{"ok":true,"result":1}')
    do_POST = do_GET

class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        source = Path(__file__).parent / 'hermes-camofox/camofox_client.py'
        tree = ast.parse(source.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'request', '_error_detail', 'check_camofox_available'}]
        cls.ns = {'requests': requests, 'Any': Any, 'Optional': Optional,
                  'get_camofox_url': lambda: 'http://127.0.0.1:' + str(cls.server.server_port),
                  'get_command_timeout': lambda: 3, '_auth_headers': lambda: {'Authorization': 'Bearer dummy-key'},
                  '_vnc_url_by_camofox_url': {}, '_vnc_url_from_health': lambda *_: None}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), cls.ns)
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close()
    def test_environment_proxies_never_receive_authenticated_or_fill_requests(self):
        original = os.environ.copy()
        try:
            for name in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
                with self.subTest(proxy=name):
                    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
                        os.environ.pop(key, None)
                    os.environ.update({name: 'http://127.0.0.1:9', 'NO_PROXY': '', 'no_proxy': ''})
                    response = self.ns['request']('post', '/evaluate', json={'value': 'dummy-fill'})
                    self.assertEqual(response.json()['result'], 1)
                    self.assertEqual(seen[-1], 'Bearer dummy-key')
                    self.assertTrue(self.ns['check_camofox_available']())
        finally: os.environ.clear(); os.environ.update(original)
    def test_authenticated_redirect_is_not_followed(self):
        before = len(seen)
        response = self.ns['request']('get', '/redirect')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(seen), before)

if __name__ == '__main__': unittest.main()
