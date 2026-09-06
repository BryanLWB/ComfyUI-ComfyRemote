import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const style = document.createElement("link");
style.rel = "stylesheet";
style.href = new URL("./comfyremote.css", import.meta.url).href;
document.head.append(style);

async function request(action, body) {
  const response = await api.fetchApi(`/comfyremote/${action}`, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-ComfyRemote": "1" },
    body: JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "连接失败，请重试。");
  return value;
}

function element(tag, attributes = {}, text = "") {
  const node = document.createElement(tag);
  Object.assign(node, attributes);
  node.textContent = text;
  return node;
}

function mount(container) {
  const root = element("div", { className: "cr-connector" });
  const heading = element("h2", {}, "ComfyRemote");
  const status = element("p", { className: "cr-status", role: "status" }, "正在连接");
  const connectedService = element("p", { className: "cr-service", hidden: true });
  const error = element("p", { className: "cr-error", role: "alert", hidden: true });
  const pairForm = element("form", { className: "cr-form" });
  const service = element("input", { type: "url", required: true, placeholder: "https://", autoComplete: "url" });
  const code = element("input", { required: true, maxLength: 20, autoComplete: "off", spellcheck: false });
  const pairButton = element("button", { type: "submit", className: "cr-primary" }, "连接");
  function field(parent, title, input) {
    const label = element("label", {}, title);
    label.append(input);
    parent.append(label);
  }
  field(pairForm, "服务地址", service);
  field(pairForm, "配对码", code);
  pairForm.append(pairButton);
  const workflowForm = element("form", { className: "cr-form", hidden: true });
  const name = element("input", { required: true, maxLength: 200 });
  const send = element("button", { type: "submit", className: "cr-primary" }, "发送当前工作流");
  const result = element("a", { className: "cr-review", target: "_blank", rel: "noopener", hidden: true });
  field(workflowForm, "工作流名称", name);
  workflowForm.append(send, result);
  const disconnect = element("button", { type: "button", className: "cr-disconnect", hidden: true }, "解除配对");
  root.append(heading, status, connectedService, error, pairForm, workflowForm, disconnect);
  container.replaceChildren(root);
  let current = {};
  let busy = false;
  let connectionError = "";
  const update = (value) => {
    current = value;
    status.textContent = value.paired ? (value.online ? "已连接" : "重新连接中") : "未连接";
    status.dataset.online = String(Boolean(value.online));
    pairForm.hidden = Boolean(value.paired);
    workflowForm.hidden = !value.paired;
    disconnect.hidden = !value.paired;
    connectedService.hidden = !value.paired;
    connectedService.textContent = value.service || "";
    send.disabled = busy || !value.online;
    if (value.error) { error.textContent = value.error; error.hidden = false; }
    else if (connectionError && error.textContent === connectionError) { error.hidden = true; }
    connectionError = value.error || "";
    if (!value.paired) result.hidden = true;
    if (value.paired && value.last_import) {
      const review = new URL(value.last_import.review_path, value.service);
      if (review.origin === new URL(value.service).origin) {
        result.href = review.href;
        result.textContent = value.last_import.duplicate ? "查看已有工作流" : `审核字段（${value.last_import.candidate_count}）`;
        result.hidden = false;
      }
    }
  };
  const action = async (callback) => {
    busy = true;
    for (const button of root.querySelectorAll("button")) button.disabled = true;
    error.hidden = true;
    try { await callback(); } catch (cause) { error.textContent = cause.message; error.hidden = false; }
    finally {
      busy = false;
      for (const button of root.querySelectorAll("button")) button.disabled = false;
      send.disabled = !current.online;
    }
  };
  pairForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void action(async () => { update(await request("pair", { origin: service.value.trim(), code: code.value.trim().toUpperCase() })); code.value = ""; });
  });
  workflowForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void action(async () => {
      const missing = (app.graph._nodes || []).filter((node) => node.type && !globalThis.LiteGraph.registered_node_types[node.type]);
      if (missing.length) throw new Error("工作流包含缺失或无效节点，请先修复。");
      const converted = await app.graphToPrompt();
      if (!converted.output || !Object.keys(converted.output).length) throw new Error("当前工作流没有可执行节点。");
      const value = await request("workflow", { name: name.value.trim(), prompt: converted.output });
      const review = new URL(value.review_path, current.service);
      if (review.origin !== new URL(current.service).origin) throw new Error("服务返回了无效的审核地址。");
      result.href = review.href;
      result.textContent = value.duplicate ? "查看已有工作流" : `审核字段（${value.candidate_count}）`;
      result.hidden = false;
    });
  });
  disconnect.addEventListener("click", () => void action(async () => {
    if (window.confirm("解除与当前服务的配对？")) update(await request("unpair", {}));
  }));
  let mounted = false;
  const refresh = async () => {
    if (!root.isConnected) {
      if (!mounted) window.setTimeout(refresh, 100);
      return;
    }
    mounted = true;
    if (!busy) {
      try { update(await request("status")); } catch { status.textContent = "ComfyUI 连接中断"; }
    }
    window.setTimeout(refresh, 5000);
  };
  void refresh();
}

app.registerExtension({
  name: "ComfyRemote.Connector",
  async setup() {
    app.extensionManager.registerSidebarTab({
      id: "comfyremote-connector",
      icon: "pi pi-cloud-upload",
      title: "ComfyRemote",
      tooltip: "ComfyRemote",
      type: "custom",
      render: mount,
    });
  },
});
