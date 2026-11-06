import os
import http.server
import socketserver

PORT = int(os.environ.get("PORT", 8000))

class SafeHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

with socketserver.TCPServer(("", PORT), SafeHandler) as httpd:
    print(f"Serving Arch-Dome Landing Page at port {PORT}")
    httpd.serve_forever()
