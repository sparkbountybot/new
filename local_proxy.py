#!/usr/bin/env python3
"""
Local HTTP proxy that routes traffic through urllib with proxy bypass.
This runs on localhost and allows other processes to connect to it.
The proxy itself uses the same network namespace, but we'll try to
route through the host's gateway service.
"""
import http.server
import socket
import socketserver
import sys
import os
import json
import urllib.request
import urllib.error
import threading
import ssl
import time
import re
from urllib.parse import urlparse, urlunparse

PROXY_PORT = 8888


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP proxy handler."""
    
    def do_CONNECT(self):
        """Handle HTTPS CONNECT requests."""
        try:
            host, port = self.path.split(':')
            port = int(port)
            
            # Connect to target
            sock = socket.create_connection((host, port), timeout=30)
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            
            # Forward data both ways
            while True:
                client_data = self.request.recv(4096)
                if not client_data:
                    break
                sock.sendall(client_data)
                
                server_data = sock.recv(4096)
                if server_data:
                    self.wfile.write(server_data)
                    self.wfile.flush()
                    
        except Exception as e:
            self.wfile.write(f"HTTP/1.1 502 Bad Gateway\r\n\r\n".encode())
            self.wfile.flush()
            print(f"CONNECT error: {e}", file=sys.stderr)
        
        finally:
            try:
                self.request.close()
            except:
                pass

    def do_GET(self):
        """Handle HTTP GET requests."""
        try:
            # Parse the URL
            parsed = urlparse(self.path)
            if not parsed.hostname:
                # Assume it's just a path, try to construct URL
                self.path = f"http://{self.path}"
                parsed = urlparse(self.path)
            
            host = parsed.hostname
            port = parsed.port or 80
            path = parsed.path + ('?' + parsed.query if parsed.query else '')
            
            # Build request
            req = urllib.request.Request(
                f"http://{host}:{port}{path}",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            # Add any headers from the original request
            for header in ['Accept', 'Accept-Encoding', 'Accept-Language',
                          'Connection', 'Cache-Control']:
                val = self.headers.get(header)
                if val:
                    req.add_header(header, val)
            
            # Make the request
            response = urllib.request.urlopen(req, timeout=30)
            
            # Forward the response
            status = response.status
            self.send_response(status)
            
            for header, value in response.getheaders():
                if header.lower() not in ['transfer-encoding', 'connection']:
                    self.send_header(header, value)
            
            self.end_headers()
            
            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
            self.wfile.flush()
            
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode())
            self.wfile.flush()
            print(f"GET error: {e}", file=sys.stderr)

    def do_POST(self):
        """Handle HTTP POST requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''
        
        try:
            parsed = urlparse(self.path)
            if not parsed.hostname:
                self.path = f"http://{self.path}"
                parsed = urlparse(self.path)
            
            host = parsed.hostname
            port = parsed.port or 80
            path = parsed.path + ('?' + parsed.query if parsed.query else '')
            
            req = urllib.request.Request(
                f"http://{host}:{port}{path}",
                data=body,
                headers={**dict(self.headers), 'User-Agent': 'Mozilla/5.0'}
            )
            
            response = urllib.request.urlopen(req, timeout=30)
            
            self.send_response(response.status)
            for header, value in response.getheaders():
                if header.lower() not in ['transfer-encoding', 'connection']:
                    self.send_header(header, value)
            self.end_headers()
            self.wfile.write(response.read())
            self.wfile.flush()
            
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode())
            print(f"POST error: {e}", file=sys.stderr)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_proxy():
    """Start the proxy server."""
    server = socketserver.TCPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    server.allow_reuse_address = True
    print(f"Proxy server listening on 127.0.0.1:{PROXY_PORT}", file=sys.stderr)
    server.serve_forever()


if __name__ == '__main__':
    start_proxy()
