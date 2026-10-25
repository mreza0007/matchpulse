"""Bounded HTTPS transport: only configured feeds, pinned public DNS addresses."""
from dataclasses import dataclass
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

from news_sources import safe_url

MAX_BYTES = 1024 * 1024


@dataclass
class FeedResponse:
    status: int
    body: bytes = b""
    etag: str | None = None
    last_modified: str | None = None
    retry_after: int = 0


class PublicHTTPS(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Non-public feed address")
        family, kind, protocol, _, address = addresses[0]
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(self.timeout)
            sock.connect(address)
            self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def header_value(value):
    return value if isinstance(value, str) and len(value) <= 512 and not any(ord(c) < 32 for c in value) else None


def fetch_feed(source, etag=None, last_modified=None):
    url = source.feed_url
    deadline = time.monotonic() + 20
    for _ in range(4):
        url = safe_url(url, source.feed_hosts)
        parts = urlsplit(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Feed deadline")
        conn = PublicHTTPS(parts.hostname, timeout=min(5, remaining))
        try:
            headers = {"User-Agent": "MatchPulse-News/1", "Accept-Encoding": "identity"}
            for name, value in (("If-None-Match", etag), ("If-Modified-Since", last_modified)):
                if header_value(value):
                    headers[name] = value
            conn.request("GET", parts.path + ("?" + parts.query if parts.query else ""), headers=headers)
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader("Location", ""))
                continue
            result = FeedResponse(response.status, etag=header_value(response.getheader("ETag")),
                                  last_modified=header_value(response.getheader("Last-Modified")))
            retry = response.getheader("Retry-After", "")
            result.retry_after = min(int(retry), 21600) if retry.isascii() and retry.isdigit() else 0
            if response.status != 200:
                return result
            mime = response.getheader("Content-Type", "").split(";")[0].strip().lower()
            accepted = {"application/json", "application/feed+json"} if source.format == "json" else {
                "application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}
            if mime not in accepted or response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Unsupported feed encoding/type")
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Feed deadline")
                if conn.sock:
                    conn.sock.settimeout(min(5, remaining))
                chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Feed too large")
            result.body = b"".join(chunks)
            return result
        finally:
            conn.close()
    raise ValueError("Too many feed redirects")
