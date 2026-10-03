import { comfy } from "/comfy/api/v2.js";

const NODE_TYPE = "Calculator";
const BUTTONS = [
  "7", "8", "9", "/",
  "4", "5", "6", "*",
  "1", "2", "3", "-",
  "0", ".", "C", "+",
  "=",
];
const states = new Map();

function nodeKey(node) {
  return `${node.graphId ?? "root"}:${node.id}`;
}

function style(element, values) {
  Object.assign(element.style, values);
  return element;
}

function listen(state, element, type, listener) {
  element.addEventListener(type, listener);
  state.unsubscribers.push(() => element.removeEventListener(type, listener));
}

function arithmetic(expression) {
  const source = expression.replace(/[^0-9+\-*/.]/g, "");
  if (!source || source.includes("++") || source.includes("--")) {
    throw new Error("Invalid expression");
  }

  let position = 0;
  const number = () => {
    const match = /^(?:\d+(?:\.\d*)?|\.\d+)/.exec(source.slice(position));
    if (!match) throw new Error("Number expected");
    position += match[0].length;
    return Number(match[0]);
  };
  const unary = () => {
    if (source[position] === "+") {
      position += 1;
      return unary();
    }
    if (source[position] === "-") {
      position += 1;
      return -unary();
    }
    return number();
  };
  const product = () => {
    let value = unary();
    while (source[position] === "*" || source[position] === "/") {
      const operator = source[position++];
      const right = unary();
      value = operator === "*" ? value * right : value / right;
    }
    return value;
  };
  const sum = () => {
    let value = product();
    while (source[position] === "+" || source[position] === "-") {
      const operator = source[position++];
      const right = product();
      value = operator === "+" ? value + right : value - right;
    }
    return value;
  };

  const result = sum();
  if (position !== source.length) throw new Error("Unexpected token");
  return result;
}

function updateDisplay(state, value) {
  const text = value || "0";
  state.display.textContent = text.length > 15 ? text.substring(0, 15) : text;
}

function press(state, label) {
  if (state.disposed) return;
  if (label === "C") {
    state.expression = "";
    state.isResult = false;
    updateDisplay(state, "0");
    return;
  }
  if (label === "=") {
    try {
      const result = arithmetic(state.expression);
      state.expression = result.toString();
      state.isResult = true;
      updateDisplay(state, state.expression);
    } catch (_error) {
      updateDisplay(state, "Error");
      state.expression = "";
    }
    return;
  }

  if (state.isResult) {
    state.expression = Number.isNaN(Number(label))
      ? state.expression + label
      : label;
    state.isResult = false;
  } else {
    state.expression += label;
  }
  updateDisplay(state, state.expression);
}

function buildCalculator(state, doc) {
  const container = style(doc.createElement("div"), {
    display: "flex",
    flexDirection: "column",
    gap: "5px",
    padding: "10px",
    backgroundColor: "#222",
    borderRadius: "8px",
    width: "220px",
    boxSizing: "border-box",
  });
  container.setAttribute("aria-label", "Calculator");

  const display = style(doc.createElement("output"), {
    backgroundColor: "#444",
    color: "#0f0",
    padding: "10px",
    textAlign: "right",
    fontSize: "20px",
    fontFamily: "monospace",
    borderRadius: "4px",
    marginBottom: "5px",
    minHeight: "44px",
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
    overflow: "hidden",
    boxSizing: "border-box",
  });
  display.setAttribute("aria-live", "polite");
  display.setAttribute("aria-label", "Calculator display");
  state.display = display;
  updateDisplay(state, "0");
  container.append(display);

  const grid = style(doc.createElement("div"), {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: "5px",
  });
  for (const label of BUTTONS) {
    const button = style(doc.createElement("button"), {
      padding: "15px 5px",
      cursor: "pointer",
      border: "none",
      borderRadius: "4px",
      backgroundColor: Number.isNaN(Number(label)) && label !== "." ? "#555" : "#777",
      color: "white",
      fontSize: "16px",
      fontWeight: "bold",
    });
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-label", label === "=" ? "Calculate" : label === "C" ? "Clear" : label);
    if (label === "=") {
      button.style.gridColumn = "span 4";
      button.style.backgroundColor = "#447744";
    }
    listen(state, button, "click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      press(state, label);
    });
    state.buttons.set(label, button);
    grid.append(button);
  }
  container.append(grid);
  return container;
}

function dispose(state) {
  if (!state || state.disposed) return;
  state.disposed = true;
  for (const unsubscribe of state.unsubscribers.splice(0)) unsubscribe();
  if (states.get(state.key) === state) states.delete(state.key);
  state.buttons.clear();
  state.display = undefined;
}

function install(node) {
  const key = nodeKey(node);
  dispose(states.get(key));
  const state = {
    key,
    expression: "",
    isResult: false,
    display: undefined,
    buttons: new Map(),
    unsubscribers: [],
    disposed: false,
  };
  states.set(key, state);
  node.widgets.mount({
    name: "calc_ui",
    height: 330,
    serialize: false,
    sendToPrompt: false,
    render(container) {
      container.replaceChildren(buildCalculator(state, container.ownerDocument));
    },
    destroy() {
      dispose(state);
    },
  });
  node.setSizeConstraints({ minWidth: 240, minHeight: 360 });
}

comfy.defs.extend(NODE_TYPE, (builder) => {
  builder.onCreated(install);
  builder.onRemoved((node) => dispose(states.get(nodeKey(node))));
});
