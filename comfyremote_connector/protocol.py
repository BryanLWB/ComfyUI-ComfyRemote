from __future__ import annotations

import ipaddress
import re
import time
from urllib.parse import parse_qs, urlsplit

CHUNK_BYTES = 4 * 1024 * 1024
MAX_BODY_BYTES = 512 * 1024 * 1024
ID = r"[a-zA-Z0-9_-]{1,100}"


def service_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    try:
        local = (
            parsed.hostname == "localhost"
            or ipaddress.ip_address(parsed.hostname or "").is_loopback
        )
    except ValueError:
        local = False
    if (
        parsed.scheme != "https" and not (local and parsed.scheme == "http")
    ) or not parsed.hostname:
        raise ValueError("Use an HTTPS service address (HTTP is allowed only on loopback)")
    if (
        parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Enter only the service origin without a path or credentials")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid service port")
    return value.strip().rstrip("/")


def validate_command(command: dict, state) -> None:
    path = command.get("path", "")
    parsed = urlsplit(path)
    method = command.get("method")
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not path.startswith("/")
        or "\\" in path
    ):
        raise ValueError("Invalid command path")
    if not re.fullmatch(r"[0-9a-f]{32}", command.get("id", "")):
        raise ValueError("Invalid command ID")
    if not isinstance(command.get("size"), int) or not 0 <= command["size"] <= MAX_BODY_BYTES:
        raise ValueError("Invalid command size")
    expires = command.get("expires")
    if not isinstance(expires, (int, float)) or not time.time() < expires <= time.time() + 86400:
        raise ValueError("Command expired or has an invalid deadline")
    if (
        method == "GET"
        and parsed.path in {"/system_stats", "/queue", "/object_info"}
        and not parsed.query
    ):
        return
    if (
        method == "POST"
        and parsed.path in {"/prompt", "/free", "/upload/image"}
        and not parsed.query
    ):
        return
    match = re.fullmatch(rf"/history/({ID})", parsed.path)
    if method == "GET" and match and not parsed.query and state.owns_prompt(match[1]):
        return
    if (
        method == "GET"
        and re.fullmatch(rf"/comfyremote-events/({ID})", parsed.path)
        and not parsed.query
    ):
        return
    match = re.fullmatch(rf"/api/jobs/({ID})/cancel", parsed.path)
    if method == "POST" and match and not parsed.query and state.owns_prompt(match[1]):
        return
    if method == "GET" and parsed.path == "/view":
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) <= {"filename", "subfolder", "type"} and all(
            len(v) == 1 for v in query.values()
        ):
            filename = query.get("filename", [""])[0]
            subfolder = query.get("subfolder", [""])[0]
            kind = query.get("type", ["output"])[0]
            if kind in {"output", "temp"} and state.owns_output(filename, subfolder, kind):
                return
    raise ValueError("Command is outside the paired device permissions")
