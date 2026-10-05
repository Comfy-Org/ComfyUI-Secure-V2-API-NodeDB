import { comfy } from "/comfy/api/v2.js";


const validationCleanup = new WeakMap();


function checkDelimiters(value) {
  const text = typeof value === "string" ? value : "";
  const brackets = [];
  const parentheses = [];
  const unmatchedClosingBrackets = [];
  const unmatchedClosingParentheses = [];

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === "[") brackets.push(index);
    if (character === "]") {
      if (brackets.length === 0) unmatchedClosingBrackets.push(index);
      else brackets.pop();
    }
    if (character === "(") parentheses.push(index);
    if (character === ")") {
      if (parentheses.length === 0) unmatchedClosingParentheses.push(index);
      else parentheses.pop();
    }
  }

  return {
    unmatchedOpeningBrackets: brackets,
    unmatchedClosingBrackets,
    unmatchedOpeningParentheses: parentheses,
    unmatchedClosingParentheses,
  };
}


function formatValidation(value) {
  const result = checkDelimiters(value);
  let message = "";
  if (result.unmatchedOpeningBrackets.length) {
    message += `Unmatched opening bracket at: ${result.unmatchedOpeningBrackets.map((p) => p + 1).join(", ")}. `;
  }
  if (result.unmatchedClosingBrackets.length) {
    message += `Unmatched closing bracket at: ${result.unmatchedClosingBrackets.map((p) => p + 1).join(", ")}. `;
  }
  if (result.unmatchedOpeningParentheses.length) {
    message += `Unmatched opening parenthesis at: ${result.unmatchedOpeningParentheses.map((p) => p + 1).join(", ")}. `;
  }
  if (result.unmatchedClosingParentheses.length) {
    message += `Unmatched closing parenthesis at: ${result.unmatchedClosingParentheses.map((p) => p + 1).join(", ")}. `;
  }
  return message || "All brackets and parentheses are properly matched!";
}


function disposeValidation(node) {
  const dispose = validationCleanup.get(node);
  if (!dispose) return;
  dispose();
  validationCleanup.delete(node);
}


function installValidation(node) {
  disposeValidation(node);
  const textWidget = node.widgets.get("text");
  const infoWidget = node.widgets.get("info_text");
  if (!textWidget || !infoWidget) return;

  infoWidget.setOption("read_only", true);
  infoWidget.setHeight(60);
  const update = (value) => infoWidget.setValue(formatValidation(value));
  update(textWidget.getValue());

  const unsubscribeInteraction = textWidget.on("textInteraction", (event) => {
    if (event.kind === "input" || event.kind === "selection") update(event.value);
  });
  const unsubscribeChange = textWidget.on("change", (value) => update(value));
  validationCleanup.set(node, () => {
    unsubscribeInteraction();
    unsubscribeChange();
  });
}


comfy.defs.extend("RandomizeTextWithCheck", (builder) => {
  builder.onCreated((node) => installValidation(node));
  builder.onConfigured((node) => installValidation(node));
  builder.onRemoved((node) => disposeValidation(node));
});


comfy.defs.extend("ShowText", (builder) => {
  builder.onCreated((node) => {
    node.widgets.get("preview")?.setOption("read_only", true);
  });

  builder.onExecuted((node, result) => {
    const raw = result.raw?.text;
    const text = Array.isArray(raw)
      ? raw.filter((item) => typeof item === "string").join("")
      : typeof raw === "string" ? raw : "";
    if (text) node.widgets.get("preview")?.setValue(text);
  });

  builder.onConnectionsChanged((node, event) => {
    if (event.side === "input" && event.index === 0) {
      node.widgets.get("preview")?.setValue("");
    }
  });
});


export { checkDelimiters, formatValidation, installValidation };
