import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { savedWorkflows, workflowName, workflowPayload } from "./workflows.js";

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
  const destination = element("select", {required: true});
  destination.setAttribute("aria-label", "发送到手机");
  const refreshTargets = element("button", {type: "button"}, "刷新手机工作流");
  let targets = [], targetSource = null, targetGeneration = 0, pendingSend = null;
  const sourcePath = () => {
    if (selectedPath) return selectedPath;
    const path = app.extensionManager?.workflow?.activeWorkflow?.path;
    const relative = typeof path === "string" ? path.replace(/^workflows\//, "") : "";
    return paths.includes(relative) ? relative : "";
  };
  async function loadTargets() {
    const generation = ++targetGeneration, source = sourcePath();
    const data = await request(`targets?source=${encodeURIComponent(source)}`);
    if (generation !== targetGeneration) return;
    targets = data.workflows || [];
    destination.replaceChildren(element("option", {value: ""}, "请选择更新目标或新建"), element("option", {value: "__new"}, "新建工作流"));
    for (const item of targets) destination.append(element("option", {value: item.workflow_id}, `${item.name} · v${item.version}`));
    if (targets.some(t => t.workflow_id === data.linked_workflow_id)) destination.value = data.linked_workflow_id;
    if (data.linked_workflow_id && !targets.some(t => t.workflow_id === data.linked_workflow_id)) {
      feedback.textContent = "原关联目标不可用，请重新选择手机工作流或另建。"; feedback.hidden = false;
    }
    destination.required = data.supported;
    destination.disabled = !data.supported;
    targetSource = source;
    pendingSend = data.pending?.length ? {_retry: data.pending[0].request_id} : null;
    if (pendingSend) { feedback.textContent = "上次发送尚未确认，重试会恢复原请求，不重复创建。"; feedback.hidden = false; send.textContent = "重试上次发送"; }
    if (data.supported && !current.capabilities?.includes("workflow-update-v1")) current.capabilities = [...(current.capabilities || []), "workflow-update-v1"];
  }
  const send = element("button", { type: "submit", className: "cr-primary" }, "发送当前工作流");
  const result = element("a", { className: "cr-review", target: "_blank", rel: "noopener", hidden: true });
  const feedback = element("p", { className: "cr-feedback", role: "status", hidden: true });
  workflowForm.append(chooser);
  field(workflowForm, "工作流名称", name);
  field(workflowForm, "发送到手机", destination);
  workflowForm.append(refreshTargets, send, feedback, result);
  refreshTargets.addEventListener("click", () => void action(loadTargets));
  destination.addEventListener("change", () => { pendingSend = null; send.textContent = destination.value && destination.value !== "__new" ? "更新手机草稿" : "发送工作流"; });
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
        targetSource = null;
        void action(loadTargets);
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
    const justConnected = !current.paired && value.paired;
    current = value;
    if (justConnected) void action(loadTargets);
    if (value.duplicate_installations?.length) {
      value.error = `检测到重复插件安装（运行版本 ${value.version}）：${value.duplicate_installations.join("、")}。请归档旧插件后重启 ComfyUI。`;
    }
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
    if (value.error || value.thumbnail_warning) { error.textContent = value.error || value.thumbnail_warning; error.hidden = false; }
    else if (connectionError && error.textContent === connectionError) { error.hidden = true; }
    connectionError = value.error || value.thumbnail_warning || "";
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
    for (const input of workflowForm.querySelectorAll("input, select")) input.disabled = true;
    for (const button of root.querySelectorAll("button")) button.disabled = true;
    error.hidden = true;
    try { await callback(); } catch (cause) { feedback.hidden = true; error.textContent = cause.message; error.hidden = false; }
    finally {
      busy = false;
      for (const input of workflowForm.querySelectorAll("input, select")) input.disabled = false;
      for (const button of root.querySelectorAll("button")) button.disabled = false;
      send.disabled = cannotSend();
      if (pendingSend) send.textContent = "重试上次发送";
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
      if (sourcePath() !== targetSource) {
        await loadTargets();
        throw new Error("当前画布来源已变化，请核对目标后再次发送。");
      }
      if (!pendingSend) {
        const payload = await workflowPayload(selectedPath);
        if (!payload.prompt || !Object.keys(payload.prompt).length) throw new Error("所选工作流没有可执行节点。");
        const supported = current.capabilities?.includes("workflow-update-v1");
        if (supported && !destination.value) throw new Error("请选择更新目标或新建工作流。");
        const target = targets.find(t => t.workflow_id === destination.value);
        const outgoing = {name: name.value.trim(), ...payload, source: sourcePath()};
        if (supported) Object.assign(outgoing, {intent: target ? "update" : "create", request_id: crypto.randomUUID(),
          ...(target ? {workflow_id: target.workflow_id, expected_revision: target.revision} : {})});
        if (target) {
          const preview = await request("preview", outgoing);
          const issues = [...(preview.issues || []).map(i => `${i.key}：${i.message}`), ...(preview.validation || []), ...Object.entries(preview.output_issues || {}).map(([id, reason]) => `${id}：${reason}`)];
          if (issues.length && !window.confirm(`更新后有配置需要修正，旧发布版本继续可用：\n${issues.join("\n")}\n是否保存为待修正草稿？`)) { feedback.hidden = true; return; }
        }
        pendingSend = outgoing;
      }
      // A lost response retries the frozen payload and request ID, even if the canvas changes.
      const value = pendingSend._retry ? await request("retry", {request_id: pendingSend._retry}) : await request("workflow", pendingSend);
      pendingSend = null;
      await loadTargets();
      const review = new URL(value.review_path, current.service);
      if (review.origin !== new URL(current.service).origin) throw new Error("服务返回了无效的审核地址。");
      result.href = review.href;
      result.textContent = value.duplicate ? "查看已有工作流" : `审核字段（${value.candidate_count}）`;
      result.hidden = false;
      feedback.textContent = value.updated ? "手机草稿已更新，兼容字段配置已保留。请检查后重新测试并发布。" : value.duplicate ? "工作流已存在，已定位原草稿。" : "发送成功，工作流已导入为草稿。";
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
    const loaded = await api.fetchApi("/extensions").then(r => r.json()).catch(() => []);
    const copies = loaded.filter(url => /\/comfyremote\.js(?:\?|$)/.test(url));
    if (copies.length > 1) {
      console.error("ComfyRemote duplicate installations:", copies);
      app.extensionManager?.toast?.add({severity: "error", summary: "ComfyRemote 重复安装", detail: "检测到多套连接插件，请归档旧插件后重启。", life: 15000});
    }

    app.extensionManager.registerSidebarTab({
      id: "comfyremote-connector",
      icon: "comfyremote-sidebar-icon",
      title: "ComfyRemote",
      tooltip: "ComfyRemote",
      type: "custom",
      render: mount,
    });
  },
});
