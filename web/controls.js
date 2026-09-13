// Import-time discovery only. Execution uses a versioned declarative manifest.
const adapters = new Map();
export function registerControlAdapter(classType, adapter) {
  if (adapters.has(classType)) throw new Error(`Duplicate tool adapter: ${classType}`);
  adapters.set(classType, adapter);
}
const text = value => String(value || "").replace(/[\x00-\x1f]/g, " ").slice(0, 200);
function color(value, palette) {
  let c = String(value || "").trim().toLowerCase();
  c = palette?.[c]?.groupcolor || c;
  c = c.replace(/^#/, "");
  return "#" + (c.length === 3 ? c.replace(/(.)/g, "$1$1") : c);
}
function groupAdapter(node, graph, modeOff) {
  const context = document.createElement("canvas").getContext("2d");
  if (node.properties?.toggleRestriction && node.properties.toggleRestriction !== "default") return { reason: "分组联动限制暂不支持，请保留固定状态" };
  let pattern;
  try { pattern = node.properties?.matchTitle?.trim() ? new RegExp(node.properties.matchTitle, "i") : null; }
  catch { return { reason: "分组名称筛选表达式无效" }; }
  const colors = String(node.properties?.matchColors || "").split(",").filter(c => c.trim()).map(c => color(c, globalThis.LGraphCanvas?.node_colors));
  const groups = (graph._groups || []).filter(g => (!pattern || pattern.test(g.title)) && (!colors.length || colors.includes(color(g.color))));
  const controls = [];
  for (const g of groups) {
    const bounds = g._bounding;
    if (!bounds) return { reason: "当前 ComfyUI 分组结构不受支持" };
    // Same centre-point membership rule as rgthree FastGroupsService. Do not use titles as identity.
    const members = (graph._nodes || []).filter(n => {
      let b = n.getBounding();
      if (context && b.every(v => v === 0)) { n.updateArea?.(context); b = n.getBounding(); }
      return b[0] + b[2] / 2 >= bounds[0] && b[0] + b[2] / 2 < bounds[0] + bounds[2] && b[1] + b[3] / 2 >= bounds[1] && b[1] + b[3] / 2 < bounds[1] + bounds[3];
    });
    if (members.some(n => n.isVirtualNode || n.isSubgraphNode?.())) return { reason: "目标分组包含虚拟节点或子图，暂保留固定状态" };
    if (!members.length) continue;
    const index = graph._groups.indexOf(g);
    controls.push({ id: `g_${index}`, label: text(g.title) || "未命名分组", type: "boolean", mode_off: modeOff,
      members: members.map(n => String(n.id)),
      default: members.every(n => (n.mode || 0) === 0) ? true : members.every(n => n.mode === modeOff) ? false : null });
  }
  return controls.length ? { controls } : { reason: "未找到匹配且可控制的分组" };
}
registerControlAdapter("Fast Groups Bypasser (rgthree)", (n, g) => groupAdapter(n, g, 4));
registerControlAdapter("Fast Groups Muter (rgthree)", (n, g) => groupAdapter(n, g, 2));

export function discoverControls(graph) {
  const nodes = [];
  for (const node of graph._nodes || []) {
    if (!node.isVirtualNode && !adapters.has(node.type)) continue;
    // Built-in transparent wiring is not an editable tool operation.
    if (["Reroute", "PrimitiveNode", "Note", "MarkdownNote"].includes(node.type)) continue;
    const adapter = adapters.get(node.type);
    const result = adapter ? adapter(node, graph) : { reason: "尚未支持的工具节点：缺少操作适配器" };
    nodes.push({ id: String(node.id), class_type: text(node.type), title: text(node.title || node.type), controls: [], ...result });
  }
  const counts = new Map();
  for (const n of nodes) for (const c of n.controls) for (const id of c.members) counts.set(id, (counts.get(id) || 0) + 1);
  for (const n of nodes) if (n.controls.some(c => c.members.some(id => counts.get(id) > 1))) {
    n.controls = []; n.reason = "目标分组重叠，暂不支持独立控制";
  }
  if (graph.serialize().definitions?.subgraphs?.length) for (const n of nodes) {
    n.controls = []; n.reason = "包含子图的工作流暂不支持分组控制";
  }
  const externalTransform = (graph._nodes || []).some(n => n.isVirtualNode && !adapters.has(n.type) && !["Reroute", "PrimitiveNode", "Note", "MarkdownNote"].includes(n.type) && (n.applyToGraph || n.resolveVirtualOutput));
  if (externalTransform) for (const n of nodes) if (n.controls.length) {
    n.controls = []; n.reason = "其他工具节点包含未适配的执行图转换，暂保留固定状态";
  }
  return { version: 1, compiler: "comfyui-bypass-v1", nodes, modes: {}, ports: {} };
}

export async function exportControlledGraph(graph, convert) {
  const manifest = discoverControls(graph);
  const original = (await convert(graph)).output;
  if (!manifest.nodes.some(n => n.controls.length)) return { prompt: original, ...(manifest.nodes.length ? { control_manifest: manifest } : {}) };
  const nodes = graph._nodes || [];
  const savedModes = new Map(nodes.map(n => [n, n.mode]));
  try {
    for (const node of nodes) if (!node.isVirtualNode) node.mode = 0;
    const full = (await convert(graph)).output;
    for (const [id] of Object.entries(full)) {
      const node = nodes.find(n => String(n.id) === id);
      if (!node) throw new Error("工具节点控制不支持展开后的子图，请使用固定状态发送。");
      manifest.modes[id] = savedModes.get(node) || 0;
      manifest.ports[id] = { inputs: (node.inputs || []).map(i => ({ name: i.name, type: String(i.type ?? "") })), outputs: (node.outputs || []).map(o => String(o.type ?? "")) };
    }
    return { prompt: full, control_manifest: manifest, original_prompt: original };
  } finally {
    for (const [node, mode] of savedModes) node.mode = mode;
  }
}
