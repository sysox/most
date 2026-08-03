"""Conservative endpoint classification; unknown is never considered private."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from .adapters import Connectivity


@dataclass(frozen=True, slots=True)
class NetworkInspector:
    def inspect(self, endpoint: str, declared_location: str = "remote-public", declared_network: str | None = None) -> Connectivity:
        parsed = urlparse(endpoint)
        host = parsed.hostname
        if not host:
            return Connectivity(endpoint, "unknown", None, "UNKNOWN", ("endpoint has no host",))
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        except (OSError, ValueError):
            return Connectivity(endpoint, "unknown", None, "UNKNOWN", ("DNS or route inspection unavailable",))
        if any(address.is_loopback for address in addresses):
            return Connectivity(endpoint, "local", "localhost", "INFERRED", tuple(str(a) for a in addresses))
        if all(address.is_private for address in addresses):
            return Connectivity(endpoint, "remote-private", "local-network", "INFERRED", tuple(str(a) for a in addresses))
        if any(address.is_global for address in addresses):
            return Connectivity(endpoint, declared_location, declared_network or "public-internet", "INFERRED", tuple(str(a) for a in addresses))
        return Connectivity(endpoint, "unknown", None, "UNKNOWN", tuple(str(a) for a in addresses))
