"""Outbound hosted transport. The local journal never retries an uncertain prompt POST."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

import aiohttp

from .workflow import minimal_info, validate_workflow


class Hosted:
    def __init__(self, runtime):
        self.runtime = runtime
        self.tasks: dict[str, asyncio.Task] = {}
        self.cancelled: set[str] = set()
        with runtime.state.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS hosted_jobs(
                id TEXT PRIMARY KEY, phase TEXT NOT NULL, prompt_id TEXT,
                history TEXT, updated REAL NOT NULL)""")

    def record(self, job_id):
        with self.runtime.state.db() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM hosted_jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def save(self, job_id, phase, prompt_id=None, history=None):
        with self.runtime.state.db() as db:
            db.execute(
                """INSERT INTO hosted_jobs VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                   phase=excluded.phase,prompt_id=COALESCE(excluded.prompt_id,prompt_id),
                   history=COALESCE(excluded.history,history),updated=excluded.updated""",
                (
                    job_id,
                    phase,
                    prompt_id,
                    json.dumps(history) if history is not None else None,
                    time.time(),
                ),
            )

    async def api(self, method, path, **kwargs):
        async with await self.runtime.remote(method, path, **kwargs) as response:
            value = await response.json() if response.content_type == "application/json" else {}
            if response.status >= 400:
                raise ValueError(value.get("error", {}).get("message", "Hosted request failed"))
            return value

    async def local(self, method, path, **kwargs):
        async with self.runtime.session.request(
            method, self.runtime.local_origin + path, allow_redirects=False, **kwargs
        ) as response:
            value = await response.json() if response.content_type == "application/json" else {}
            if response.status >= 400:
                raise ValueError("ComfyUI rejected the task. Check the workflow and missing nodes.")
            return value

    async def connect(self):
        pairing = self.runtime.pairing
        async with self.runtime.session.ws_connect(
            pairing["origin"] + "/api/connector/socket",
            headers={"Authorization": "Bearer " + pairing["token"]},
            max_msg_size=4096,
        ) as socket:
            self.runtime.online = True
            self.runtime.error = ""
            heartbeat = asyncio.create_task(self.heartbeat(socket))
            try:
                async for message in socket:
                    if self.runtime.pairing is not pairing:
                        break
                    if message.type != aiohttp.WSMsgType.TEXT:
                        continue
                    value = json.loads(message.data)
                    if value.get("type") == "inspect_workflow":
                        inspection_id = str(uuid.UUID(value["id"]))
                        if inspection_id not in self.tasks or self.tasks[inspection_id].done():
                            self.tasks[inspection_id] = asyncio.create_task(
                                self.inspect_workflow(inspection_id)
                            )
                    if value.get("type") == "refresh_status":
                        await self.send_telemetry(socket)
                    if value.get("type") in {"run", "cancel", "retry_upload"}:
                        job_id = str(uuid.UUID(value["id"]))
                        if value["type"] == "cancel":
                            self.cancelled.add(job_id)
                        if job_id not in self.tasks or self.tasks[job_id].done():
                            self.tasks[job_id] = asyncio.create_task(
                                self.run_job(job_id, value["type"] == "retry_upload")
                            )
            finally:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
                self.runtime.online = False
                if socket.close_code == 4001:
                    raise ValueError("Device was revoked. Unpair locally and reconnect.")

    async def heartbeat(self, socket):
        while True:
            await self.send_telemetry(socket)
            await asyncio.sleep(60)

    async def inspect_workflow(self, inspection_id):
        path = f"/inspections/{inspection_id}"
        try:
            value = await self.api("GET", path)
            graph = value["graph"]
            validate_workflow(graph)
            classes = sorted({node["class_type"] for node in graph.values()})
            info = await asyncio.wait_for(self.runtime.node_info(classes), timeout=20)
            payload = {"info": minimal_info(graph, info)}
            if len(json.dumps(payload).encode()) > 10 * 1024 * 1024:
                raise ValueError("Selected workflow metadata exceeds the import limit")
            await self.api("POST", path, json=payload)
            self.runtime.state.add_classes(classes)
            self.runtime.state.remember_references(graph)
        except (aiohttp.ClientError, OSError, ValueError, TypeError, KeyError, TimeoutError):
            try:
                await self.api(
                    "POST",
                    path,
                    json={"error": "无法读取所选工作流的节点定义，请检查缺失节点并重试。"},
                )
            except (aiohttp.ClientError, OSError, ValueError, TimeoutError):
                pass

    async def send_telemetry(self, socket):
        snapshot = None
        try:
            stats, queue = await asyncio.gather(
                self.local("GET", "/system_stats", timeout=aiohttp.ClientTimeout(total=5)),
                self.local("GET", "/queue", timeout=aiohttp.ClientTimeout(total=5)),
            )
            device = next((d for d in stats.get("devices", []) if d.get("type") != "cpu"), None)
            gpu = None
            if device and device.get("vram_total", 0) > 0:
                total = int(device["vram_total"])
                gpu = {
                    "name": str(device.get("name", "GPU"))[:160],
                    "vram_total": total,
                    "vram_free": max(0, min(total, int(device.get("vram_free", 0)))),
                }
            snapshot = {
                "gpu": gpu,
                "queue": {
                    "comfy_running": len(queue.get("queue_running", [])),
                    "comfy_pending": len(queue.get("queue_pending", [])),
                },
            }
        except (aiohttp.ClientError, OSError, ValueError, TypeError, AttributeError, TimeoutError):
            pass
        # Only aggregate hardware/queue statistics leave the computer.
        await socket.send_json({"type": "ping", "telemetry": snapshot})

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    async def status(self, job_id, status, **kwargs):
        return await self.api("POST", f"/jobs/{job_id}/status", json={"status": status, **kwargs})

    async def recover(self, job_id):
        queue = await self.local("GET", "/queue")
        for row in queue.get("queue_running", []) + queue.get("queue_pending", []):
            if len(row) > 3 and row[3].get("comfyremote_hosted_job") == job_id:
                return row[1]
        history = await self.local("GET", "/history?max_items=1000")
        for prompt_id, entry in history.items():
            prompt = entry.get("prompt", [])
            if len(prompt) > 3 and prompt[3].get("comfyremote_hosted_job") == job_id:
                return prompt_id
        return None

    async def resolve_inputs(self, graph):
        uploaded = {}
        for node in graph.values():
            for name, value in node["inputs"].items():
                if not isinstance(value, dict) or "comfyremote_assets" not in value:
                    continue
                refs = []
                for ref in value["comfyremote_assets"]:
                    asset_id = ref["asset_id"]
                    if asset_id not in uploaded:
                        temp = self.runtime.state.root / f"{asset_id}.hosted-input"
                        try:
                            async with await self.runtime.remote(
                                "GET", f"/assets/{asset_id}/content"
                            ) as response:
                                response.raise_for_status()
                                size = 0
                                with temp.open("wb") as output:
                                    async for chunk in response.content.iter_chunked(1024 * 1024):
                                        size += len(chunk)
                                        if size > 500000000:
                                            raise ValueError(
                                                "Input exceeds the hosted transfer limit"
                                            )
                                        output.write(chunk)
                            extension = Path(ref["name"]).suffix
                            with temp.open("rb") as stream:
                                form = aiohttp.FormData()
                                form.add_field(
                                    "image",
                                    stream,
                                    filename=asset_id + extension,
                                    content_type=ref["mime"],
                                )
                                form.add_field("type", "input")
                                form.add_field("subfolder", "ComfyRemote/hosted")
                                form.add_field("overwrite", "false")
                                result = await self.local("POST", "/upload/image", data=form)
                            uploaded[asset_id] = result.get("subfolder", "") + "/" + result["name"]
                        finally:
                            temp.unlink(missing_ok=True)
                    refs.append({"file": uploaded[asset_id], "kind": ref["mime"].split("/")[0]})
                node["inputs"][name] = (
                    json.dumps(refs, ensure_ascii=False)
                    if value.get("serialization") == "media_manifest_json"
                    else refs[0]["file"]
                )

    async def run_job(self, job_id, retry_upload=False):
        try:
            job = await self.api("GET", f"/jobs/{job_id}")
            record = self.record(job_id)
            if record and record["phase"] == "complete" and not retry_upload:
                await self.status(job_id, "succeeded", transfer_status="complete")
                return
            if record and record["phase"] in {"failed", "cancelled", "uncertain"}:
                await self.status(job_id, record["phase"])
                return
            if record and record["history"]:
                if retry_upload or record["phase"] != "upload_failed":
                    await self.upload_outputs(job, json.loads(record["history"]))
                return
            if job["status"] not in {"queued", "submitted", "running"}:
                return
            prompt_id = (record or {}).get("prompt_id") or job.get("prompt_id")
            if not prompt_id and record:
                prompt_id = await self.recover(job_id)
                if not prompt_id:
                    self.save(job_id, "uncertain")
                    await self.status(
                        job_id,
                        "uncertain",
                        error="本机提交结果需要人工核对，为防止重复生成已停止自动重试。",
                    )
                    return
            if not prompt_id:
                if job.get("cancel_requested") or job_id in self.cancelled:
                    self.save(job_id, "cancelled")
                    await self.status(job_id, "cancelled")
                    return
                graph = job["graph"]
                validate_workflow(graph)
                if not {node["class_type"] for node in graph.values()} <= set(
                    self.runtime.state.classes()
                ):
                    raise ValueError("Send this workflow from ComfyUI before running it remotely")
                await self.resolve_inputs(graph)
                self.save(job_id, "submitting")
                result = await self.local(
                    "POST",
                    "/prompt",
                    json={
                        "prompt": graph,
                        "client_id": "comfyremote-" + job_id,
                        "extra_data": {"comfyremote_hosted_job": job_id},
                    },
                )
                prompt_id = result["prompt_id"]
            self.save(job_id, "submitted", prompt_id)
            with self.runtime.state.db() as db:
                db.execute("INSERT OR IGNORE INTO prompts VALUES (?)", (prompt_id,))
            await self.status(job_id, "submitted", prompt_id=prompt_id)
            running_reported = False
            while True:
                history = await self.local("GET", "/history/" + prompt_id)
                if prompt_id in history:
                    entry = history[prompt_id]
                    if entry.get("status", {}).get("status_str") == "error":
                        phase = "cancelled" if job_id in self.cancelled else "failed"
                        self.save(job_id, phase, prompt_id)
                        await self.status(
                            job_id,
                            phase,
                            error="任务已取消或 ComfyUI 执行失败，请检查本机任务记录。",
                        )
                        return
                    self.runtime.state.own_history_outputs(history)
                    self.save(job_id, "generated", prompt_id, entry)
                    await self.status(job_id, "succeeded", transfer_status="pending")
                    await self.upload_outputs(job, entry)
                    return
                queue = await self.local("GET", "/queue")
                if not running_reported and any(
                    row[1] == prompt_id for row in queue.get("queue_running", [])
                ):
                    await self.status(job_id, "running", prompt_id=prompt_id)
                    running_reported = True
                if job_id in self.cancelled:
                    if any(row[1] == prompt_id for row in queue.get("queue_pending", [])):
                        await self.local("POST", "/queue", json={"delete": [prompt_id]})
                        self.save(job_id, "cancelled", prompt_id)
                        await self.status(job_id, "cancelled")
                        return
                    if any(row[1] == prompt_id for row in queue.get("queue_running", [])):
                        # Targeted interruption is required; never interrupt an unrelated canvas task.
                        await self.local("POST", "/interrupt", json={"prompt_id": prompt_id})
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except (aiohttp.ClientError, OSError, ValueError, KeyError, TimeoutError) as exc:
            self.runtime.error = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Hosted task connection interrupted; reconnecting."
            )
            record = self.record(job_id)
            if not record:
                self.save(job_id, "failed")
                try:
                    await self.status(job_id, "failed", error=self.runtime.error[:500])
                except (aiohttp.ClientError, ValueError, TimeoutError):
                    pass

    async def upload_outputs(self, job, history):
        job_id = job["id"]
        try:
            await self.status(job_id, "succeeded", transfer_status="pending")
            count = 0
            for node_id in job["outputs"]:
                output = history.get("outputs", {}).get(node_id, {})
                for group in output.values():
                    if not isinstance(group, list):
                        continue
                    for item in group:
                        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                            continue
                        if item.get("type", "output") not in {"output", "temp"}:
                            continue
                        await self.upload_file(job_id, item)
                        count += 1
            if not count:
                raise ValueError("所选输出节点没有产生可上传的图像、视频或音频文件。")
            self.save(job_id, "complete")
            await self.status(job_id, "succeeded", transfer_status="complete")
        except (aiohttp.ClientError, OSError, ValueError, TimeoutError) as exc:
            self.save(job_id, "upload_failed")
            await self.status(
                job_id,
                "succeeded",
                transfer_status="failed",
                error=str(exc)[:500]
                if isinstance(exc, ValueError)
                else "资源上传中断，本机结果已保留，可稍后重新上传。",
            )

    async def upload_file(self, job_id, item):
        source = {
            "filename": item["filename"],
            "subfolder": item.get("subfolder", ""),
            "type": item.get("type", "output"),
        }
        if not self.runtime.state.owns_output(
            source["filename"], source["subfolder"], source["type"]
        ):
            raise ValueError("Output does not belong to this device task")
        temp = self.runtime.state.root / (job_id + ".hosted-output")
        try:
            async with self.runtime.session.get(
                self.runtime.local_origin + "/view?" + urlencode(source)
            ) as response:
                response.raise_for_status()
                mime = response.headers.get("Content-Type", "").split(";")[0]
                if not mime.startswith(("image/", "video/", "audio/")):
                    mime = mimetypes.guess_type(source["filename"])[0] or "application/octet-stream"
                size = 0
                with temp.open("wb") as output:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        size += len(chunk)
                        if size > 500000000:
                            raise ValueError("结果超过 500 MB，已保留在本机。")
                        output.write(chunk)
            asset = await self.api(
                "POST",
                f"/jobs/{job_id}/assets",
                json={
                    "name": source["filename"],
                    "mime": mime,
                    "size": size,
                    "source_key": json.dumps(source, sort_keys=True),
                },
            )
            if asset["status"] == "ready":
                return
            progress = await self.api("GET", f"/assets/{asset['id']}")
            completed = {p["part"] for p in progress["parts"]}
            with temp.open("rb") as stream:
                part = 1
                while chunk := stream.read(asset["part_bytes"]):
                    if part not in completed:
                        await self.api("PUT", f"/assets/{asset['id']}/parts/{part}", data=chunk)
                    part += 1
            await self.api("POST", f"/assets/{asset['id']}/complete", json={})
        finally:
            temp.unlink(missing_ok=True)
