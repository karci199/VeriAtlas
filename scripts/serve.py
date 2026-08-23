"""Serve `public/` and `web/` for development, with caching turned off.

`python -m http.server` answers with a Last-Modified and nothing else, and the browser
takes that as licence to keep a copy. That is fine for data files and poison for the code:
edit `explorer.js`, reload, and the page runs yesterday's script while the file on disk is
today's. It cost three rounds of "the fix is not working" in one session — the fix was
working, the browser was not reading it.

So: `Cache-Control: no-store` on everything. The whole site is a few megabytes off local
disk, so there is nothing to save and one thing to get wrong.

A second, narrow job: `POST /ingest/<name>.json` writes the body to `raw/endeksa/geo/`.
A browser tab logged into endeksa.com pulls boundaries and pushes them here directly —
hundreds of megabytes that would otherwise have to be ferried out of the tab in slices.
Only that directory, only `.json` names, only bodies that parse as JSON; CORS is opened
for it because the push comes from another origin.

Run:  uv run python scripts/serve.py [port]
"""

import http.server
import json
import re
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
INGEST = ROOT / "raw" / "endeksa" / "geo"
NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}\.json$")


class NoCache(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        name = self.path.rsplit("/", 1)[-1]
        if not self.path.startswith("/ingest/") or not NAME.match(name):
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            json.loads(body)
        except ValueError:
            self.send_error(400, "not JSON")
            return
        INGEST.mkdir(parents=True, exist_ok=True)
        (INGEST / name).write_bytes(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"{name} {len(body)}".encode())

    def log_message(self, fmt, *args):
        # One line per request is noise while a page pulls forty files; errors still show.
        if not str(args[1] if len(args) > 1 else "").startswith("2"):
            super().log_message(fmt, *args)


class Threaded(socketserver.ThreadingTCPServer):
    """One thread per request.

    The plain TCPServer is single-threaded, and a browser holding a keep-alive connection
    open blocks every other request behind it — including anything else asking the same
    server a question, which then times out looking like the server is down.
    """

    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    with Threaded(("", PORT), NoCache) as server:
        print("sunucu:", f"http://localhost:{PORT}/web/explorer.html")
        print("kok   :", ROOT)
        server.serve_forever()


if __name__ == "__main__":
    main()
