// Conversion checkpoint only. Legacy web/comfyui and manager pages are not loaded.
// Pure marker transformations are tested independently; typed menu wiring pending.
export { ROLES, markState, clearState } from './marker_logic.js';
// Not auto-registered until backend schema and loader-delivery integration pass.
export { registerTriggerWords } from './trigger_widget.js';
// Caller can register this tested topology adapter independently of the still
// unresolved Trigger beforeSerialize and manager-wide settings/UI contracts.
export { registerStackInputs } from './stack_inputs.js';

// Prompt topology candidate; opt-in until original-ID registration/browser proof.
export { registerPromptInputs } from './prompt_inputs.js';

// Marker menu candidate; manager registry change consumer remains pending.
export { registerNodeMarkers } from './node_markers.js';

// Whole settings projection; template command lifecycle and browser persistence pending.
export { registerManagerSettings, createManagerPreferences, setManagerPreference } from './manager_settings.js';

// Registry descriptions/updates only; original route and workflow loading remain held.
export { describeWorkflowNodes, appendWorkflowWidgetValue, applyWorkflowWidgetUpdate, registerWorkflowRegistryEvents } from './workflow_registry.js';

// Template option/graph source only; own routes/core command/browser proof pending.
export { createTemplateWorkflows, prepareTemplateForNewTab, blankTemplateWorkflow } from './template_workflows.js';

// Save Image frontend source; serializer/browser/backend certification pending.
export { registerSaveImageExtraOutput } from './save_image_extra_output.js';

// Debug Metadata display only; native collector and actual browser proof pending.
export { registerMetadataDisplay } from './metadata_display.js';

// Create Hook selection/topology only; actual hook factory and browser proof held.
export { registerCreateHookLora } from './create_hook_lora.js';
