"""Fetch configured RSS/Atom URLs from public addresses, including redirects."""
import ipaddress
import socket

import httpx


def is_public(address):
    ip = ipaddress.ip_address(address)
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def checked_url(value, public=True):
    try:
        url = httpx.URL(value)
    except httpx.InvalidURL as error:
        raise ValueError("Enter a valid HTTP or HTTPS URL") from error
    if url.scheme not in {"http", "https"} or not url.host or url.userinfo:
        raise ValueError("Enter an HTTP or HTTPS URL without embedded credentials")
    if public:
        if url.port not in (None, 80 if url.scheme == "http" else 443):
            raise ValueError("RSS feeds must use the standard HTTP or HTTPS port")
        try:
            address = ipaddress.ip_address(url.host)
        except ValueError:
            if "." not in url.host.rstrip(".") or url.host.rstrip(".").lower().endswith((".localhost", ".local")):
                raise ValueError("RSS feeds must use a public hostname")
        else:
            if not is_public(address):
                raise ValueError("RSS feeds must use a public address")
    return url


def read_public_feed(client, value):
    url = checked_url(value)
    for _ in range(6):
        hostname = url.raw_host.decode("ascii")
        port = 443 if url.scheme == "https" else 80
        resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(entry[4][0] for entry in resolved))
        if not addresses or not all(is_public(address) for address in addresses):
            raise ValueError("RSS hostname resolves to a non-public address")
        for address in addresses:
            try:
                with client.stream(
                    "GET", url.copy_with(host=address), headers={"Host": url.netloc.decode("ascii")},
                    extensions={"sni_hostname": hostname}, follow_redirects=False,
                ) as response:
                    if response.has_redirect_location:
                        url = checked_url(str(url.join(response.headers["location"])))
                        break
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65_536):
                        body.extend(chunk)
                        if len(body) > 7_000_000:
                            raise ValueError("Feed larger than 7 MB")
                    return bytes(body)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if address == addresses[-1]:
                    raise
    raise ValueError("Too many RSS feed redirects")
