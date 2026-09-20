# Tool operations — workflow-controls-v1

Version 0.2.3 requires a server advertising `workflow-controls-v1` to import tool
descriptions. Existing ordinary workflows and remote generation remain compatible
with older servers. API execution JSON cannot reconstruct removed virtual nodes;
send the canvas or saved workflow again after updating the connector and server.

The candidate list keeps each tool's actual type, node id and custom title. Group
labels come from the workflow. Labels are editable display text, never identifiers.
Two equally named groups retain separate import-local control ids.

| Operation | Support |
| --- | --- |
| Fast Groups Bypasser (rgthree) | Boolean enable / bypass, mode 0 / 4 |
| Fast Groups Muter (rgthree) | Boolean enable / mute, mode 0 / 2 |
| Mixed initial member modes | Explicit default required before field save |
| Parent groups | Prefer matched independent leaves; parent diagnostic shown |
| Duplicate/intersecting groups and cross-controller targets | Only conflicting controls disabled |
| Group-local Reroute / PrimitiveNode / controllers | Fixed; exact unsupported members shown |
| Note / MarkdownNote | Excluded from executable targets |
| Subgraphs, linked restrictions and unknown graph transforms | Fixed import state; reason shown |
| Other virtual tools / momentary buttons | No guessed executable field |

`web/controls.js` exports `registerControlAdapter(classType, adapter)`. An adapter
receives the isolated node and graph and returns `controls` or an unsupported
`reason`. Controls declare an id, label, boolean type, member ids, off mode and
original state. The first server contract whitelists the two adapters above.
Adding an adapter requires matching server validation, execution semantics and
native comparison fixtures; registering frontend code alone grants no capability.

Import clones the workflow, discovers operations, and exports both the original
native prompt and the full active branches with ordered port metadata. Node modes
are restored even if export fails. The local Python compiler checks original-state
equivalence against ComfyUI `graphToPrompt` before upload. The original reference
stays local; only structured graph/control data are sent. No callbacks or scripts
are uploaded for execution. Safety checks also cover formerly disabled branches.

Compatible servers validate bindings, compile task-local graphs, validate required
dependencies and outputs, and consume only active media. They persist the concrete
graph for task submission/recovery. Neither execution nor changing mobile controls
requires an open ComfyUI browser or changes the original canvas.

Validation uses native ComfyUI 0.34.5 / frontend 1.49.6, independent Python and
TypeScript compiler fixtures, and actual isolated CPU resize jobs with the browser
closed. `scripts/browser-controls.cjs` exercises renamed/same-name groups, mixed
state, restrictions, overlap, unknown tools, subgraphs and ordinary imports.
No production service, workflow or pairing is upgraded by this release procedure.

## 导入诊断

导入请求可携带 `control_diagnostics`，与 `control_manifest` 分离。每项包括 `node_id`、`group_id`、`group_label`、`code`、`reason`、`related_node_ids`。最多 1000 项，文字最多 200 字，关联节点最多 50 个；控制器必须存在。诊断只作文字展示，不改变候选绑定、权限或执行。

共享服务将诊断存入既有 `package_manifest_json`，配置页在可用字段旁展示受限分组。旧导入没有该属性时按空列表处理；更新草稿时替换诊断，旧发布版本保持原样。旧服务会忽略新增请求属性，仍独立验证 v1 执行清单；旧界面不会展示分组级说明。

修复不会回填已有工作流。启用新版代码后需重新发送并审核草稿。API 执行 JSON 无法恢复已被转换掉的虚拟工具操作。

## 扩展与验证

复用插件 `registerControlAdapter`；新增执行语义必须同时有服务端校验、编译规则及 ComfyUI 原生执行图参考，不能只注册一个前端控件。标准字段不按节点名称硬编码。未知工具暂保留固定状态并展示原因。

原生参考使用带父分组、组外 Reroute、Note / MarkdownNote 的小型图，对比 Bypass / Mute 开关结果。插件 Python、共享 Python 和 TypeScript 消费相同参考；浏览器发现检查覆盖同名、筛选、重叠及导出失败时模式恢复。不需要运行大型模型来验证图转换。
