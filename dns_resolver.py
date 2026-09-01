"""
Pure Python DNS resolver using raw UDP.
Bypasses system resolver by sending UDP queries directly.
"""
import socket
import struct
import time
import threading
import sys


class DnsResolver:
    """Resolve DNS names using raw UDP to external DNS servers."""
    
    def __init__(self, dns_servers=None):
        self.dns_servers = dns_servers or [
            ('8.8.8.8', 53),
            ('1.1.1.1', 53),
            ('9.9.9.9', 53),
            ('208.67.222.222', 53),  # OpenDNS
        ]
        self.cache = {}
        self.cache_ttl = 60  # seconds
    
    def _build_query(self, domain, qtype=1):
        """Build a DNS query packet."""
        # Transaction ID
        txid = b'\x00\x01'
        
        # Flags: standard query with recursion desired
        flags = b'\x01\x00'
        
        # QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT
        counts = struct.pack('HHHH', 1, 0, 0, 0)
        
        # Question section
        # Encode domain name in DNS format
        question = b''
        for part in domain.split('.'):
            question += bytes([len(part)]) + part.encode()
        question += b'\x00'  # Null terminator
        
        # QTYPE (A record = 1) and QCLASS (IN = 1)
        question += struct.pack('HH', qtype, 1)
        
        return txid + flags + counts + question
    
    def _parse_response(self, data):
        """Parse DNS response and extract A records."""
        if len(data) < 12:
            return None
        
        # Flags
        flags = struct.unpack('H', data[2:4])[0]
        rcode = flags & 0xF
        
        if rcode != 0:
            return None
        
        # Question count
        qdcount = struct.unpack('H', data[4:6])[0]
        
        # Answer count
        ancount = struct.unpack('H', data[6:8])[0]
        
        # Skip question section
        offset = 12
        for i in range(qdcount):
            while offset < len(data):
                length = data[offset]
                if length == 0:
                    offset += 1
                    break
                offset += length + 1
            offset += 4  # QTYPE + QCLASS
        
        # Parse answers
        results = []
        for i in range(ancount):
            if offset >= len(data):
                break
            
            # Read answer name (may use pointer compression)
            if data[offset] & 0xC0 == 0xC0:
                pointer = struct.unpack('!H', data[offset:offset+2])[0] & 0x3FFF
                offset += 2
                # Follow pointer - but we need to save position first
                name = self._decode_name(data, pointer)
            else:
                name = self._decode_name(data, offset)
                offset += len(name) + 1
            
            if offset + 10 > len(data):
                break
            
            # Type, Class, TTL, RDLENGTH
            rtype, rclass, ttl, rdlength = struct.unpack('HHIH', data[offset:offset+10])
            offset += 10
            
            # A record
            if rtype == 1 and rdlength == 4:
                ip = '.'.join(str(b) for b in data[offset:offset+4])
                offset += rdlength
                results.append((name, ip, ttl))
            else:
                offset += rdlength
        
        return results
    
    def _decode_name(self, data, offset):
        """Decode a DNS domain name, handling pointer compression."""
        labels = []
        visited = set()
        
        while offset < len(data):
            if data[offset] & 0xC0 == 0xC0:
                pointer = struct.unpack('!H', data[offset:offset+2])[0] & 0x3FFF
                if pointer in visited:
                    break  # Prevent loops
                visited.add(pointer)
                offset = pointer
            else:
                length = data[offset]
                offset += 1
                labels.append(data[offset:offset+length].decode())
                offset += length
        
        return '.'.join(labels)
    
    def resolve(self, domain, timeout=5):
        """Resolve a domain name to IP address."""
        # Check cache
        if domain in self.cache:
            ip, timestamp = self.cache[domain]
            if time.time() - timestamp < self.cache_ttl:
                return ip
        
        # Try each DNS server
        for dns_ip, dns_port in self.dns_servers:
            try:
                # Create raw UDP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                
                # Build and send query
                query = self._build_query(domain)
                sock.sendto(query, (dns_ip, dns_port))
                
                # Receive response
                response, _ = sock.recvfrom(4096)
                sock.close()
                
                # Parse response
                results = self._parse_response(response)
                if results:
                    ip = results[0][1]
                    self.cache[domain] = (ip, time.time())
                    return ip
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f'DNS error: {dns_ip}: {e}', file=sys.stderr)
        
        return None


def patch_socket_dns():
    """Patch socket.getaddrinfo to use our DNS resolver."""
    original_getaddrinfo = socket.getaddrinfo
    resolver = DnsResolver()
    
    def patched_getaddrinfo(host, port=None, family=0, type=0, proto=0, flags=0):
        # If host is already an IP, use original
        if host and host.lstrip('.').replace('.', '').isdigit():
            return original_getaddrinfo(host, port, family, type, proto, flags)
        
        # Resolve hostname using our resolver
        if host:
            ip = resolver.resolve(host)
            if ip:
                # Replace hostname with IP for resolution
                try:
                    results = original_getaddrinfo(
                        ip, port, family, type, proto, flags
                    )
                    return results
                except:
                    return [(family, type, proto, '', (ip, port))]
        
        # Fall back to original
        try:
            return original_getaddrinfo(host, port, family, type, proto, flags)
        except:
            raise
    
    socket.getaddrinfo = patched_getaddrinfo
    return resolver


if __name__ == '__main__':
    resolver = DnsResolver()
    
    domains = ['github.com', 'paper-api.alpaca.markets', 'api.alpaca.markets', 
               'example.com', 'google.com']
    
    print('Resolving DNS with pure Python resolver:')
    for domain in domains:
        ip = resolver.resolve(domain)
        status = 'OK' if ip else 'FAILED'
        print(f'  {domain:30s} -> {ip or "N/A":15s} [{status}]')
