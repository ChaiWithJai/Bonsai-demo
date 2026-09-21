"""A+ error-discovery review server (stdlib only, local access only)."""
import json
import os
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
FILES = {"samples", "annotations", "patterns", "suggestions"}
MAX_BODY = 5_000_000


def ensure_data_files():
    for name in FILES:
        path = os.path.join(BASE, f"{name}.json")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump([], handle)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
            return super().do_GET()
        name = self.path.removeprefix("/api/")
        if self.path.startswith("/api/") and name in FILES:
            with open(os.path.join(BASE, f"{name}.json"), encoding="utf-8") as f:
                return self._json(json.load(f))
        return super().do_GET()

    def do_POST(self):
        name = self.path.removeprefix("/api/")
        if not (self.path.startswith("/api/") and name in FILES):
            return self._json({"error": "unknown"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            return self._json({"error": "payload too large"}, 413)
        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json({"error": "invalid JSON"}, 400)
        target = os.path.join(BASE, f"{name}.json")
        with tempfile.NamedTemporaryFile("w", dir=BASE, delete=False, encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
            temp_name = handle.name
        os.replace(temp_name, target)
        return self._json({"ok": True})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ensure_data_files()
    print("A+ review app on http://localhost:8377")
    ThreadingHTTPServer(("127.0.0.1", 8377), Handler).serve_forever()
