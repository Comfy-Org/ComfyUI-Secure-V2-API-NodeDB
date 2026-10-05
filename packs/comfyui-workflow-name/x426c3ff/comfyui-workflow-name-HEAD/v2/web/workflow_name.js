import { comfy } from "/comfy/api/v2.js";


export const FALLBACK_NAME = "NO_WORKFLOW_NAME";
const MAX_NAME_CHARS = 512;
const INVALID_FILENAME_CHARS = /[<>:"/\\|?*\x00-\x1f]/g;
const EDGE_CHARS = /^[ ._]+|[ ._]+$/g;


/** Mirror the legacy route's filename policy without a backend round trip. */
export function sanitizeWorkflowName(value) {
  if (typeof value !== "string" || value.length > MAX_NAME_CHARS) return FALLBACK_NAME;
  const basename = value.split("/").at(-1) ?? "";
  const withoutJson = basename.endsWith(".json") ? basename.slice(0, -5) : basename;
  const clean = withoutJson.replace(INVALID_FILENAME_CHARS, "_").replace(EDGE_CHARS, "");
  return clean || FALLBACK_NAME;
}


export function updateWorkflowName(api) {
  const name = sanitizeWorkflowName(api.workflow.current()?.name);
  const nodes = api.graph.queryNodes({
    type: "WorkflowName",
    scope: "root-and-subgraphs",
  });
  for (const node of nodes) node.widgets.get("workflow_name")?.setValue(name);
  return name;
}


export function installWorkflowName(api) {
  return api.queue.onBeforeRun(() => {
    updateWorkflowName(api);
  });
}


installWorkflowName(comfy);
