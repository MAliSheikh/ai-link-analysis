"""URL validation and SSRF (Server-Side Request Forgery) protection.

SSRF = an attacker sends a URL like http://127.0.0.1 or http://169.254.169.254
so OUR server visits its own private/internal network. We block that.
"""
import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidURLError(AppError):
    status_code = 400
    code = "invalid_url"


class BlockedURLError(AppError):
    status_code = 400
    code = "blocked_url"


class WebsiteFetchError(AppError):
    status_code = 502
    code = "website_unreachable"


class ContentExtractionError(AppError):
    status_code = 422
    code = "not_enough_content"

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {None, 80, 443}
BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata"}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")
HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}$")


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def is_public_ip(ip_str: str) -> bool:
    """True only for normal public internet addresses."""
    try:
        ip = ipaddress.ip_address(ip_str.split("%")[0])  # remove IPv6 zone id like %eth0
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:  # ::ffff:127.0.0.1 tricks
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def normalize_url(raw: str) -> str:
    """Check the URL shape (no network call) and return a clean version."""
    if raw is None or not str(raw).strip():
        raise InvalidURLError("URL (Uniform Resource Locator) is empty.")
    url = str(raw).strip()
    if len(url) > MAX_URL_LENGTH:
        raise InvalidURLError("URL is too long.")
    if "://" not in url:
        url = "https://" + url

    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError("Only http and https URLs are allowed.")
    if parts.username or parts.password:
        raise InvalidURLError("URLs with a username or password are not allowed.")

    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise InvalidURLError("URL must contain a domain name, for example https://example.com")
    if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_SUFFIXES):
        raise BlockedURLError("Local or internal addresses are not allowed (SSRF protection).")

    if not _is_ip(host):
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise InvalidURLError("Domain name is not valid.")
        if not HOSTNAME_RE.match(ascii_host):
            raise InvalidURLError("Domain name is not valid, for example use https://example.com")
        host = ascii_host

    try:
        port = parts.port
    except ValueError:
        raise InvalidURLError("Port number in the URL is not valid.")
    if port not in ALLOWED_PORTS:
        raise BlockedURLError("Only standard web ports 80 and 443 are allowed.")

    netloc = f"[{host}]" if ":" in host else host
    if port:
        netloc += f":{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def resolve_and_check_host(host: str) -> list:
    """DNS (Domain Name System) lookup, then make sure EVERY address is public."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        raise InvalidURLError(f"Domain '{host}' could not be found (DNS lookup failed).")
    ips = {info[4][0] for info in infos}
    if not ips:
        raise InvalidURLError(f"Domain '{host}' has no IP (Internet Protocol) address.")
    for ip in ips:
        if not is_public_ip(ip):
            raise BlockedURLError(
                "This URL points to a private or internal network address. "
                "It is blocked for security (SSRF protection)."
            )
    return sorted(ips)


def validate_public_url(raw: str) -> str:
    url = normalize_url(raw)
    resolve_and_check_host(urlsplit(url).hostname)
    return url


async def validate_public_url_async(raw: str) -> str:
    # DNS lookup is blocking, so run it in a thread.
    return await asyncio.to_thread(validate_public_url, raw)
