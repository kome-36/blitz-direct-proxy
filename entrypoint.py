#!/usr/bin/env python3
"""Direct (no-argo) xray node for blitz.cloud.

Architecture:
  client --TLS--> blitz.cloud edge (terminates TLS, *.blitz.cloud cert)
         --plain HTTP--> container:$PORT --xray fallback--> 127.0.0.1:3001 (vless+ws, path /vless)

The platform only forwards to ONE container port, so xray's outer inbound
listens on $PORT and dispatches by HTTP path. Container-side TLS is OFF
(the edge already terminated it). Clients use security=tls, sni=DOMAIN.

Env vars (set in blitz.cloud dashboard > app > Settings > Environment):
  PORT    container http port (default 8080; the platform usually injects its own)
  UUID    node UUID (REQUIRED for stability; generated per-boot if missing,
          which breaks clients on every restart/sleep-wake)
  DOMAIN  public address, e.g. proxy.cloud.blitz.cloud (REQUIRED for /sub links)
  NAME    node remark prefix (default "blitz-direct")
"""
import base64
import json
import os
import subprocess
import sys
import threading
import uuid as uuidlib
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8080"))
UUID = os.environ.get("UUID") or str(uuidlib.uuid4())
DOMAIN = os.environ.get("DOMAIN", "").strip()
NAME = os.environ.get("NAME", "blitz-direct")

if not os.environ.get("UUID"):
    print("WARNING: UUID env not set - generated one for THIS BOOT ONLY. "
          "Clients will break after every restart/sleep. Set UUID in app settings.",
          flush=True)
if not DOMAIN:
    print("WARNING: DOMAIN env not set - /sub links will have an empty address. "
          "Set DOMAIN to the app's public address (e.g. proxy.cloud.blitz.cloud).",
          flush=True)

RUNTIME = "/tmp/xray"
os.makedirs(RUNTIME, exist_ok=True)

config = {
    "log": {"loglevel": "warning"},
    "inbounds": [
        {
            "port": PORT,
            "protocol": "vless",
            "settings": {
                "clients": [{"id": UUID}],
                "decryption": "none",
                "fallbacks": [
                    {"path": "/vless", "dest": 3001},
                    {"dest": 3002},
                ],
            },
            "streamSettings": {"network": "tcp"},
        },
        {
            "port": 3001, "listen": "127.0.0.1", "protocol": "vless",
            "settings": {"clients": [{"id": UUID}], "decryption": "none"},
            "streamSettings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {"path": "/vless"},
            },
        },
    ],
    "outbounds": [{"protocol": "freedom", "tag": "direct"}],
}
with open(os.path.join(RUNTIME, "config.json"), "w") as f:
    json.dump(config, f)

node = (
    f"vless://{UUID}@{DOMAIN}:443?encryption=none&security=tls"
    f"&sni={DOMAIN}&type=ws&host={DOMAIN}&path=%2Fvless#{NAME}"
)
sub_b64 = base64.b64encode(node.encode()).decode()

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>blitz-direct node</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:40px auto">
<h2>blitz-direct proxy node</h2>
<p>Status: <b>online</b></p>
<p>Subscription: <a href="/sub">/sub</a></p>
<p>Protocol: VLESS + WS + TLS (port 443, path /vless), no argo tunnel.</p>
</body></html>""".encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/sub":
            body = sub_b64.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        elif self.path == "/":
            body = PAGE
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            body = b"not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    web = HTTPServer(("127.0.0.1", 3002), Handler)
    threading.Thread(target=web.serve_forever, daemon=True).start()
    print(f"web ui on 127.0.0.1:3002, xray on :{PORT} (uuid {UUID[:8]}..., domain {DOMAIN or '<unset>'})",
          flush=True)
    proc = subprocess.Popen(["/app/bin/xray", "-c", os.path.join(RUNTIME, "config.json")])
    try:
        proc.wait()
    except KeyboardInterrupt:
        pass
    sys.exit(proc.returncode or 0)


if __name__ == "__main__":
    main()
