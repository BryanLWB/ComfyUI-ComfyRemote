"""workflow-controls-v1; keep behavior aligned with frontend/src/workflowControls.ts."""

from __future__ import annotations

import copy
import re


def _bad(message):
    raise ValueError("工具节点：" + message)


def _keys(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        _bad("包含未支持的描述属性")


def _id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]+(?::[0-9]+)*", value)


def _label(value):
    return isinstance(value, str) and 0 < len(value) <= 200 and not re.search(r"[\x00-\x1f]", value)


def validate_control_manifest(raw, graph):
    if raw is None:
        return None
    _keys(raw, ["version", "compiler", "nodes", "modes", "ports"])
    if (
        type(raw.get("version")) is not int
        or raw.get("version") != 1
        or raw.get("compiler") != "comfyui-bypass-v1"
        or not isinstance(raw.get("nodes"), list)
        or len(raw["nodes"]) > 500
        or not isinstance(raw.get("modes"), dict)
        or not isinstance(raw.get("ports"), dict)
    ):
        _bad("描述版本或结构不受支持")
    ids, claimed = set(), set()
    for node in raw["nodes"]:
        _keys(node, ["id", "class_type", "title", "reason", "controls"])
        if (
            not _id(node.get("id"))
            or node["id"] in ids
            or not _label(node.get("class_type"))
            or not _label(node.get("title"))
            or not isinstance(node.get("controls"), list)
            or len(node["controls"]) > 200
            or ("reason" in node and not _label(node["reason"]))
        ):
            _bad("节点标识或控件列表无效")
        ids.add(node["id"])
        expected = {"Fast Groups Bypasser (rgthree)": 4, "Fast Groups Muter (rgthree)": 2}.get(
            node["class_type"]
        )
        if node["controls"] and (node.get("reason") or expected is None):
            _bad("工具节点适配器尚未支持")
        controls = set()
        for c in node["controls"]:
            _keys(c, ["id", "label", "type", "members", "mode_off", "default"])
            if (
                not isinstance(c.get("id"), str)
                or not re.fullmatch(r"g_[0-9]+", c["id"])
                or c["id"] in controls
                or not _label(c.get("label"))
                or c.get("type") != "boolean"
                or c.get("mode_off") != expected
                or "default" not in c
                or (c["default"] is not None and not isinstance(c["default"], bool))
                or not isinstance(c.get("members"), list)
                or not 0 < len(c["members"]) <= 5000
            ):
                _bad("控件类型或操作无效")
            controls.add(c["id"])
            for node_id in c["members"]:
                if not _id(node_id) or node_id not in graph or node_id in claimed:
                    _bad("分组目标不存在或重叠")
                claimed.add(node_id)
            modes = [raw["modes"].get(n) for n in c["members"]]
            initial = (
                True
                if all(m == 0 for m in modes)
                else False
                if all(m == expected for m in modes)
                else None
            )
            if c["default"] is not initial:
                _bad("控件初始状态与工作流不一致")
    if not claimed and (raw["modes"] or raw["ports"]):
        _bad("无可用控件时不应包含执行转换")
    if claimed:
        if set(raw["modes"]) != set(graph) or set(raw["ports"]) != set(graph):
            _bad("缺少完整分支结构")
        for node_id in graph:
            p = raw["ports"][node_id]
            _keys(p, ["inputs", "outputs"])
            if (
                type(raw["modes"][node_id]) is not int
                or raw["modes"][node_id] not in (0, 2, 4)
                or not isinstance(p.get("inputs"), list)
                or not isinstance(p.get("outputs"), list)
                or len(p["inputs"]) > 500
                or len(p["outputs"]) > 500
            ):
                _bad("节点端口或初始状态无效")
            names = set()
            for i in p["inputs"]:
                _keys(i, ["name", "type"])
                if (
                    not _label(i.get("name"))
                    or i["name"] in names
                    or not isinstance(i.get("type"), str)
                    or len(i["type"]) > 200
                ):
                    _bad("输入端口无效")
                names.add(i["name"])
            if any(not isinstance(t, str) or len(t) > 200 for t in p["outputs"]):
                _bad("输出端口无效")
        # Validate all port records before following cross-node links.
        for node_id, node in graph.items():
            names = {i["name"] for i in raw["ports"][node_id]["inputs"]}
            for name, value in node["inputs"].items():
                if isinstance(value, list) and (
                    len(value) != 2
                    or not _id(value[0])
                    or type(value[1]) is not int
                    or value[1] < 0
                    or name not in names
                    or value[0] not in graph
                    or value[1] >= len(raw["ports"].get(value[0], {}).get("outputs", []))
                ):
                    _bad("连接或端口缺失")
    return raw


def control_candidates(manifest):
    return [
        {
            "key": f"ctrl_{n['id'].replace(':', '_')}_{c['id']}",
            "node_id": n["id"],
            "input_name": c["id"],
            "binding_kind": "tool_control",
            "label": c["label"][:100],
            "type": "boolean",
            "default": c["default"],
            "required": False,
        }
        for n in (manifest or {}).get("nodes", [])
        for c in n["controls"]
    ]


