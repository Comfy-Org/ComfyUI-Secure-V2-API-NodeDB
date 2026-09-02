import { comfy } from '/comfy/api/v2.js';

const LAST_SEED_BUTTON_LABEL = '🎲 Randomize / ♻️ Last Queued Seed';
const SEED_BEHAVIOR_RANDOMIZE = 'Randomize';
const SEED_BEHAVIOR_INCREMENT = 'Increment';
const SEED_BEHAVIOR_DECREMENT = 'Decrement';

const NODE_WIDGET_MAP = {
    "KSampler (Efficient)": "seed",
    "KSampler Adv. (Efficient)": "noise_seed",
    "KSampler SDXL (Eff.)": "noise_seed",
    "Noise Control Script": "seed",
    "HighRes-Fix Script": "seed",
    "Tiled Upscaler Script": "seed"
};

const SPECIFIC_WIDTH = 325; // Set to desired width

function setNodeWidthForMappedTitles(node) {
     if (NODE_WIDGET_MAP[node.comfyClass]) {
        node.setSize({ width: SPECIFIC_WIDTH, height: node.getSize().height });
    }
}

class SeedControl {
    constructor(node, seedName) {
        this.lastSeed = -1;
        this.serializedCtx = {};
        this.node = node;
        this.seedBehavior = 'fixed'; // Default behavior
        // A widget's name is its identity and cannot be reassigned, so the
        // button's text is changed with setLabel() and mirrored here — the
        // callback below compares against the label, and there is no getLabel().
        this.buttonLabel = LAST_SEED_BUTTON_LABEL;

        let controlAfterGenerateIndex;

        for (const [i, name] of this.node.widgets.names().entries()) {
            if (name === seedName) {
                this.seedWidget = this.node.widgets.get(name);
            } else if (name === 'control_after_generate') {
                controlAfterGenerateIndex = i;
                this.node.widgets.remove(name);
            }
        }

        if (!this.seedWidget) {
            throw new Error('Something\'s wrong; expected seed widget');
        }

        this.lastSeedButton = this.node.widgets.add({
            type: "button",
            name: LAST_SEED_BUTTON_LABEL,
            value: null,
            options: { width: 50, serialize: false }
        });
        this.lastSeedButton.on('activate', () => {
            const isValidValue = Number.isInteger(this.seedWidget.getValue()) && this.seedWidget.getValue() >= min && this.seedWidget.getValue() <= max;

            // Special case: if the current label is the default and seed value is -1
            if (this.buttonLabel === LAST_SEED_BUTTON_LABEL && this.seedWidget.getValue() == -1) {
                return; // Do nothing and return early
            }

            if (isValidValue && this.seedWidget.getValue() != -1) {
                this.lastSeed = this.seedWidget.getValue();
                this.seedWidget.setValue(-1);
            } else if (this.lastSeed !== -1) {
                this.seedWidget.setValue(this.lastSeed);
            } else {
                this.seedWidget.setValue(-1); // Set to -1 if the label didn't update due to a seed value issue
            }

            if (isValidValue) {
                this.updateButtonLabel(); // Update the button label to reflect the change
            }
        });

        setNodeWidthForMappedTitles(node);
        if (controlAfterGenerateIndex !== undefined) {
            this.node.widgets.move(LAST_SEED_BUTTON_LABEL, controlAfterGenerateIndex);
            setNodeWidthForMappedTitles(node);
        }

        const max = Math.min(1125899906842624, this.seedWidget.getOptions().max);
        const min = Math.max(-1125899906842624, this.seedWidget.getOptions().min);
        const range = (max - min) / (this.seedWidget.getOptions().step / 10);

        this.seedWidget.on('beforeSerialize', (e) => {
            // Only the queued payload is substituted. The widget is left alone,
            // so the sentinel the user typed stays on screen and the saved
            // workflow keeps it too.
            if (e.context !== 'prompt') {
                return;
            }

            // Check if the button is disabled
            if (this.lastSeedButton.isDisabled()) {
                return;
            }

            const currentSeed = this.seedWidget.getValue();
            this.serializedCtx = {
                wasSpecial: currentSeed == -1,
            };

            if (this.serializedCtx.wasSpecial) {
                switch (this.seedBehavior) {
                    case 'increment':
                        this.serializedCtx.seedUsed = this.lastSeed + 1;
                        break;
                    case 'decrement':
                        this.serializedCtx.seedUsed = this.lastSeed - 1;
                        break;
                    default:
                        this.serializedCtx.seedUsed = Math.floor(Math.random() * range) * (this.seedWidget.getOptions().step / 10) + min;
                        break;
                }

            // Ensure the seed value is an integer and remains within the accepted range
            this.serializedCtx.seedUsed = Number.isInteger(this.serializedCtx.seedUsed) ? Math.min(Math.max(this.serializedCtx.seedUsed, min), max) : this.seedWidget.getValue();

            } else {
                this.serializedCtx.seedUsed = this.seedWidget.getValue();
            }

            // Update the last seed value and the button's label to show the current seed value
            this.lastSeed = this.serializedCtx.seedUsed;
            this.updateButtonLabel();

            e.setSerializedValue(this.serializedCtx.seedUsed);
        });
    }

