#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

image=${1:?Usage: bash scripts/smoke-image.sh IMAGE}
desktop="$PWD/deploy/homelab/desktop"
container=$(docker run -d --security-opt seccomp=unconfined --shm-size=1g \
  --mount "type=bind,source=$desktop/nginx.conf,target=/defaults/default.conf,readonly" \
  --mount "type=bind,source=$desktop/startwm.sh,target=/defaults/startwm.sh,readonly" \
  --mount "type=bind,source=$desktop,target=/opt/camofox-desktop,readonly" \
  "$image")
cleanup() {
  status=$?
  if (( status != 0 )); then
    docker logs --tail 80 "$container" >&2 || true
  fi
  docker rm -fv "$container" >/dev/null || true
}
trap cleanup EXIT

ready() {
  docker exec "$container" sh -c 'test -S /tmp/.X11-unix/X1 && pgrep -x openbox >/dev/null && curl -fsS http://127.0.0.1:9377/health >/dev/null && curl -fsS http://127.0.0.1:3000/ >/dev/null'
}
for attempt in {1..45}; do
  if ready 2>/dev/null; then
    break
  fi
  sleep 1
done
ready

docker exec -i "$container" python3 - <<'PY'
import http.client
import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

title = 'Camofox overlay smoke'


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        html = f'<title>{title}</title><main><h1>{title}</h1></main>'.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def request(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=40)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.read() if response.status != 101 else b''
    finally:
        connection.close()


with ThreadingHTTPServer(('127.0.0.1', 0), Fixture) as fixture:
    Thread(target=fixture.serve_forever, daemon=True).start()
    identity = {'userId': 'overlay-ci', 'sessionKey': 'smoke'}
    url = f'http://127.0.0.1:{fixture.server_port}/'
    status, raw = request(9377, 'POST', '/tabs', json.dumps(dict(identity, url=url)),
                          {'Content-Type': 'application/json'})
    assert status == 200, (status, raw)
    tab = json.loads(raw)['tabId']
    path = f'/tabs/{tab}'
    query = '?userId=overlay-ci&sessionKey=smoke'
    try:
        status, raw = request(9377, 'GET', path + '/snapshot' + query)
        assert status == 200 and title in json.loads(raw)['snapshot'], (status, raw)
        windows = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
        assert title in windows, 'API tab is missing from the Selkies X11 display'
        print('Camofox created a visible API tab and captured its content without a viewer.')
    finally:
        request(9377, 'DELETE', path + query)

headers = {
    'Connection': 'Upgrade',
    'Upgrade': 'websocket',
    'Sec-WebSocket-Version': '13',
    'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
    'Origin': 'http://127.0.0.1:3000',
}
frontend = Path('/usr/share/selkies/web')
web_assets = [asset.read_bytes() for asset in frontend.rglob('*.js')]
if any(b'/api/websockets' in asset for asset in web_assets):
    stream_path = '/api/websockets'
    status, _ = request(3000, 'GET', '/api/status')
    assert status == 200, f'Selkies status endpoint returned {status} instead of 200'
else:
    # The older dashboard builds this path by appending to the page URL.
    legacy_route = re.compile(rb'''\.pathname\s*\+=\s*["'`]websockets["'`]''')
    assert any(b'/websockets' in asset or legacy_route.search(asset) for asset in web_assets), 'Unrecognized Selkies frontend streaming route'
    stream_path = '/websockets'

status, _ = request(3000, 'GET', stream_path, headers=headers)
assert status == 101, f'Selkies stream {stream_path} returned {status} instead of 101. Check upstream route and deployment proxy compatibility.'
status, _ = request(3000, 'GET', stream_path, headers=dict(headers, Origin='https://unrelated.example'))
assert status == 403, f'Selkies accepted a foreign WebSocket origin with status {status}'
status, _ = request(3000, 'POST', '/api/tokens')
assert status == 404, f'Selkies control plane is routed with status {status}'
for path in ('/files', '/api/files'):
    status, _ = request(3000, 'GET', path)
    assert status == 404, f'Selkies file endpoint {path} is routed with status {status}'
print(f'Selkies upgraded {stream_path}, rejected a foreign origin and kept its control and file endpoints private.')
PY
