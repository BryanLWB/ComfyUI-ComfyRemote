"""Display-only import diagnostics; never used to authorize or compile controls."""

import re


def validate_control_diagnostics(raw, manifest):
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > 1000:
        raise ValueError("分组诊断列表无效")
    known = {n["id"] for n in (manifest or {}).get("nodes", [])}
    keys = {"node_id", "group_id", "group_label", "code", "reason", "related_node_ids"}
    for item in raw:
        if not isinstance(item, dict) or set(item) != keys or not isinstance(item.get("node_id"), str) or item["node_id"] not in known:
            raise ValueError("分组诊断目标无效")
        for key in ("group_id", "group_label", "code", "reason"):
            value = item[key]
            if not isinstance(value, str) or len(value) > 200 or re.search(r"[\x00-\x1f]", value):
                raise ValueError("分组诊断文字无效")
        if not re.fullmatch(r"g_[0-9]+|", item["group_id"]) or not item["reason"] or not re.fullmatch(r"[a-z_]{1,40}", item["code"]):
            raise ValueError("分组诊断标识无效")
        ids = item["related_node_ids"]
        if not isinstance(ids, list) or len(ids) > 50 or any(not isinstance(n, str) or not re.fullmatch(r"[0-9]+(?::[0-9]+)*", n) for n in ids):
            raise ValueError("分组诊断关联节点无效")
    return raw
