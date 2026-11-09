from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
import time
from pathlib import Path

# Global counter for request numbering
request_counter = 0

# Configurable output directory
DEBUG_DIR = Path("experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/data/guardian/gliner_debug").resolve()

class MockRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global request_counter
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))
        
        mode = payload.get("mode", "entities")
        
        # Save request to a unique file in debug dir
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        req_filename = f"req_{request_counter:03d}_{mode}.json"
        req_path = DEBUG_DIR / req_filename
        with req_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Mock Server: Saved request {request_counter} to {req_path}", file=sys.stderr)
        
        request_counter += 1

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {}
        
        # Check for mixed mode (both entities and relations in payload)
        if mode == "mixed" or ("entities" in payload and "relations" in payload):
             response = {
                "entities": [
                    {
                        "text": "Guardian Financial Services",
                        "label": "Organization",
                        "score": 0.98,
                        "start": 0,
                        "end": 27
                    },
                    {
                        "text": "Income Protection",
                        "label": "Product",
                        "score": 0.95,
                        "start": 20, # rough guess matching relations below
                        "end": 37
                    }
                ],
                "relation_extraction": [
                    {
                        "head": {"text": "Guardian Financial Services", "label": "Organization", "start": 0, "end": 27},
                        "tail": {"text": "Income Protection", "label": "Product", "start": 20, "end": 37},
                        "label": "OFFERS", 
                        "score": 0.92
                    }
                ]
            }
        elif mode == "relations":
            response = {
                "relation_extraction": [
                    {
                        "head": {"text": "Guardian", "label": "Organization", "start": 0, "end": 8},
                        "tail": {"text": "Income Protection", "label": "Product", "start": 20, "end": 37},
                        "label": "OFFERS", 
                        "score": 0.92
                    }
                ]
            }
        else:
            response = {
                "entities": [
                    {
                        "text": "Guardian Financial Services",
                        "label": "Organization",
                        "score": 0.98,
                        "start": 0,
                        "end": 27
                    }
                ]
            }
        
        # Save response
        resp_filename = f"resp_{request_counter-1:03d}_{mode}.json"
        resp_path = DEBUG_DIR / resp_filename
        with resp_path.open("w", encoding="utf-8") as f:
            json.dump(response, f, indent=2)
        print(f"Mock Server: Saved response to {resp_path}", file=sys.stderr)
            
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        return # Silence default logging

if __name__ == '__main__':
    port = 8999
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server_address = ('', port)
    httpd = HTTPServer(server_address, MockRequestHandler)
    print(f"Mock GLiNER server running on port {port}...")
    httpd.serve_forever()