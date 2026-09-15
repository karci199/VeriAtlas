"""Local receiver for files that can only be downloaded inside a browser session.

Some portals (TÜİK Veri Portalı) answer "Erişim engellendi" to any client but a browser
page on their own origin. The page can fetch the file; it cannot save it. This listens on
127.0.0.1 and writes whatever the page POSTs to `<target>/<name>`, so the bytes reach
the raw store untouched.

    python scripts/receive_browser_files.py C:/veri-ham/tuik/ceza_portal [port]

In the page: fetch(url) -> blob -> fetch("http://127.0.0.1:8765/<name>", {method: "POST", body: blob}).
Listens on loopback only; names are reduced to their last path part.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

TARGET = Path(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765


class Receiver(BaseHTTPRequestHandler):
    def cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self) -> None:
        # A relay page for portals whose Content-Security-Policy blocks fetch() to loopback:
        # the portal page opens this one and postMessage()s {name, blob}; this page, being
        # same-origin with the receiver, POSTs it here.
        page = (
            b"<script>addEventListener('message',async e=>{const r=await fetch('/'+"
            b"encodeURIComponent(e.data.name),{method:'POST',body:e.data.blob});"
            b"e.source.postMessage({name:e.data.name,status:r.status},'*')});"
            b"opener&&opener.postMessage('hazir','*')</script>relay"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self) -> None:
        name = Path(unquote(self.path)).name
        body = self.rfile.read(int(self.headers["Content-Length"]))
        TARGET.mkdir(parents=True, exist_ok=True)
        (TARGET / name).write_bytes(body)
        print(f"{name} {len(body)} bayt", flush=True)
        self.send_response(200)
        self.cors()
        self.end_headers()
        self.wfile.write(b"ok")


HTTPServer(("127.0.0.1", PORT), Receiver).serve_forever()
