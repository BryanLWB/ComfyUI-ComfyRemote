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
| Overlapping target sets, subgraphs, linked toggle restrictions | Fixed import state; reason shown |
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
