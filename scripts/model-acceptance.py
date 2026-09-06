"""Run a benign, low-load branch of a supplied workflow without modifying its source."""
import argparse
import json
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=["krea", "h3"])
parser.add_argument("--admin", default="http://127.0.0.1:8892")
args = parser.parse_args()
client = httpx.Client(timeout=180, trust_env=False)
admin = args.admin.rstrip("/") + "/admin/api"
comfy = "http://127.0.0.1:8189"
session = client.get(admin + "/session").json()
headers = {"Origin": args.admin, "X-CSRF-Token": session["csrf_token"]}


def call(method, path, **kwargs):
    response = client.request(method, admin + path, headers=headers, **kwargs)
    if response.is_error:
        raise RuntimeError(f"{method} {path}: {response.text[:3000]}")
    return response.json() if response.content else None


source = json.loads(Path(f"artifacts/{args.kind}-api.json").read_text(encoding="utf-8"))
if args.kind == "krea":
    # Reuse the user's actual model/encoder/VAE and sampler configuration in a small image branch.
    graph = {key: source[key] for key in ("11", "12", "13")}
    graph.update({
        "201": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["12", 0], "text": "A small red ceramic teapot on a white table, soft daylight, product photograph."}},
        "202": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["201", 0]}},
        "203": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "204": {"class_type": "KSampler", "inputs": {"model": ["11", 0], "positive": ["201", 0], "negative": ["202", 0], "latent_image": ["203", 0], "seed": 142, "steps": 4, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "205": {"class_type": "VAEDecode", "inputs": {"samples": ["204", 0], "vae": ["13", 0]}},
        "206": {"class_type": "SaveImage", "inputs": {"images": ["205", 0], "filename_prefix": "ComfyRemote/connector-model-test"}},
    })
    output = "206"
    fields = []
    uploads = {}
else:
    graph = source
    director = graph["183"]["inputs"]
    director["提示词 / 创意思路"] = "A red paper boat gently moves across calm blue water. Static camera, soft daylight."
    director["提示词模式"] = "手写提示词"
    director["百万像素"] = .065
    director["时长(秒)"] = 1.0
    director["宽高比"] = "1:1 (Square)"
    director["加速模式"] = "Turbo · 4步"
    director["素材列表JSON"] = "[]"
    graph["92"]["inputs"]["filename_prefix"] = "ComfyRemote/connector-model-test"
    # ComfyUI 0.34.5 changed CreateVideo.bit_depth from INT to COMBO.
    graph["130"]["inputs"]["bit_depth"] = 8
    fields = [{"key": "reference", "label": "Reference image", "node_id": "183", "input_name": "素材列表JSON", "type": "media", "upload_serialization": "media_manifest_json", "max_files": 9, "required": True, "accept": ["image/*", "video/*"]}]
    image_path = Path("artifacts/reference-boat.png")
    image = Image.new("RGB", (384,384), (110,183,214))
    draw = ImageDraw.Draw(image)
    draw.polygon([(60,205),(320,205),(260,268),(118,268)], fill=(196,44,50))
    draw.polygon([(140,202),(220,100),(260,202)], fill=(238,100,80))
    image.save(image_path)
    with image_path.open("rb") as stream:
        uploaded = call("POST", "/uploads", files={"file": (image_path.name, stream, "image/png")})
    uploads = {"reference": [uploaded["upload_id"]]}
    output = "92"
response = client.post(comfy + "/comfyremote/workflow", headers={"Origin": comfy, "X-ComfyRemote": "1"}, json={"name": f"Connector {args.kind} model acceptance", "prompt": graph})
response.raise_for_status()
wid = response.json()["workflow_id"]
print(json.dumps({"workflow_id": wid, "kind": args.kind}), flush=True)
for name in sorted({node["class_type"] for node in graph.values()}):
    call("PUT", "/trusted-nodes/" + name)
call("PUT", f"/workflows/{wid}/versions/1", json={"fields": fields, "output_nodes": [output]})
version = call("POST", f"/workflows/{wid}/versions/1/validate")
print(json.dumps({"validation": version["validation"]}, ensure_ascii=False), flush=True)
job = call("POST", f"/workflows/{wid}/versions/1/test", json={"parameters": {}, "uploads": uploads})
Path(f"artifacts/{args.kind}-active-job.json").write_text(json.dumps({"workflow_id": wid,"job_id":job["id"]}), encoding="utf-8")
print(json.dumps({"job_id": job["id"]}), flush=True)
last = None
deadline = time.monotonic() + 1800
while time.monotonic() < deadline:
    job = call("GET", f"/jobs/{job['id']}")
    state = {"status": job["status"], "progress": job["progress"], "error": job["error"]}
    if state != last:
        print(json.dumps(state, ensure_ascii=False), flush=True)
        last = state
    if job["status"] in {"succeeded", "failed", "cancelled"}:
        break
    time.sleep(5)
Path(f"artifacts/model-{args.kind}.json").write_text(json.dumps(job), encoding="utf-8")
assert job["status"] == "succeeded", job.get("error")
print(json.dumps({"assets": job["assets"]}), flush=True)
