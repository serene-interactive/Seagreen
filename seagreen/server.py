"""Loopback-only dashboard with per-launch authorization and no remote assets."""
import argparse
import csv
import hmac
import io
import json
import mimetypes
import os
import secrets
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .jobs import JobManager
from .control import control_process, PROTECTED
import psutil
from .monitor import Monitor

ASSETS = Path(__file__).with_name('web')


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, port, directory=None):
        self.token = secrets.token_urlsafe(32)
        self.monitor = Monitor(directory=directory)
        self.jobs = JobManager()
        super().__init__(('127.0.0.1', port), DashboardHandler)
        self.origin = 'http://127.0.0.1:' + str(self.server_address[1])
        self.launch_url = self.origin + '/#' + self.token

    def server_close(self):
        try:
            self.monitor.stop()
        finally:
            try:
                if self.jobs.snapshot()['running']:
                    self.jobs.stop()
            finally:
                super().server_close()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = 'Seagreen/3.0'

    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, status, data, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, api=False):
        if self.headers.get('Host') != urlsplit(self.server.origin).netloc:
            self.reply(403, {'error': 'Invalid local host.'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            self.reply(403, {'error': 'Foreign origin rejected.'})
            return False
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.reply(403, {'error': 'Cross-site requests are not allowed.'})
            return False
        if api:
            credential = self.headers.get('Authorization', '')
            expected = 'Bearer ' + self.server.token
            if not hmac.compare_digest(credential.encode(), expected.encode()):
                self.reply(401, {'error': 'Open the authorized URL shown by Seagreen in your terminal.'})
                return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(path.startswith('/api/')):
            return
        if path == '/api/state':
            result = self.server.monitor.snapshot()
            result['job'] = self.server.jobs.snapshot()
            protected_pids = {os.getpid(), *(p.pid for p in psutil.Process().parents())}
            if result.get('sample'):
                for process in result['sample']['processes']:
                    process['protected'] = process['pid'] in protected_pids or process['pid'] <= 1 or process['name'].lower() in PROTECTED
            self.reply(200, result)
        elif path == '/api/recordings':
            self.reply(200, self.server.monitor.recordings())
        elif path in ('/', '/index.html', '/app.js', '/style.css', '/mark.svg'):
            file = ASSETS / ('index.html' if path == '/' else path.lstrip('/'))
            try:
                self.reply(200, file.read_bytes(), (mimetypes.guess_type(str(file))[0] or 'text/plain') + '; charset=utf-8')
            except OSError:
                self.reply(404, {'error': 'Asset not found.'})
        else:
            self.reply(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self.allowed(api=True):
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.reply(415, {'error': 'JSON required.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                self.reply(413, {'error': 'Invalid request size.'})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object.')
            path = urlsplit(self.path).path
            monitor = self.server.monitor
            if path == '/api/record/start':
                result = monitor.start_recording(payload.get('title', ''), payload.get('notes', ''), payload.get('units', 1), payload.get('unitName', 'task'))
            elif path == '/api/record/finish':
                result = monitor.finish_recording()
            elif path == '/api/record/delete':
                monitor.delete_recording(payload.get('id', ''))
                result = {'ok': True}
            elif path == '/api/record/export':
                record = next((r for r in monitor.recordings() if r['id'] == payload.get('id')), None)
                if not record:
                    raise ValueError('Recording not found.')
                if payload.get('format') == 'csv':
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(['timestamp', 'cpu_percent', 'memory_gb', 'power_watts', 'power_source_scope'])
                    for point in record['points']:
                        writer.writerow([point['date'], point['cpu'], point['memoryGB'], point['watts'], point['powerKey']])
                    self.reply(200, output.getvalue().encode(), 'text/csv; charset=utf-8', 'Seagreen-' + record['id'] + '.csv')
                else:
                    self.reply(200, record, filename='Seagreen-' + record['id'] + '.json')
                return
            elif path == '/api/monitor/pause':
                with monitor.lock:
                    if monitor.active:
                        raise ValueError('Finish the recording before pausing monitoring.')
                    if not isinstance(payload.get('paused'), bool):
                        raise ValueError('Invalid paused state.')
                    monitor.paused = payload['paused']
                result = {'ok': True}
            elif path == '/api/process/control':
                result = control_process(payload.get('pid'), payload.get('created'), payload.get('mode'))
            elif path == '/api/job/launch':
                result = self.server.jobs.launch(payload.get('executable'), payload.get('arguments', []), payload.get('efficient', True))
            elif path == '/api/job/stop':
                self.server.jobs.stop()
                result = {'ok': True}
            else:
                self.reply(404, {'error': 'Not found.'})
                return
            self.reply(200, result)
        except (ValueError, TypeError, KeyError) as error:
            self.reply(400, {'error': str(error)})
        except OSError as error:
            self.reply(409, {'error': str(error)})


def start_web_server(port=8080, directory=None):
    try:
        server = DashboardServer(port, directory=directory)
    except OSError:
        return None
    server.monitor.start()
    threading.Thread(target=server.serve_forever, name='Seagreen-web', daemon=True).start()
    return server


def main():
    parser = argparse.ArgumentParser(description='Seagreen v3.0.0 local web UI')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = start_web_server(args.port)
    if not server:
        parser.error('Could not bind to the local port. Try --port 8081.')
    print('Seagreen v3.0.0 - Local monitoring. Press Ctrl+C to stop.')
    print('Open this private local URL:\n' + server.launch_url)
    if not args.no_browser:
        webbrowser.open(server.launch_url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        if server.jobs.snapshot()['running']:
            print('Requesting termination of the process launched by Seagreen.')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
