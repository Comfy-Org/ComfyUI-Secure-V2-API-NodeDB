import { comfy } from '/comfy/api/v2.js';


// Credentials are host-profile-owned in Secure V2 and never enter the guest.
// Preserve the legacy input in saved workflows, but do not present an unused
// workflow-secret control to the user.
comfy.defs.extend(
  (def) => def.type === 'OllamaTool_WebSearch',
  (builder) => {
    builder.hideWidget('ollama_api_key');
  },
);
