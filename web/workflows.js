import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { exportControlledGraph } from "./controls.js";

export async function savedWorkflows() {
  const response = await api.fetchApi('/userdata?dir=workflows&recurse=true');
  if (response.status === 404) return [];
  if (!response.ok) throw new Error('无法读取工作流列表，请刷新重试。');
  const paths = await response.json();
  if (!Array.isArray(paths)) throw new Error('工作流列表格式无效。');
  return paths.filter(path => typeof path === 'string' && path.toLowerCase().endsWith('.json'))
    .sort((a, b) => a.localeCompare(b, 'zh-CN', { numeric: true }));
}

export function workflowName(path) {
  return path.split('/').pop().replace(/\.json$/i, '');
}

function checkNodes(graph) {
  const missing = (graph._nodes || []).filter(node => node.type && !globalThis.LiteGraph.registered_node_types[node.type]);
  if (missing.length) throw new Error(`工作流缺少节点：${[...new Set(missing.map(node => node.type))].join('、')}`);
}

export async function workflowPayload(path) {
  if (path && (path.split('/').some(part => !part || part === '.' || part === '..') || /[\\:]/.test(path))) {
    throw new Error('工作流路径无效。');
  }
  let data;
  if (path) {
    const response = await api.fetchApi(`/userdata/${encodeURIComponent('workflows/' + path)}`);
    if (!response.ok) throw new Error(response.status === 404 ? '工作流文件已不存在，请刷新列表。' : '无法读取所选工作流。');
    data = await response.json();
  } else {
    checkNodes(app.rootGraph || app.graph);
    data = (app.rootGraph || app.graph).serialize();
  }
  if (!data || !Array.isArray(data.nodes)) throw new Error('文件不是可转换的 ComfyUI 工作流。');
  if (path && data.definitions?.subgraphs?.length) throw new Error('此工作流包含子图，暂不支持后台转换；请打开后选择当前画布发送。');
  const missing = data.nodes.filter(node => !globalThis.LiteGraph.registered_node_types[node.type]);
  if (missing.length) throw new Error(`工作流缺少节点：${[...new Set(missing.map(node => node.type))].join('、')}`);
  const graph = new globalThis.LGraph();
  try {
    graph.configure(structuredClone(data));
    checkNodes(graph);
    return await exportControlledGraph(graph, g => app.graphToPrompt(g));
  } finally {
    graph.clear();
  }
}

// Legacy API for extensions which only need the original executable prompt.
export async function workflowPrompt(path) {
  const value = await workflowPayload(path);
  return value.original_prompt || value.prompt;
}
