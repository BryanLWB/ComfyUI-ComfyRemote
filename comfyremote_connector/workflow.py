from __future__ import annotations

import re

SECRET_NAME = re.compile(
    r"api.?key|access.?token|auth.?token|authorization|password|secret|credential|cookie",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{10,}|\bsk-[A-Za-z0-9_-]{12,}|\bgh[opurs]_[A-Za-z0-9]{20,}"
)
EXECUTABLE = re.compile(
    r"shell|command|terminal|subprocess|exec(?:ute)?|python|javascript|powershell|script",
    re.IGNORECASE,
)
MODEL_NAME = re.compile(
    r"(?:ckpt|lora|vae|unet|clip|model)_name|model_path|vision_model", re.IGNORECASE
)


def validate_workflow(graph: dict) -> None:
    if not isinstance(graph, dict) or not graph or len(graph) > 5000:
        raise ValueError("Invalid executable workflow")
    for node in graph.values():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
            raise TypeError("Invalid workflow node")
        if EXECUTABLE.search(node["class_type"]):
            raise ValueError("Executable code nodes cannot be sent to ComfyRemote")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise TypeError("Invalid workflow inputs")
        for name, value in inputs.items():
            if (SECRET_NAME.search(name) and value) or (
                isinstance(value, str) and SECRET_VALUE.search(value)
            ):
                raise ValueError("Remove credentials from the workflow before sending")


def minimal_info(graph: dict, info: dict) -> dict:
    # Model selectors disclose only references used by this graph; ordinary enums retain choices.
    selected = {}
    for node in graph.values():
        for name, value in node.get("inputs", {}).items():
            if isinstance(value, str):
                selected.setdefault((node["class_type"], name), []).append(value)
    for class_type, definition in info.items():
        for section in ("required", "optional"):
            for name, spec in definition.get("input", {}).get(section, {}).items():
                if not isinstance(spec, list) or not spec:
                    continue
                if SECRET_NAME.search(name) and len(spec) > 1 and isinstance(spec[1], dict):
                    spec[1].pop("default", None)
                metadata = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                private_selector = MODEL_NAME.search(name) or any(
                    metadata.get(key) for key in ("image_upload", "video_upload", "audio_upload")
                )
                if private_selector:
                    references = selected.get((class_type, name), [])
                    if isinstance(spec[0], list):
                        spec[0] = [value for value in spec[0] if value in references]
                    elif len(spec) > 1 and isinstance(spec[1], dict) and "options" in spec[1]:
                        spec[1]["options"] = [
                            value for value in spec[1]["options"] if value in references
                        ]
    return info
