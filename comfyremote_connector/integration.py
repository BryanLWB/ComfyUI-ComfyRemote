from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web

from .runtime import Runtime


def local_request(request: web.Request) -> bool:
    try:
        remote = ipaddress.ip_address(request.remote or "")
        host = urlsplit("http://" + request.host).hostname
        local_host = host == "localhost" or ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False
    if not remote.is_loopback or not local_host:
        return False
    if request.method not in {"GET", "HEAD"}:
        origin = urlsplit(request.headers.get("Origin", ""))
        return (
            origin.scheme in {"http", "https"}
            and origin.netloc == request.host
            and request.headers.get("X-ComfyRemote") == "1"
        )
    return True


def install():
    import folder_paths
    from comfy.cli_args import args
    from server import PromptServer

    server = PromptServer.instance
    if "comfyremote_connector" in server.app:
        return
    runtime = Runtime(
        Path(folder_paths.get_user_directory()) / "comfyremote-connector",
        f"http://127.0.0.1:{args.port}",
    )
    installations = []
    for directory in folder_paths.get_folder_paths("custom_nodes"):
        for child in Path(directory).iterdir():
            if (child / "comfyremote_connector" / "integration.py").is_file():
                installations.append(str(child))
    runtime.duplicate_installations = installations if len(installations) > 1 else []
    server.app["comfyremote_connector"] = runtime

    async def startup(app):
        await runtime.start()

    async def cleanup(app):
        await runtime.close()

    server.app.on_startup.append(startup)
    server.app.on_cleanup.append(cleanup)

    async def handler(request):
        if not local_request(request):
            raise web.HTTPForbidden()
        action = request.match_info["action"]
        try:
            user = server.user_manager.get_request_user_id(request)
            if request.method == "GET" and action == "targets":
                value = await runtime.workflow_targets(user, request.query.get("source", ""))
            elif request.method == "GET" and action == "status":
                value = runtime.status()
            elif request.method == "POST" and action in {"pair", "unpair", "workflow", "preview", "retry"}:
                if request.content_length is None or request.content_length > 10 * 1024 * 1024:
                    raise web.HTTPRequestEntityTooLarge(
                        max_size=10 * 1024 * 1024, actual_size=request.content_length or 0
                    )
                body = await request.json()
                if action == "pair":
                    await runtime.pair(body["origin"], body["code"], body.get("name", "ComfyUI"))
                    value = runtime.status()
                elif action == "unpair":
                    await runtime.unpair()
                    value = runtime.status()
                elif action == "retry":
                    value = await runtime.retry_workflow(body["request_id"], user)
                else:
                    value = await runtime.send_workflow(body, user=user, preview=action == "preview")
            else:
                raise web.HTTPNotFound()
        except (ValueError, KeyError, TypeError) as exc:
            return web.json_response(
                {"error": str(exc)}, status=400, headers={"Cache-Control": "no-store"}
            )
        return web.json_response(value, headers={"Cache-Control": "no-store"})

    server.routes.get("/comfyremote/{action}")(handler)
    server.routes.post("/comfyremote/{action}")(handler)
