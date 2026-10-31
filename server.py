import os
from http.server import SimpleHTTPRequestHandler, HTTPServer

class StaticHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # تفعيل التخزين المؤقت وحماية الرؤوس
        self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

def run():
    port = int(os.environ.get("PORT", 8080))
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, StaticHandler)
    print(f"🚀 Arch-Dome Landing Server is running on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()