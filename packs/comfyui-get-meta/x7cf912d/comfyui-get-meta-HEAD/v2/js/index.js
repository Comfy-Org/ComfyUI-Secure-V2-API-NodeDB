"use strict";

import { comfy } from "/comfy/api/v2.js";


export const EXTENSION_NAME = "shinich39.GetMeta";

const META_TYPES = [
  "GetBooleanFromImage",
  "GetIntFromImage",
  "GetFloatFromImage",
  "GetStringFromImage",
  "GetComboFromImage",
  "GetValuesFromImage",
  "GetWorkflowFromImage",
  "GetPromptFromImage",
];

const QUERY_TYPES = [
  "GetBooleanFromImage",
  "GetIntFromImage",
  "GetFloatFromImage",
  "GetStringFromImage",
  "GetComboFromImage",
];

const VALUE_WIDGETS = {
  GetBooleanFromImage: "boolean",
  GetIntFromImage: "int",
  GetFloatFromImage: "float",
  GetStringFromImage: "string",
  GetComboFromImage: "combo",
  GetValuesFromImage: "nodes",
  GetWorkflowFromImage: "workflow",
  GetPromptFromImage: "prompt",
};


function resultRecord(result) {
  const records = result?.raw?.get_meta;
  if (!Array.isArray(records) || records.length !== 1) return undefined;
  const record = records[0];
  if (!record || typeof record !== "object") return undefined;
  if (!META_TYPES.includes(record.node_type)) return undefined;
  return record;
}


function applyExecutedValue(node, result) {
  const record = resultRecord(result);
  if (!record || record.node_type !== node.comfyClass) return;
  const name = VALUE_WIDGETS[node.comfyClass];
  const widget = name ? node.widgets.get(name) : undefined;
  if (widget) widget.setValue(record.value);
}


function queryParts(query) {
  if (typeof query !== "string") return undefined;
  const dot = query.lastIndexOf(".");
  if (dot <= 0 || dot === query.length - 1) return undefined;
  const rawSelector = query.slice(0, dot);
  const match = rawSelector.match(/^(.*?)(\[[0-9]+\])?$/);
  if (!match || !match[1] || match[1].startsWith("#")) return undefined;
  return {
    selector: match[1],
    index: match[2] || "",
    widget: query.slice(dot + 1),
  };
}


function normalizedQuery(query) {
  const parts = queryParts(query);
  if (!parts) return query;
  const matches = comfy.defs.all().filter((definition) => (
    definition.title === parts.selector
  ));
  if (matches.length !== 1) return query;
  return `${matches[0].type}${parts.index}.${parts.widget}`;
}


function normalizeQueriesForRun() {
  const changed = [];
  const nodes = comfy.graph.queryNodes({
    scope: "root-and-subgraphs",
    type: QUERY_TYPES,
  });
  for (const node of nodes) {
    const widget = node.widgets.get("query");
    if (!widget) continue;
    const original = widget.getValue();
    const normalized = normalizedQuery(original);
    if (normalized === original) continue;
    widget.setValue(normalized);
    changed.push({ widget, original, normalized });
  }
  return () => {
    for (const { widget, original, normalized } of changed) {
      if (!widget.isDeleted && widget.getValue() === normalized) {
        widget.setValue(original);
      }
    }
  };
}


comfy.defs.extend(META_TYPES, (builder) => {
  builder.onExecuted(applyExecutedValue);
});

comfy.queue.onBeforeRun(normalizeQueriesForRun);

