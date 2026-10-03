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

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexora — Team Analytics Platform</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1a202c;background:#fff}
nav{display:flex;justify-content:space-between;align-items:center;padding:18px 6%;border-bottom:1px solid #edf2f7}
.logo{font-weight:800;font-size:20px;color:#2b6cb0}
nav a{margin-left:24px;text-decoration:none;color:#4a5568;font-size:14px}
.hero{text-align:center;padding:90px 6% 60px;background:linear-gradient(180deg,#ebf4ff,#fff)}
.hero h1{font-size:44px;margin-bottom:16px}
.hero p{color:#4a5568;font-size:18px;max-width:560px;margin:0 auto 32px}
.btn{display:inline-block;background:#2b6cb0;color:#fff;padding:14px 34px;border-radius:8px;text-decoration:none;font-weight:600}
.feats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;padding:60px 6%}
.card{border:1px solid #e2e8f0;border-radius:12px;padding:28px}
.card h3{margin-bottom:10px;font-size:17px}
.card p{color:#718096;font-size:14px;line-height:1.6}
footer{text-align:center;padding:32px;color:#a0aec0;font-size:13px;border-top:1px solid #edf2f7}
</style></head><body>
<nav><div class="logo">Nexora</div><div><a href="#">Product</a><a href="#">Pricing</a><a href="#">Docs</a><a href="#">Sign in</a></div></nav>
<div class="hero"><h1>Analytics your team will actually use</h1>
<p>Nexora turns raw product data into dashboards everyone understands. No SQL required.</p>
<a class="btn" href="#">Start free trial</a></div>
<div class="feats">
<div class="card"><h3>Real-time dashboards</h3><p>Metrics update the second events happen. Build views with drag and drop.</p></div>
<div class="card"><h3>Team workspaces</h3><p>Share boards, annotate charts, and keep every discussion next to the data.</p></div>
<div class="card"><h3>200+ integrations</h3><p>Connect your warehouse, CRM, and billing stack in a few clicks.</p></div>
</div>
<footer>&copy; 2026 Nexora Labs, Inc. &middot; Privacy &middot; Terms &middot; Status</footer>
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
