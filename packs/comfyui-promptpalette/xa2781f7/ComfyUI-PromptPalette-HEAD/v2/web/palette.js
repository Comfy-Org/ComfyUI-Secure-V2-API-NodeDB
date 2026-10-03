import { Line } from "./line.js";
import { TextLines } from "./text_lines.js";


const COLORS = {
  text: "var(--text-primary)",
  muted: "color-mix(in srgb, var(--text-primary) 55%, transparent)",
  control: "var(--component-node-widget-background)",
  controlHover: "var(--component-node-widget-background-hovered)",
};


function style(element, values) {
  Object.assign(element.style, values);
  return element;
}


function button(doc, label, title, action) {
  const element = doc.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.title = title;
  element.setAttribute("aria-label", title);
  style(element, {
    border: "0",
    borderRadius: "4px",
    background: COLORS.control,
    color: COLORS.text,
    cursor: "pointer",
    minWidth: "22px",
    height: "22px",
    padding: "0 5px",
  });
  const enter = () => { element.style.background = COLORS.controlHover; };
  const leave = () => { element.style.background = COLORS.control; };
  element.addEventListener("mouseenter", enter);
  element.addEventListener("mouseleave", leave);
  element.addEventListener("click", action);
  return element;
}


export function normalizeConfig(delimiter, lineBreak) {
  if (!["comma", "space", "none"].includes(delimiter.getValue())) {
    delimiter.setValue("comma");
  }
  if (typeof lineBreak.getValue() !== "boolean") {
    lineBreak.setValue(true);
  }
}


export class PromptPaletteView {
  #container;
  #doc;
  #text;
  #delimiter;
  #lineBreak;
  #root;
  #rows;
  #empty;
  #toggle;
  #editing = false;
  #destroyed = false;
  #unsubscribers = [];

  constructor(container, text, delimiter, lineBreak) {
    this.#container = container;
    this.#doc = container.ownerDocument;
    this.#text = text;
    this.#delimiter = delimiter;
    this.#lineBreak = lineBreak;

    this.#root = style(this.#doc.createElement("div"), {
      boxSizing: "border-box",
      color: COLORS.text,
      display: "flex",
      flexDirection: "column",
      fontSize: "14px",
      gap: "6px",
      height: "100%",
      minHeight: "120px",
      padding: "2px",
      width: "100%",
    });
    this.#root.setAttribute("data-prompt-palette", "");

    this.#rows = style(this.#doc.createElement("div"), {
      display: "flex",
      flex: "1 1 auto",
      flexDirection: "column",
      gap: "4px",
      minHeight: "0",
      overflow: "auto",
    });
    this.#rows.setAttribute("data-role", "rows");

    this.#empty = style(this.#doc.createElement("div"), {
      alignItems: "center",
      color: COLORS.muted,
      display: "none",
      flex: "1 1 auto",
      justifyContent: "center",
    });
    this.#empty.setAttribute("data-role", "empty");
    this.#empty.textContent = "No Text";

    this.#toggle = button(this.#doc, "Edit", "Edit prompt palette", () => {
      this.setEditing(!this.#editing);
    });
    this.#toggle.style.width = "100%";
    this.#toggle.setAttribute("data-action", "toggle-edit");

    this.#root.append(this.#rows, this.#empty, this.#toggle);
    this.#container.replaceChildren(this.#root);
    this.#unsubscribers.push(this.#text.on("change", () => this.renderRows()));
    this.setEditing(false);
  }

  get editing() {
    return this.#editing;
  }

  setEditing(editing) {
    if (this.#destroyed) return;
    this.#editing = Boolean(editing);
    this.#text.setHidden(this.#editing ? false : true);
    this.#delimiter.setHidden(this.#editing ? false : true);
    this.#lineBreak.setHidden(this.#editing ? false : true);
    this.#toggle.textContent = this.#editing ? "Save" : "Edit";
    this.#toggle.title = this.#editing ? "Save prompt palette" : "Edit prompt palette";
    this.#toggle.setAttribute("aria-label", this.#toggle.title);
    this.renderRows();
  }

  renderRows() {
    if (this.#destroyed) return;
    this.#rows.replaceChildren();
    if (this.#editing) {
      this.#rows.style.display = "none";
      this.#empty.style.display = "none";
      return;
    }

    const value = this.#text.getValue();
    const text = typeof value === "string" ? value : "";
    if (!text.trim()) {
      this.#rows.style.display = "none";
      this.#empty.style.display = "flex";
      return;
    }

    this.#rows.style.display = "flex";
    this.#empty.style.display = "none";
    text.split("\n").forEach((raw, index) => {
      this.#rows.append(this.#createRow(raw, index));
    });
  }

  #createRow(raw, index) {
    const line = new Line(raw);
    const row = style(this.#doc.createElement("div"), {
      alignItems: "center",
      display: "flex",
      gap: "8px",
      minHeight: "24px",
    });
    row.setAttribute("data-line-index", String(index));
    if (!line.hasPhraseText()) {
      row.setAttribute("data-empty-line", "");
      return row;
    }

    const toggle = button(
      this.#doc,
      line.commentedOut ? "" : "✓",
      line.commentedOut ? "Enable phrase" : "Disable phrase",
      () => this.#mutate(index, "comment"),
    );
    toggle.setAttribute("data-action", "toggle-comment");
    toggle.style.border = `1px solid ${COLORS.muted}`;

    const phrase = style(this.#doc.createElement("span"), {
      flex: "1 1 auto",
      fontWeight: line.weight === 1.0 ? "normal" : "bold",
      opacity: line.commentedOut ? "0.4" : "1",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "pre",
    });
    phrase.setAttribute("data-role", "phrase");
    phrase.textContent = line.displayText;
    row.append(toggle, phrase);

    const controls = style(this.#doc.createElement("div"), {
      alignItems: "center",
      display: "inline-flex",
      gap: "4px",
      marginLeft: "auto",
    });
    if (line.weight !== 1.0) {
      const weight = this.#doc.createElement("span");
      weight.setAttribute("data-role", "weight");
      weight.textContent = line.weightText;
      weight.style.minWidth = "32px";
      weight.style.textAlign = "right";
      controls.append(weight);
    }
    const minus = button(
      this.#doc, "−", "Decrease phrase weight", () => this.#mutate(index, -0.1)
    );
    minus.setAttribute("data-action", "weight-minus");
    const plus = button(
      this.#doc, "+", "Increase phrase weight", () => this.#mutate(index, 0.1)
    );
    plus.setAttribute("data-action", "weight-plus");
    controls.append(minus, plus);
    row.append(controls);
    return row;
  }

  #mutate(index, action) {
    if (this.#destroyed || this.#editing) return;
    const value = this.#text.getValue();
    const lines = new TextLines(typeof value === "string" ? value : "");
    if (action === "comment") {
      lines.toggleCommentAt(index);
    } else {
      lines.adjustWeightAt(index, action);
    }
    this.#text.setValue(lines.toString());
    // WidgetHandle change normally redraws synchronously. Rebuilding here also
    // covers minimal hosts that commit without immediately dispatching it.
    this.renderRows();
  }

  destroy() {
    if (this.#destroyed) return;
    this.#destroyed = true;
    for (const unsubscribe of this.#unsubscribers.splice(0)) unsubscribe();
    this.#text.setHidden(false);
    this.#delimiter.setHidden(false);
    this.#lineBreak.setHidden(false);
    this.#container.replaceChildren();
  }
}
