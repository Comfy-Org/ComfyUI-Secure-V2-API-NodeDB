import { comfy } from "/comfy/api/v2.js";

const PANEL_ID = "h3-project-suite.projects";
const MAX_NAME = 80;

function notify(severity, summary, error) {
  comfy.commands.notify({
    severity,
    summary,
    detail: error instanceof Error ? error.message : String(error ?? ""),
  });
}

async function request(path, body) {
  const response = await comfy.backend.ownFetch(path, body === undefined ? undefined : {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error || `H3 project request failed (${response.status})`);
  }
  return data;
}

function safeName(value) {
  const name = String(value ?? "").trim();
  if (!name || name.length > MAX_NAME || name.includes("..") ||
      !/^[A-Za-z0-9][A-Za-z0-9 _.-]*$/.test(name)) {
    throw new Error("Project names may contain letters, numbers, spaces, dot, dash, and underscore.");
  }
  return name;
}

function button(doc, label, action, className = "") {
  const element = doc.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.className = `h3p-button ${className}`.trim();
  element.addEventListener("click", () => void action());
  return element;
}

class H3ProjectPanel {
  constructor() {
    this.root = undefined;
    this.select = undefined;
    this.nameInput = undefined;
    this.summary = undefined;
    this.timeline = undefined;
    this.actions = undefined;
    this.state = undefined;
    this.dialog = undefined;
  }

