import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { savedWorkflows, workflowName, workflowPrompt } from "./workflows.js";

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
  const header = element("div", { className: "cr-header" });
  const heading = element("h2", {}, "ComfyRemote");
  const status = element("span", { className: "cr-status", role: "status" }, "连接中");
  const account = element("p", { className: "cr-account", hidden: true });
  const connectedService = element("p", { className: "cr-service", hidden: true });
  const error = element("p", { className: "cr-error", role: "alert", hidden: true });
  const pairForm = element("form", { className: "cr-form" });
  const service = element("input", { type: "url", required: true, placeholder: "https://comfy-app.dominohub.xyz", autoComplete: "url" });
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
  const chooser = element("div", { className: "cr-chooser" });
  const listHeader = element("div", { className: "cr-list-header" });
  const search = element("input", { type: "search", placeholder: "搜索工作流" });
  search.setAttribute("aria-label", "搜索工作流");
  const reloadList = element("button", { type: "button", className: "cr-icon", title: "刷新工作流列表" });
  reloadList.setAttribute("aria-label", "刷新工作流列表");
  reloadList.append(element("i", { className: "pi pi-refresh" }));
  const list = element("div", { className: "cr-workflows", role: "radiogroup" });
  list.setAttribute("aria-label", "选择工作流");
  const listMessage = element("p", { className: "cr-list-message", role: "status" });
  listHeader.append(search, reloadList);
  chooser.append(listHeader, list, listMessage);
  const name = element("input", { required: true, maxLength: 200 });
  const send = element("button", { type: "submit", className: "cr-primary" }, "发送当前工作流");
  const result = element("a", { className: "cr-review", target: "_blank", rel: "noopener", hidden: true });
  const feedback = element("p", { className: "cr-feedback", role: "status", hidden: true });
  workflowForm.append(chooser);
  field(workflowForm, "工作流名称", name);
  workflowForm.append(send, feedback, result);
  const disconnect = element("button", { type: "button", className: "cr-disconnect", hidden: true, title: "解除配对" });
  disconnect.setAttribute("aria-label", "解除配对");
  disconnect.append(element("i", { className: "pi pi-sign-out" }));
  disconnect.append(element("span", {}, "解除配对"));
  header.append(heading, status, disconnect);
  root.append(header, account, connectedService, error, pairForm, workflowForm);
  container.replaceChildren(root);
  let current = {};
  let busy = false;
  let connectionError = "";
  let selectedPath = "";
  let paths = [];
  let listError = "";
  const cannotSend = () => busy || !current.online || Boolean(selectedPath && !paths.includes(selectedPath));
  const currentName = () => app.extensionManager?.workflow?.activeWorkflow?.filename?.replace(/\.json$/i, '') || "当前工作流";
  name.value = currentName();
  function renderList() {
    list.replaceChildren();
    const matching = paths.filter(path => path.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()));
    for (const path of ["", ...matching, ...(selectedPath && !paths.includes(selectedPath) ? [selectedPath] : [])]) {
      const row = element("label", { className: "cr-workflow", title: path || "当前画布（包含未保存修改）" });
      const radio = element("input", { type: "radio", name: "comfyremote-workflow", value: path, checked: selectedPath === path, disabled: busy });
      radio.setAttribute("aria-label", path || "当前画布（包含未保存修改）");
      const text = element("span");
      text.append(element("strong", {}, path ? path.split('/').pop() : "当前画布"));
      radio.addEventListener("change", () => {
        selectedPath = path;
        name.value = path ? workflowName(path) : currentName();
        send.textContent = path ? "发送所选工作流" : "发送当前工作流";
        result.hidden = true;
        feedback.hidden = true;
        send.disabled = cannotSend();
      });
      row.append(radio, text);
      list.append(row);
    }
    listMessage.textContent = listError || (!paths.length ? "暂无已保存工作流" : !matching.length ? "没有匹配的工作流" : "");
    listMessage.hidden = !listMessage.textContent;
  }
  async function refreshList() {
    reloadList.disabled = true;
    try {
      paths = await savedWorkflows();
      listError = selectedPath && !paths.includes(selectedPath) ? "所选文件已不存在，请重新选择。" : "";
    } catch (cause) { listError = cause.message; }
    finally { renderList(); reloadList.disabled = busy; send.disabled = cannotSend(); }
  }
  search.addEventListener("input", renderList);
  reloadList.addEventListener("click", () => void refreshList());
  renderList();
  void refreshList();
  const update = (value) => {
    current = value;
    status.textContent = value.paired ? (value.online ? "已连接" : "重连中") : "未连接";
    status.dataset.online = String(Boolean(value.online));
    pairForm.hidden = Boolean(value.paired);
    workflowForm.hidden = !value.paired;
    disconnect.hidden = !value.paired;
    connectedService.hidden = !value.paired;
    connectedService.textContent = value.service || "";
    account.hidden = !value.paired;
    account.textContent = value.owner_email || "账号信息暂不可用";
    send.disabled = cannotSend();
    if (value.error) { error.textContent = value.error; error.hidden = false; }
    else if (connectionError && error.textContent === connectionError) { error.hidden = true; }
    connectionError = value.error || "";
    if (!value.paired) result.hidden = true;
    if (value.paired && value.last_import && !result.hidden) {
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
    for (const input of workflowForm.querySelectorAll("input")) input.disabled = true;
    for (const button of root.querySelectorAll("button")) button.disabled = true;
    error.hidden = true;
    try { await callback(); } catch (cause) { feedback.hidden = true; error.textContent = cause.message; error.hidden = false; }
    finally {
      busy = false;
      for (const input of workflowForm.querySelectorAll("input")) input.disabled = false;
      for (const button of root.querySelectorAll("button")) button.disabled = false;
      send.disabled = cannotSend();
    }
  };
  pairForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void action(async () => { update(await request("pair", { origin: service.value.trim(), code: code.value.trim().toUpperCase() })); code.value = ""; });
  });
  workflowForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void action(async () => {
      if (selectedPath && !paths.includes(selectedPath)) throw new Error("所选文件已不存在，请重新选择。");
      result.hidden = true;
      feedback.hidden = false;
      feedback.textContent = "正在发送工作流…";
      const prompt = await workflowPrompt(selectedPath);
      if (!prompt || !Object.keys(prompt).length) throw new Error("所选工作流没有可执行节点。");
      const value = await request("workflow", { name: name.value.trim(), prompt });
      const review = new URL(value.review_path, current.service);
      if (review.origin !== new URL(current.service).origin) throw new Error("服务返回了无效的审核地址。");
      result.href = review.href;
      result.textContent = value.duplicate ? "查看已有工作流" : `审核字段（${value.candidate_count}）`;
      result.hidden = false;
      feedback.textContent = value.duplicate ? "工作流已存在，已定位原草稿。" : "发送成功，工作流已导入为草稿。";
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
