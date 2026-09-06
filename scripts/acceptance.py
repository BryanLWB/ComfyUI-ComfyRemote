"""Exercise real ComfyUI and ComfyRemote APIs using isolated, benign sample graphs."""
import argparse
import json
import time
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--kind", choices=["image", "video"], default="image")
parser.add_argument("--admin", default="http://127.0.0.1:8892")
parser.add_argument("--comfy", default="http://127.0.0.1:8189")
parser.add_argument("--publish", action="store_true")
args = parser.parse_args()
client = httpx.Client(timeout=150, trust_env=False)
admin = args.admin.rstrip("/") + "/admin/api"
comfy = args.comfy.rstrip("/")
session = client.get(admin + "/session").json()
headers = {"Origin": args.admin, "X-CSRF-Token": session["csrf_token"]}


def call(method, path, **kwargs):
    response = client.request(method, admin + path, headers=headers, **kwargs)
    if response.is_error:
        raise RuntimeError(f"{method} {path}: {response.text[:3000]}")
    return response.json() if response.content else None


graph = {
    "1": {"class_type": "EmptyImage", "inputs": {"width": 256, "height": 256, "batch_size": 8 if args.kind == "video" else 1, "color": 3372963}},
}
if args.kind == "video":
    graph["2"] = {"class_type": "CreateVideo", "inputs": {"images": ["1", 0], "fps": 8.0}}
    graph["3"] = {"class_type": "SaveVideo", "inputs": {"video": ["2", 0], "filename_prefix": "ComfyRemote/connector-acceptance", "format": "mp4", "codec": "h264"}}
else:
    graph["3"] = {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "ComfyRemote/connector-acceptance"}}
response = client.post(comfy + "/comfyremote/workflow", headers={"Origin": comfy, "X-ComfyRemote": "1"}, json={"name": f"Connector {args.kind} acceptance", "prompt": graph})
response.raise_for_status()
imported = response.json()
wid = imported["workflow_id"]
print(json.dumps({"import": imported}), flush=True)
for name in {node["class_type"] for node in graph.values()}:
    call("PUT", "/trusted-nodes/" + name)
call("PUT", f"/workflows/{wid}/versions/1", json={"fields": [], "output_nodes": ["3"]})
validation = call("POST", f"/workflows/{wid}/versions/1/validate")
print(json.dumps({"validation": validation}, ensure_ascii=False)[:2000], flush=True)
job = call("POST", f"/workflows/{wid}/versions/1/test", json={"parameters": {}, "uploads": {}})
deadline = time.monotonic() + 120
while time.monotonic() < deadline:
    job = call("GET", f"/jobs/{job['id']}")
    if job["status"] in {"succeeded", "failed", "cancelled"}:
        break
    time.sleep(2)
print(json.dumps({"job": job}, ensure_ascii=False)[:3000], flush=True)
assert job["status"] == "succeeded", job
assert job["assets"], job
if args.publish:
    published = call("POST", f"/workflows/{wid}/versions/1/publish")
    print(json.dumps({"published": published.get("status"), "workflow_id": wid}), flush=True)
Path("artifacts").mkdir(exist_ok=True)
Path(f"artifacts/acceptance-{args.kind}.json").write_text(json.dumps({"workflow_id": wid, "job": job}), encoding="utf-8")