    setBehavior(behavior) {
        this.seedBehavior = behavior;

        // Capture the current seed value as lastSeed and then set the seed widget value to -1
        if (this.seedWidget.getValue() != -1) {
            this.lastSeed = this.seedWidget.getValue();
            this.seedWidget.setValue(-1);
        }

        this.updateButtonLabel();
    }

    updateButtonLabel() {

        switch (this.seedBehavior) {
            case 'increment':
                this.buttonLabel = `➕ Increment / ♻️ ${this.lastSeed === -1 ? "Last Queued Seed" : this.lastSeed}`;
                break;
            case 'decrement':
                this.buttonLabel = `➖ Decrement / ♻️ ${this.lastSeed === -1 ? "Last Queued Seed" : this.lastSeed}`;
                break;
            default:
                this.buttonLabel = `🎲 Randomize / ♻️ ${this.lastSeed === -1 ? "Last Queued Seed" : this.lastSeed}`;
                break;
        }
        this.lastSeedButton.setLabel(this.buttonLabel);
    }

}

// The SeedControl instance used to be hung on the node as `node.seedControl`.
// A handle holds no arbitrary properties, so it lives here keyed by node id.
const seedControls = new Map();

// V2 node handles deliberately do not accept arbitrary pack properties. Keep
// the cross-module state in this realm and expose only the lookup the widget
// visibility module needs.
export function getSeedControl(node) {
    return seedControls.get(node.id);
}

comfy.defs.extend(Object.keys(NODE_WIDGET_MAP), (b) => {
    b.onCreated((node) => {
        const seedControl = new SeedControl(node, NODE_WIDGET_MAP[node.comfyClass]);
        seedControl.seedWidget.setValue(-1);
        seedControls.set(node.id, seedControl);
    });

    b.onRemoved((node) => {
        seedControls.delete(node.id);
    });

    b.addMenuItem({
        label: "🌱 Seed behavior...",
        order: 4,
        // Check conditions before showing the seed behavior option
        when: (node) => {
            if (node.comfyClass === "Noise Control Script") {
                // Check for 'add_seed_noise' widget being false
                const addSeedNoiseWidget = node.widgets.get('add_seed_noise');
                return !addSeedNoiseWidget || Boolean(addSeedNoiseWidget.getValue());
            }
            if (node.comfyClass === "HighRes-Fix Script") {
                // Check for 'use_same_seed' widget being true
                const useSameSeedWidget = node.widgets.get('use_same_seed');
                return !useSameSeedWidget || !useSameSeedWidget.getValue();
            }
            return true;
        },
        items: [
            { label: "🎲 Randomize", run: (node) => seedControls.get(node.id).setBehavior('randomize') },
            { label: "➕ Increment", run: (node) => seedControls.get(node.id).setBehavior('increment') },
            { label: "➖ Decrement", run: (node) => seedControls.get(node.id).setBehavior('decrement') }
        ]
    });
});
