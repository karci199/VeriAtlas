"""Serve `public/` and `web/` for development, with caching turned off.

`python -m http.server` answers with a Last-Modified and nothing else, and the browser
takes that as licence to keep a copy. That is fine for data files and poison for the code:
edit `explorer.js`, reload, and the page runs yesterday's script while the file on disk is
today's. It cost three rounds of "the fix is not working" in one session — the fix was
working, the browser was not reading it.

So: `Cache-Control: no-store` on everything. The whole site is a few megabytes off local
disk, so there is nothing to save and one thing to get wrong.

Run:  uv run python scripts/serve.py [port]
"""

import http.server
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8123


class NoCache(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

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
        print("sunucu:", "http://localhost:%d/web/explorer.html" % PORT)
        print("kok   :", ROOT)
        server.serve_forever()


if __name__ == "__main__":
    main()
