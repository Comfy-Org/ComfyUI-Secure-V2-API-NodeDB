// Opt-in template source. Own routes and core-command interception are held.
const NEW_TAB_TEMPLATE_DEFAULT = 'Default';
const NEW_TAB_ZOOM_LEVEL = 0.8;

/** Retain the native mutation, including existing offset and extra fields. */
export function prepareTemplateForNewTab(workflowData) {
  if (!workflowData.extra) workflowData.extra = {};
  if (!workflowData.extra.ds) workflowData.extra.ds = { offset: [0, 0], scale: 1 };
  workflowData.extra.ds.scale = NEW_TAB_ZOOM_LEVEL;
  return workflowData;
}

/** A fresh instance of the exact native blank graph on every invocation. */
export function blankTemplateWorkflow() {
  return {
    last_node_id: 0, last_link_id: 0, nodes: [], links: [], groups: [],
    config: {}, extra: {}, version: 0.4,
  };
}

/**
 * Native option cache and selected-template loading through pack-owned URLs.
 * No route or command is registered by construction. The existing settings
 * adapter may declare options after loadWorkflowOptions resolves; live option
 * refresh and original command interception remain separate API gaps.
 * @param {Comfy} comfy
 */
export function createTemplateWorkflows(comfy) {
  let workflowOptions = [NEW_TAB_TEMPLATE_DEFAULT];
  let workflowOptionsFull = [{ value: 'Default', label: 'Default (Blank)', path: null }];
  let workflowOptionsLoaded = false;

  const loadWorkflowOptions = async () => {
    if (workflowOptionsLoaded) return;
    try {
      const response = await comfy.backend.ownFetch('/example-workflows');
      const data = await response.json();
      if (data.success && data.workflows) {
        workflowOptionsFull = data.workflows;
        workflowOptions = data.workflows.map(workflow => workflow.label);
        workflowOptionsLoaded = true;
      }
    } catch (error) {
      console.warn('LoRA Manager: Failed to fetch workflow options', error);
    }
  };

  const getWorkflowOptions = () => workflowOptions;

  const loadTemplateWorkflow = async templateName => {
    if (!templateName || templateName === NEW_TAB_TEMPLATE_DEFAULT) return null;
    try {
      const workflow = workflowOptionsFull.find(workflow => workflow.label === templateName);
      if (workflow && workflow.value) {
        const response = await comfy.backend.ownFetch(
          `/example-workflows/${encodeURIComponent(workflow.value)}`);
        const data = await response.json();
        if (data.success && data.workflow) return data.workflow;
      }
    } catch (error) {
      console.error('LoRA Manager: Failed to load template workflow', error);
    }
    return null;
  };

  // Return the native command branch's graph; the caller must supply the
  // admitted native command lifecycle. An unrelated new command is not parity.
  const workflowForNewTab = async templateName => {
    if (templateName && templateName !== NEW_TAB_TEMPLATE_DEFAULT) {
      const data = await loadTemplateWorkflow(templateName);
      if (data) return prepareTemplateForNewTab(data);
    }
    return blankTemplateWorkflow();
  };

  return { loadWorkflowOptions, getWorkflowOptions, loadTemplateWorkflow, workflowForNewTab };
}
