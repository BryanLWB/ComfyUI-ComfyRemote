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
const annotations = new Set(["Note", "MarkdownNote"]);
const wiring = new Set(["Reroute", "PrimitiveNode"]);
const diagnostic = (node, group, code, reason, members = []) => ({
  node_id: String(node.id), group_id: group?.id || "", group_label: text(group?.label || ""),
  code, reason: text(reason), related_node_ids: members.map(n => String(n.id)).slice(0, 50),
});
function groupAdapter(node, graph, modeOff) {
  const context = document.createElement("canvas").getContext("2d");
  if (node.properties?.toggleRestriction && node.properties.toggleRestriction !== "default") return { reason: "分组联动限制暂不支持，请保留固定状态" };
  let pattern;
  try { pattern = node.properties?.matchTitle?.trim() ? new RegExp(node.properties.matchTitle, "i") : null; }
  catch { return { reason: "分组名称筛选表达式无效" }; }
  const colors = String(node.properties?.matchColors || "").split(",").filter(c => c.trim()).map(c => color(c, globalThis.LGraphCanvas?.node_colors));
  const groups = [];
  for (const [index, g] of (graph._groups || []).entries()) {
    if ((pattern && !pattern.test(g.title)) || (colors.length && !colors.includes(color(g.color)))) continue;
    const bounds = g._bounding;
    if (!bounds) return { reason: "当前 ComfyUI 分组结构不受支持" };
    // Match rgthree's centre-point rule, including auxiliary nodes before conflict analysis.
    const members = (graph._nodes || []).filter(n => {
      let b = n.getBounding();
      if (context && b.every(v => v === 0)) { n.updateArea?.(context); b = n.getBounding(); }
      return b[0] + b[2] / 2 >= bounds[0] && b[0] + b[2] / 2 < bounds[0] + bounds[2] && b[1] + b[3] / 2 >= bounds[1] && b[1] + b[3] / 2 < bounds[1] + bounds[3];
    });
    groups.push({ id: `g_${index}`, label: text(g.title) || "未命名分组", members });
  }
  const controls = [], diagnostics = [];
  const contains = (a, b) => b.members.length && b.members.every(n => a.members.includes(n));
  // Reject parents before checking partial intersections: a parent must not poison its leaves.
  const parents = new Set(groups.filter(a => groups.some(b => a !== b && a.members.length > b.members.length && contains(a, b))));
  const leaves = groups.filter(g => !parents.has(g));
  for (const g of groups) {
    if (parents.has(g)) {
      diagnostics.push(diagnostic(node, g, "parent_group", "包含其他匹配的小分组，请使用小分组开关"));
      continue;
    }
    const clashes = leaves.filter(other => other !== g && other.members.some(n => g.members.includes(n)));
    if (clashes.length) {
      diagnostics.push(diagnostic(node, g, "overlap", `与分组 ${clashes.map(c => c.label).join("、")} 重叠，暂不支持独立控制`));
      continue;
    }
    // Wiring nodes can change native bypass/mute conversion. They are not annotations.
    const unsupported = g.members.filter(n => !annotations.has(n.type) && (wiring.has(n.type) || n.isVirtualNode || n.isSubgraphNode?.()));
    if (unsupported.length) {
      diagnostics.push(diagnostic(node, g, "unsupported_member", `节点 ${unsupported.map(n => `${n.id}（${n.type}）`).join("、")} 的分组模式转换尚未适配`, unsupported));
      continue;
    }
    const members = g.members.filter(n => !annotations.has(n.type));
    if (!members.length) {
      diagnostics.push(diagnostic(node, g, "empty_group", "没有可控制的执行节点"));
      continue;
    }
    controls.push({ id: g.id, label: g.label, type: "boolean", mode_off: modeOff,
      members: members.map(n => String(n.id)),
      default: members.every(n => (n.mode || 0) === 0) ? true : members.every(n => n.mode === modeOff) ? false : null });
  }
  return { controls, diagnostics, ...(!controls.length ? { reason: "没有可独立控制的分组，请查看各分组说明" } : {}) };
}
registerControlAdapter("Fast Groups Bypasser (rgthree)", (n, g) => groupAdapter(n, g, 4));
registerControlAdapter("Fast Groups Muter (rgthree)", (n, g) => groupAdapter(n, g, 2));

export function analyzeControls(graph) {
  const nodes = [], diagnostics = [];
  for (const node of graph._nodes || []) {
    if (!node.isVirtualNode && !adapters.has(node.type)) continue;
    if (annotations.has(node.type) || wiring.has(node.type)) continue;
    const adapter = adapters.get(node.type);
    const { diagnostics: issues = [], ...result } = adapter ? adapter(node, graph) : { reason: "尚未支持的工具节点：缺少操作适配器" };
    diagnostics.push(...issues);
    nodes.push({ id: String(node.id), class_type: text(node.type), title: text(node.title || node.type), controls: [], ...result });
  }
  const claims = nodes.flatMap(n => n.controls.map(c => ({node_id: n.id, ...c})));
  const counts = new Map();
  for (const n of nodes) for (const c of n.controls) for (const id of c.members) counts.set(id, (counts.get(id) || 0) + 1);
  for (const n of nodes) {
    n.controls = n.controls.filter(c => {
      const collisions = c.members.filter(id => counts.get(id) > 1);
      if (!collisions.length) return true;
      const others = claims.filter(other => (other.node_id !== n.id || other.id !== c.id) && other.members.some(id => collisions.includes(id)));
      diagnostics.push(diagnostic(n, c, "controller_overlap", `与 ${others.map(other => `控制器 ${other.node_id} / ${other.label}`).join("、")} 重叠，暂不支持独立控制`, collisions.map(id => ({id}))));
      return false;
    });
    if (!n.controls.length && !n.reason) n.reason = "没有可独立控制的分组，请查看各分组说明";
  }
  const hasSubgraphs = graph.serialize().definitions?.subgraphs?.length;
  const external = (graph._nodes || []).filter(n => n.isVirtualNode && !adapters.has(n.type) && !annotations.has(n.type) && !wiring.has(n.type) && (n.applyToGraph || n.resolveVirtualOutput));
  if (hasSubgraphs || external.length) for (const n of nodes) {
    n.controls = [];
    n.reason = hasSubgraphs ? "包含子图的工作流暂不支持分组控制" : `节点 ${external.map(n => `${n.id}（${n.type}）`).join("、")} 包含未适配的执行图转换`;
    n.reason = text(n.reason);
  }
  return { manifest: { version: 1, compiler: "comfyui-bypass-v1", nodes, modes: {}, ports: {} }, diagnostics };
}

export function discoverControls(graph) { return analyzeControls(graph).manifest; }

export async function exportControlledGraph(graph, convert) {
  const { manifest, diagnostics } = analyzeControls(graph);
  const original = (await convert(graph)).output;
  if (!manifest.nodes.some(n => n.controls.length)) return { prompt: original, ...(manifest.nodes.length ? { control_manifest: manifest, control_diagnostics: diagnostics } : {}) };
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
    return { prompt: full, control_manifest: manifest, control_diagnostics: diagnostics, original_prompt: original };
  } finally {
    for (const [node, mode] of savedModes) node.mode = mode;
  }
}