  async mount(container) {
    this.destroy();
    const doc = container.ownerDocument;
    const stylesheet = doc.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = new URL("./h3_project_panel.css", import.meta.url).href;

    const root = doc.createElement("section");
    root.className = "h3p-root";
    const heading = doc.createElement("h2");
    heading.textContent = "H3 Projects";

    const picker = doc.createElement("div");
    picker.className = "h3p-row";
    this.select = doc.createElement("select");
    this.select.className = "h3p-grow";
    this.select.setAttribute("aria-label", "H3 project");
    this.select.addEventListener("change", () => void this.refresh());
    picker.append(this.select, button(doc, "Refresh", () => this.loadProjects()));

    const creator = doc.createElement("div");
    creator.className = "h3p-row";
    this.nameInput = doc.createElement("input");
    this.nameInput.className = "h3p-grow";
    this.nameInput.maxLength = MAX_NAME;
    this.nameInput.placeholder = "New project name";
    this.nameInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        void this.create();
      }
    });
    creator.append(this.nameInput, button(doc, "Create", () => this.create(), "primary"));

    this.summary = doc.createElement("p");
    this.summary.className = "h3p-summary";
    this.summary.textContent = "Choose a project.";
    this.timeline = doc.createElement("div");
    this.timeline.className = "h3p-timeline";
    this.actions = doc.createElement("div");
    this.actions.className = "h3p-actions";

    root.append(heading, picker, creator, this.summary, this.timeline, this.actions);
    container.replaceChildren(stylesheet, root);
    this.root = root;
    await this.loadProjects();
  }

  destroy() {
    this.dialog?.close();
    this.dialog = undefined;
    this.root?.remove();
    this.root = undefined;
    this.state = undefined;
  }

  projectName() {
    return safeName(this.select?.value);
  }

  async loadProjects(preferred) {
    try {
      const result = await request("/projects");
      const projects = Array.isArray(result.projects) ? result.projects : [];
      const selected = preferred || this.select?.value || projects[0] || "";
      this.select.replaceChildren();
      const doc = this.select.ownerDocument;
      for (const name of projects) {
        const option = doc.createElement("option");
        option.value = name;
        option.textContent = name;
        this.select.appendChild(option);
      }
      if (projects.includes(selected)) this.select.value = selected;
      await this.refresh();
    } catch (error) {
      notify("error", "Could not list H3 projects", error);
    }
  }

  async create() {
    try {
      const name = safeName(this.nameInput.value);
      await request("/create", { name });
      this.nameInput.value = "";
      await this.loadProjects(name);
    } catch (error) {
      notify("error", "Could not create H3 project", error);
    }
  }

  async act(route, body = {}) {
    try {
      await request(route, { name: this.projectName(), ...body });
      await this.refresh();
    } catch (error) {
      notify("error", "H3 project action failed", error);
    }
  }

  async refresh() {
    if (!this.select?.value) {
      this.state = undefined;
      this.summary.textContent = "Create a project to begin.";
      this.timeline.replaceChildren();
      this.actions.replaceChildren();
      return;
    }
    try {
      const state = await request(`/state?name=${encodeURIComponent(this.projectName())}`);
      this.state = state;
      this.render();
    } catch (error) {
      notify("error", "Could not load H3 project", error);
    }
  }

  branchDialog(index, take) {
    this.dialog?.close();
    const source = this.projectName();
    let input;
    let handle;
    const submit = async () => {
      try {
        const newName = safeName(input.value);
        await request("/branch", {
          name: source, new_name: newName, index, take,
        });
        handle.close();
        this.dialog = undefined;
        await this.loadProjects(newName);
      } catch (error) {
        notify("error", "Could not branch H3 project", error);
      }
    };
    handle = comfy.ui.showDialog({
      key: "H3ProjectSuite.branch",
      title: `Branch ${source} at clip ${index}`,
      render(container) {
        const doc = container.ownerDocument;
        const explanation = doc.createElement("p");
        explanation.textContent = `Create a new project ending at take ${take}. Existing managed outputs are reused read-only.`;
        input = doc.createElement("input");
        input.maxLength = MAX_NAME;
        input.placeholder = `${source} branch`;
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void submit();
          }
        });
        container.append(explanation, input, button(doc, "Create branch", submit, "primary"));
      },
      destroy: () => { if (this.dialog === handle) this.dialog = undefined; },
    });
    this.dialog = handle;
  }

  render() {
    const state = this.state;
    const doc = this.root.ownerDocument;
    const approved = Array.isArray(state.approved) ? state.approved : [];
    const takes = Array.isArray(state.takes) ? state.takes : [];
    const pending = state.pending && typeof state.pending === "object" ? state.pending : undefined;
    const size = state.width && state.height ? ` · ${state.width}×${state.height}` : "";
    this.summary.textContent = `${approved.length} approved${pending ? " · review pending" : ""}${size}`;
    this.timeline.replaceChildren();

    const byIndex = new Map();
    for (const take of takes) {
      const index = Number(take.index);
      if (!Number.isInteger(index) || index < 1) continue;
      const entries = byIndex.get(index) || [];
      entries.push(take);
      byIndex.set(index, entries);
    }
    for (const index of [...byIndex.keys()].sort((a, b) => a - b)) {
      const group = doc.createElement("article");
      group.className = "h3p-clip";
      const title = doc.createElement("strong");
      title.textContent = `Clip ${index}`;
      group.appendChild(title);
      for (const take of byIndex.get(index)) {
        const row = doc.createElement("div");
        row.className = "h3p-take";
        const label = doc.createElement("span");
        const isApproved = approved.some((item) => item.basename === take.basename);
        const isPending = pending?.basename === take.basename;
        label.textContent = `Take ${take.take}${isApproved ? " · approved" : isPending ? " · pending" : ""}`;
        row.append(label);
        if (index === approved.length + 1 && !isPending) {
          row.append(button(doc, "Select", () => this.act("/select-take", {
            index: take.index,
            take: take.take,
          })));
        }
        if (index <= approved.length) {
          row.append(button(doc, "Branch", () => this.branchDialog(index, take.take)));
        }
        group.appendChild(row);
      }
      this.timeline.appendChild(group);
    }

    this.actions.replaceChildren();
    if (pending) {
      this.actions.append(
        button(doc, "Approve", () => this.act("/approve"), "primary"),
        button(doc, "Reject", () => this.act("/reject"), "danger"),
      );
    }
    if (approved.length) {
      this.actions.append(button(doc, "Reopen last", () => this.act("/reopen")));
    }
    const autoLabel = state.auto_approve ? "Disable auto-approve" : "Enable auto-approve";
    this.actions.append(button(doc, autoLabel, () => this.act("/auto-approve", {
      enabled: !state.auto_approve,
    })));
  }
}

const panel = new H3ProjectPanel();

comfy.ui.addSidebarTab({
  id: PANEL_ID,
  title: "H3 Projects",
  icon: "icon-[lucide--film]",
  tooltip: "Review and manage MiniMax H3 continuation projects",
  render(container) { void panel.mount(container); },
  destroy() { panel.destroy(); },
});

comfy.commands.register({
  id: "H3ProjectSuite.Refresh",
  label: "H3 Projects: Refresh",
  run: () => panel.refresh(),
});
