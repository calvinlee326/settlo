from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        print(self.rfile.read(length).decode(), flush=True)
        self.send_response(204)
        self.end_headers()


HTTPServer(("127.0.0.1", 9000), Handler).serve_forever()
