import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from seagreen.server import DashboardServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.server = DashboardServer(0, Path(cls.directory.name) / 'records')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.directory.cleanup()

    def request(self, path, method='GET', body=None, authorized=True, extra=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if authorized:
            headers['Authorization'] = 'Bearer ' + self.server.token
        headers.update(extra or {})
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def test_loopback_and_unauthorized(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        self.assertEqual(self.request('/api/state', authorized=False)[0], 401)
        self.assertEqual(self.request('/api/record/start', 'POST', {'title': 'bad'}, authorized=False)[0], 401)
        self.assertEqual(self.request('/api/state')[0], 200)

    def test_foreign_origin_and_rebinding_rejected(self):
        self.assertEqual(self.request('/api/state', extra={'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/state', extra={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/state', extra={'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_process_controls_require_auth_and_valid_identity(self):
        import os
        import psutil
        from unittest.mock import patch
        payload = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'mode': 'force'}
        self.assertEqual(self.request('/api/process/control', 'POST', payload, authorized=False)[0], 401)
        self.assertEqual(self.request('/api/process/control', 'POST', payload)[0], 400)
        with patch('seagreen.server.control_process', return_value={'ok': True, 'message': 'Requested'}) as control:
            self.assertEqual(self.request('/api/process/control', 'POST', payload)[0], 200)
            control.assert_called_once_with(payload['pid'], payload['created'], 'force')

    def test_legacy_control_endpoints_removed(self):
        self.assertEqual(self.request('/api/kill/1', 'POST', {})[0], 404)
        self.assertEqual(self.request('/api/green/1', 'POST', {})[0], 404)

    def test_static_csp_and_no_remote_assets(self):
        status, html, headers = self.request('/', authorized=False)
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        # An explicit release link is navigation, not a remotely loaded asset.
        self.assertNotIn(b'https://', html.replace(b'https://github.com/serene-interactive/Seagreen/releases/latest', b''))
        self.assertNotIn(self.server.token.encode(), html)
        for file in ['/app.js', '/style.css', '/mark.svg']:
            self.assertEqual(self.request(file, authorized=False)[0], 200)
        self.assertEqual(self.request('/../server.py', authorized=False)[0], 404)

    def test_bad_input_and_record_export(self):
        self.assertEqual(self.request('/api/record/start', 'POST', [1, 2])[0], 400)
        self.assertEqual(self.request('/api/record/start', 'POST', {'units': -1})[0], 400)
        status, body, _ = self.request('/api/record/start', 'POST', {'title': '<img src=x onerror=alert(1)>', 'units': 1})
        self.assertEqual(status, 200)
        identifier = json.loads(body)['id']
        self.assertEqual(self.request('/api/monitor/pause', 'POST', {'paused': True})[0], 400)
        self.server.monitor.sample()
        self.assertEqual(self.request('/api/record/finish', 'POST', {})[0], 200)
        status, body, headers = self.request('/api/record/export', 'POST', {'id': identifier, 'format': 'csv'})
        self.assertEqual(status, 200)
        self.assertIn(b'power_source_scope', body)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertEqual(self.request('/api/record/delete', 'POST', {'id': identifier})[0], 200)
        self.assertEqual(self.request('/api/record/delete', 'POST', {'id': '../../outside'})[0], 400)


if __name__ == '__main__':
    unittest.main()
