from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from .models import Target


class ScopeError(ValueError):
    pass


BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
BLOCKED_IPS = {
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
}


def host_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ScopeError("target URL must use http or https")
    if not parsed.hostname:
        raise ScopeError("target URL must include a hostname")
    return parsed.hostname.lower()


def validate_target_scope(target: Target) -> None:
    host = host_from_url(target.url)
    if host in BLOCKED_HOSTS and not target.allow_private_networks:
        raise ScopeError(f"blocked local/control-plane host: {host}")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip and not target.allow_private_networks:
        if any(ip in network for network in BLOCKED_IPS) or ip.is_private:
            raise ScopeError(f"blocked private or unsafe target IP: {ip}")

    for excluded in target.excludes:
        if excluded and excluded in target.url:
            raise ScopeError(f"target URL matches excluded scope: {excluded}")