def control_nodes(manifest):
    return [
        {
            "id": n["id"],
            "class_type": n["class_type"],
            "title": n["title"],
            "inputs": [
                {"name": c["id"], "type": "BOOLEAN", "value": c["default"]} for c in n["controls"]
            ],
        }
        for n in (manifest or {}).get("nodes", [])
    ]


def validate_control_bindings(fields, manifest):
    seen = set()
    for field in fields:
        if field.get("binding_kind", "node_input") not in ("node_input", "tool_control"):
            _bad("字段绑定类型不受支持")
        if field.get("binding_kind") != "tool_control":
            continue
        source = next(
            (
                c
                for c in control_candidates(manifest)
                if c["node_id"] == field["node_id"] and c["input_name"] == field["input_name"]
            ),
            None,
        )
        identity = (field["node_id"], field["input_name"])
        if source is None or field["type"] != "boolean" or identity in seen:
            _bad("操作绑定无效或重复，请重新选择候选控件")
        if not isinstance(field.get("default"), bool):
            _bad("请为分组控件选择明确的开启或关闭默认值")
        seen.add(identity)


def _compatible(a, b):
    return any(
        not x or not y or x == "*" or y == "*" or x.lower() == y.lower()
        for x in a.split(",")
        for y in b.split(",")
    )


def compile_controls(graph, manifest, fields, values, outputs=None, info=None):
    validate_control_bindings(fields, manifest)
    result = copy.deepcopy(graph)
    if not manifest or not manifest["modes"]:
        return result
    modes = dict(manifest["modes"])
    for field in fields:
        if field.get("binding_kind") != "tool_control":
            continue
        condition = field.get("visible_when")
        if condition:
            controller = next((f for f in fields if f["key"] == condition["field"]), {})
            value = values.get(condition["field"], controller.get("default"))
            if not any(type(v) is type(value) and v == value for v in condition["values"]):
                continue
        value = values.get(field["key"], field.get("default"))
        if not isinstance(value, bool):
            _bad("开关值必须是布尔值")
        control = next(
            c
            for n in manifest["nodes"]
            if n["id"] == field["node_id"]
            for c in n["controls"]
            if c["id"] == field["input_name"]
        )
        modes.update({n: 0 if value else control["mode_off"] for n in control["members"]})

    def resolve(node_id, slot, expected, path):
        key = (node_id, slot)
        if key in path or len(path) > 500:
            _bad("旁路连接形成循环或超过深度限制")
        if node_id not in graph:
            _bad("连接目标不存在")
        if modes[node_id] == 2:
            return None
        if modes[node_id] == 0:
            return [node_id, slot]
        p = manifest["ports"][node_id]
        inputs, output = p["inputs"], p["outputs"][slot]
        same = inputs[slot] if slot < len(inputs) else None
        if expected in ("*", ""):
            index = slot if slot < len(inputs) else 0
        elif same and _compatible(same["type"], output) and _compatible(same["type"], expected):
            index = slot
        else:
            index = next((i for i, p in enumerate(inputs) if p["type"] == expected), -1)
            if index == -1:
                index = next(
                    (
                        i
                        for i, p in enumerate(inputs)
                        if _compatible(p["type"], output) and _compatible(p["type"], expected)
                    ),
                    -1,
                )
        port = inputs[index] if 0 <= index < len(inputs) else None
        link = graph[node_id]["inputs"].get(port["name"]) if port else None
        if not isinstance(link, list):
            return None
        return resolve(str(link[0]), link[1], port["type"], path | {key})

    for node_id, node in list(result.items()):
        if modes[node_id] != 0:
            del result[node_id]
            continue
        for name, value in list(node["inputs"].items()):
            if isinstance(value, list):
                expected = next(
                    p["type"] for p in manifest["ports"][node_id]["inputs"] if p["name"] == name
                )
                link = resolve(str(value[0]), value[1], expected, set())
                if link is not None:
                    node["inputs"][name] = link
                else:
                    del node["inputs"][name]
    if outputs is not None:
        active = [n for n in outputs if n in result]
        if not active:
            _bad("当前开关组合没有可执行的输出，请启用输出分组")
        visiting, visited = set(), set()

        def visit(node_id):
            if node_id in visiting:
                _bad("执行连接形成循环")
            if node_id in visited:
                return
            if len(visiting) > 500:
                _bad("执行图超过深度限制")
            visiting.add(node_id)
            node = result[node_id]
            for name in (
                (info or {}).get(node["class_type"], {}).get("input", {}).get("required", {})
            ):
                if name not in node["inputs"]:
                    _bad(f"节点 {node_id} 缺少必需输入 {name}，请调整开关组合")
            for value in node["inputs"].values():
                if isinstance(value, list):
                    visit(str(value[0]))
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in active:
            visit(node_id)
        for node_id, node in result.items():
            if (info or {}).get(node["class_type"], {}).get("output_node"):
                visit(node_id)
        result = {n: v for n, v in result.items() if n in visited}
    return result
