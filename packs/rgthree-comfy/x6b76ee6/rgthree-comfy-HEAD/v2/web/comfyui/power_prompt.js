import { comfy } from '/comfy/api/v2.js';
import { extendPowerPrompt } from './base_power_prompt.js';

const POWER_PROMPT = 'Power Prompt (rgthree)';

comfy.defs.extend([
    POWER_PROMPT,
    'Power Prompt - Simple (rgthree)',
    'SDXL Power Prompt - Positive (rgthree)',
    'SDXL Power Prompt - Simple / Negative (rgthree)'
], (builder) => {
    if (builder.def.type === POWER_PROMPT) {
        const currentOutput = builder.def.outputs[0];
        builder.onConfigured((node) => {
            const output = node.outputs.at(0);
            if (output?.type !== 'STRING' || !currentOutput) return;
            output.moveLinksTo({ index: 3 });
            output.modify({
                name: currentOutput.name,
                type: currentOutput.type,
                color: null,
                colorWhenUnconnected: null
            });
        });
    }
    extendPowerPrompt(builder);
});

// REFUSED: replacing node connection-position methods to let a pack choose
// where the renderer places every input and output. The prompt controls,
// connection gating and old-workflow migration do not depend on that layout.
