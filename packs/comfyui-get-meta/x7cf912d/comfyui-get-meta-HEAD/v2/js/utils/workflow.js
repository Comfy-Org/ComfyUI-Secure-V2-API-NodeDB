"use strict";

/**
 * Parse bounded workflow/prompt data without consulting LiteGraph globals.
 * `titleForType` may be backed by `comfy.defs.get(type)?.title` when a caller
 * needs a display title; the parser itself remains inert and host-independent.
 */
export function parseWorkflow(workflow, prompt, titleForType = (type) => type) {
  const result = [];
  const workflowNodes = Array.isArray(workflow?.nodes)
    ? workflow.nodes.slice(0, 4096)
    : [];
  const byId = new Map(workflowNodes.map((node) => [String(node?.id), node]));

  for (const node of workflowNodes) {
    if (!node || node.type !== "Note") continue;
    result.push({
      id: node.id,
      title: node.title || titleForType("Note"),
      type: "Note",
      values: { text: Array.isArray(node.widgets_values) ? node.widgets_values[0] : "" },
    });
  }

  if (prompt && typeof prompt === "object" && !Array.isArray(prompt)) {
    for (const [key, value] of Object.entries(prompt).slice(0, 4096)) {
      if (!value || typeof value !== "object" || Array.isArray(value)) continue;
      const node = byId.get(String(key));
      const type = String(value.class_type || node?.type || "");
      result.push({
        id: /^\d+$/.test(key) ? Number.parseInt(key, 10) : key,
        title: node?.title || titleForType(type),
        type,
        values: value.inputs && typeof value.inputs === "object"
          ? value.inputs
          : {},
      });
    }
  }

  result.sort((a, b) => String(a.id).localeCompare(String(b.id), undefined, {
    numeric: true,
  }));
  return result;
}
