from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from collections import deque
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import quote

import aiohttp

from .protocol import CHUNK_BYTES, MAX_BODY_BYTES, service_origin, validate_command
from .state import State
from .workflow import minimal_info, validate_workflow

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, root: Path, local_origin: str):
        self.state = State(root)
        self.local_origin = local_origin
        self.error = ""
        try:
            self.pairing = self.state.load_pairing()
        except (OSError, ValueError):
            self.pairing = None
            self.error = "Saved credential cannot be opened. Revoke the old device and pair again."
        self.task: asyncio.Task | None = None
        self.online = False
        self.last_import: dict | None = None
        self.session: aiohttp.ClientSession | None = None
        self.mutation = asyncio.Lock()
        self.progress = {}
        self.progress_tasks = {}

    async def start(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=150), trust_env=False
        )
        self.task = asyncio.create_task(self.run(), name="comfyremote-connector")

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for task in self.progress_tasks.values():
            task.cancel()
        await asyncio.gather(*self.progress_tasks.values(), return_exceptions=True)
        if self.session:
            await self.session.close()

    def status(self) -> dict:
        return {
            "paired": bool(self.pairing),
            "online": self.online,
            "error": self.error,
            "service": self.pairing["origin"] if self.pairing else "",
            "last_import": self.last_import,
        }

    async def remote(self, method: str, path: str, **kwargs):
        if not self.pairing or not self.session:
            raise ValueError("Pair the device first")
        return await self.session.request(
            method,
            self.pairing["origin"] + "/api/connector" + path,
            headers={"Authorization": "Bearer " + self.pairing["token"]},
            allow_redirects=False,
            **kwargs,
        )

    async def pair(self, origin: str, code: str, name: str):
        async with self.mutation:
            if self.pairing:
                raise ValueError("Unpair the existing service before connecting another")
            origin = service_origin(origin)
            async with self.session.post(
                origin + "/api/connector/pair",
                json={"code": code.strip().upper(), "name": name[:80], "protocol": 1},
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        "Pairing failed. Check the service address and generate a new code."
                    )
                value = await response.json()
            if value.get("protocol") != 1 or not isinstance(value.get("token"), str):
                raise ValueError("The service uses an unsupported connector protocol")
            value["origin"] = origin
            self.state.save_pairing(value)
            self.pairing = value
            self.error = ""

    async def unpair(self):
        async with self.mutation:
            if self.pairing:
                async with await self.remote("DELETE", "/pair") as response:
                    if response.status not in {204, 401}:
                        raise ValueError("Revocation failed. Retry when the service is reachable.")
            self.pairing = None
            self.online = False
            self.state.clear_pairing()

    async def node_info(self, names: list[str]) -> dict:
        result = {}
        for name in names:
            async with self.session.get(
                self.local_origin + "/object_info/" + quote(name, safe="")
            ) as response:
                response.raise_for_status()
                value = await response.json()
            if name not in value:
                raise ValueError(f"Missing node: {name}")
            result[name] = value[name]
        return result

    async def send_workflow(self, body: dict) -> dict:
        graph = body.get("prompt")
        name = body.get("name", "").strip()
        if not name or len(name) > 200 or not isinstance(graph, dict) or not graph:
            raise ValueError("A named executable workflow is required")
        validate_workflow(graph)
        classes = sorted({node["class_type"] for node in graph.values()})
        info = minimal_info(graph, await self.node_info(classes))
        # This action is the boundary for exposing definitions of the selected graph.
        self.state.add_classes(classes)
        self.state.remember_references(graph)
        payload = {"protocol": 1, "name": name, "prompt": graph, "object_info": info}
        if len(json.dumps(payload).encode()) > 10 * 1024 * 1024:
            raise ValueError("Workflow exceeds the 10 MB import limit")
        async with await self.remote("POST", "/workflows", json=payload) as response:
            value = await response.json()
            if response.status not in {200, 201}:
                raise ValueError(value.get("detail", {}).get("message", "Workflow import failed"))
        self.last_import = value
        return value

    async def run(self):
        delay = 1.0
        while True:
            if not self.pairing:
                await asyncio.sleep(1)
                continue
            try:
                pairing = self.pairing
                async with await self.remote("GET", "/poll") as response:
                    if self.pairing is not pairing:
                        continue
                    if response.status == 401:
                        self.pairing = None
                        self.state.clear_pairing()
                        raise ValueError("Device was revoked. Pair again to reconnect.")
                    response.raise_for_status()
                    command = await response.json()
                self.online = True
                self.error = ""
                delay = 1
                if command:
                    async with self.mutation:
                        if self.pairing is pairing:
                            await self.execute(command)
            except asyncio.CancelledError:
                raise
            except (
                aiohttp.ClientError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                TimeoutError,
            ) as exc:
                self.online = False
                self.error = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "Connection interrupted. Reconnecting."
                )
                logger.warning("Connector retry: %s", type(exc).__name__)
                await asyncio.sleep(delay + random.random())
                delay = min(delay * 2, 30)

    async def execute(self, command: dict):
        validate_command(command, self.state)
        command_id = command["id"]
        with self.state.db() as db:
            db.execute("DELETE FROM receipts WHERE received<?", (time.time() - 86400,))
            inserted = db.execute(
                "INSERT OR IGNORE INTO receipts VALUES (?,?)", (command_id, time.time())
            )
            if inserted.rowcount != 1:
                return
        request_path = self.state.root / f"{command_id}.request"
        response_path = self.state.root / f"{command_id}.response"
        try:
            with request_path.open("wb") as stream:
                for offset in range(0, command["size"], CHUNK_BYTES):
                    async with await self.remote(
                        "GET", f"/commands/{command_id}/body?offset={offset}"
                    ) as response:
                        response.raise_for_status()
                        chunk = await response.read()
                        if len(chunk) != min(CHUNK_BYTES, command["size"] - offset):
                            raise ValueError("Invalid request chunk")
                        stream.write(chunk)
            try:
                status, content_type = await self.local_request(
                    command, request_path, response_path
                )
            except (ValueError, KeyError, TypeError) as exc:
                response_path.write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
                status, content_type = 422, "application/json"
            with response_path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
                stream.seek(0)
                offset = 0
                while chunk := stream.read(CHUNK_BYTES):
                    async with await self.remote(
                        "PUT", f"/commands/{command_id}/body?offset={offset}", data=chunk
                    ) as response:
                        response.raise_for_status()
                    offset += len(chunk)
            async with await self.remote(
                "POST",
                f"/commands/{command_id}/complete",
                json={
                    "status": status,
                    "content_type": content_type,
                    "size": offset,
                    "sha256": digest,
                },
            ) as response:
                response.raise_for_status()
        finally:
            request_path.unlink(missing_ok=True)
            response_path.unlink(missing_ok=True)

    async def local_request(self, command: dict, source: Path, target: Path) -> tuple[int, str]:
        path = command["path"]
        if path == "/upload/image":
            raw = (
                b"Content-Type: "
                + command["content_type"].encode("ascii")
                + b"\r\nMIME-Version: 1.0\r\n\r\n"
                + source.read_bytes()
            )
            message = BytesParser(policy=policy.default).parsebytes(raw)
            fields = {}
            images = 0
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name == "image":
                    filename = part.get_filename() or ""
                    if (
                        not filename
                        or any(c in filename for c in "/\\:")
                        or filename in {".", ".."}
                    ):
                        raise ValueError("Invalid upload filename")
                    images += 1
                elif name in {"subfolder", "type", "overwrite"}:
                    if name in fields:
                        raise ValueError("Duplicate upload field")
                    fields[name] = part.get_payload(decode=True).decode("utf-8")
                else:
                    raise ValueError("Unsupported upload field")
            subfolder = fields.get("subfolder", "").replace("\\", "/")
            if (
                images != 1
                or fields.get("type") != "input"
                or not subfolder.startswith("ComfyRemote/")
                or any(part in {"", ".", ".."} for part in subfolder.split("/"))
                or ":" in subfolder
            ):
                raise ValueError("Uploads must stay inside the ComfyRemote input directory")
        if path.startswith("/comfyremote-events/"):
            client_id = path.rsplit("/", 1)[-1]
            queue = self.progress.get(client_id, [])
            value = list(queue)
            queue.clear()
            target.write_text(json.dumps(value), encoding="utf-8")
            return 200, "application/json"
        if path == "/object_info":
            value = minimal_info(
                self.state.reference_graph(), await self.node_info(self.state.classes())
            )
            target.write_text(json.dumps(value), encoding="utf-8")
            return 200, "application/json"
        if path == "/prompt":
            body = json.loads(source.read_bytes())
            graph = body.get("prompt", {})
            validate_workflow(graph)
            if not {node["class_type"] for node in graph.values()} <= set(self.state.classes()):
                raise ValueError("Send this workflow from ComfyUI before running it remotely")
            client_id = body.get("client_id", "")
            if not isinstance(client_id, str) or len(client_id) > 100:
                raise ValueError("Invalid client identifier")
            for key, task in list(self.progress_tasks.items()):
                if task.done():
                    del self.progress_tasks[key]
                    self.progress.pop(key, None)
            ready = asyncio.Event()
            self.progress[client_id] = deque(maxlen=200)
            self.progress_tasks[client_id] = asyncio.create_task(
                self.watch_progress(client_id, ready)
            )
            await asyncio.wait_for(ready.wait(), timeout=12)
        with source.open("rb") as stream:
            async with self.session.request(
                command["method"],
                self.local_origin + path,
                data=stream if command["size"] else None,
                headers={"Content-Type": command["content_type"] or "application/json"},
                allow_redirects=False,
            ) as response:
                count = 0
                with target.open("wb") as output:
                    async for chunk in response.content.iter_chunked(CHUNK_BYTES):
                        count += len(chunk)
                        if count > MAX_BODY_BYTES:
                            raise ValueError("ComfyUI output exceeds the transfer limit")
                        output.write(chunk)
                status = response.status
                content_type = response.headers.get("Content-Type", "application/octet-stream")
        if path == "/prompt" and status == 200:
            value = json.loads(target.read_bytes())
            if value.get("prompt_id"):
                with self.state.db() as db:
                    db.execute("INSERT OR IGNORE INTO prompts VALUES (?)", (value["prompt_id"],))
        if path.startswith("/history/") and status == 200:
            self.state.own_history_outputs(json.loads(target.read_bytes()))
        if path == "/queue" and status == 200:
            value = json.loads(target.read_bytes())
            target.write_text(
                json.dumps(
                    {
                        key: [row[:2] for row in value.get(key, [])]
                        for key in ("queue_running", "queue_pending")
                    }
                ),
                encoding="utf-8",
            )
        return status, content_type

    async def watch_progress(self, client_id, ready):
        try:
            async with self.session.ws_connect(
                self.local_origin + "/ws?clientId=" + quote(client_id, safe=""), heartbeat=20
            ) as socket:
                ready.set()
                async with asyncio.timeout(7200):
                    async for message in socket:
                        if message.type != aiohttp.WSMsgType.TEXT:
                            continue
                        value = json.loads(message.data)
                        if value.get("type") in {
                            "execution_start",
                            "executing",
                            "progress",
                            "execution_success",
                            "execution_error",
                            "execution_interrupted",
                        }:
                            self.progress[client_id].append(value)
                        if value.get("type") in {
                            "execution_success",
                            "execution_error",
                            "execution_interrupted",
                        }:
                            return
        except (aiohttp.ClientError, ValueError, TimeoutError):
            ready.set()
