import { comfy } from '/comfy/api/v2.js';
import {$t} from '../common/i18n.js'
import {CheckpointInfoDialog, LoraInfoDialog} from "../common/model.js";

const loaders = ['easy fullLoader', 'easy a1111Loader', 'easy comfyLoader', 'easy kolorsLoader', 'easy hunyuanDiTLoader', 'easy pixArtLoader']
const preSampling = ['easy preSampling', 'easy preSamplingAdvanced', 'easy preSamplingDynamicCFG', 'easy preSamplingNoiseIn', 'easy preSamplingCustom', 'easy preSamplingLayerDiffusion', 'easy fullkSampler']
const kSampler = ['easy kSampler', 'easy kSamplerTiled', 'easy kSamplerInpainting', 'easy kSamplerDownscaleUnet', 'easy kSamplerLayerDiffusion']
const controlnet = ['easy controlnetLoader', 'easy controlnetLoaderADV', 'easy controlnetLoader++', 'easy instantIDApply', 'easy instantIDApplyADV']
const ipadapter = ['easy ipadapterApply', 'easy ipadapterApplyADV', 'easy ipadapterApplyFaceIDKolors', 'easy ipadapterStyleComposition', 'easy ipadapterApplyFromParams', 'easy pulIDApply', 'easy pulIDApplyADV']
const positive_prompt = ['easy positive', 'easy wildcards']
const imageNode = ['easy loadImageBase64', 'LoadImage', 'LoadImageMask']
const inpaint = ['easy applyBrushNet', 'easy applyPowerPaint', 'easy applyInpaint']
const widgetMapping = {
    "positive_prompt":{
        "text": "positive",
        "positive": "text"
    },
    "loaders":{
        "ckpt_name": "ckpt_name",
        "vae_name": "vae_name",
        "clip_skip": "clip_skip",
        "lora_name": "lora_name",
        "resolution": "resolution",
        "empty_latent_width": "empty_latent_width",
        "empty_latent_height": "empty_latent_height",
        "positive": "positive",
        "negative": "negative",
        "batch_size": "batch_size",
        "a1111_prompt_style": "a1111_prompt_style"
    },
    "preSampling":{
        "steps": "steps",
        "cfg": "cfg",
        "cfg_scale_min": "cfg",
        "sampler_name": "sampler_name",
        "scheduler": "scheduler",
        "denoise": "denoise",
        "seed_num": "seed_num",
        "seed": "seed"
    },
    "kSampler":{
        "image_output": "image_output",
        "save_prefix": "save_prefix",
        "link_id": "link_id"
    },
    "controlnet":{
        "control_net_name":"control_net_name",
        "strength": ["strength", "cn_strength"],
        "scale_soft_weights": ["scale_soft_weights","cn_soft_weights"],
        "cn_strength": ["strength", "cn_strength"],
        "cn_soft_weights": ["scale_soft_weights","cn_soft_weights"],
    },
    "ipadapter":{
        "preset":"preset",
        "lora_strength": "lora_strength",
        "provider": "provider",
        "weight":"weight",
        "weight_faceidv2": "weight_faceidv2",
        "start_at": "start_at",
        "end_at": "end_at",
        "cache_mode": "cache_mode",
        "use_tiled": "use_tiled",
        "insightface": "insightface",
        "pulid_file": "pulid_file"
    },
    "load_image":{
        "image":"image",
        "base64_data":"base64_data",
        "channel": "channel"
    },
    "inpaint":{
        "dtype": "dtype",
        "fitting": "fitting",
        "function": "function",
        "scale": "scale",
        "start_at": "start_at",
        "end_at": "end_at"
    }
}
const inputMapping = {
    "loaders":{
        "optional_lora_stack": "optional_lora_stack",
        "positive": "positive",
        "negative": "negative"
    },
    "preSampling":{
        "pipe": "pipe",
        "image_to_latent": "image_to_latent",
        "latent": "latent"
    },
    "kSampler":{
        "pipe": "pipe",
        "model": "model"
    },
    "controlnet":{
        "pipe": "pipe",
        "image": "image",
        "image_kps": "image_kps",
        "control_net": "control_net",
        "positive": "positive",
        "negative": "negative",
        "mask": "mask"
    },
    "positive_prompt":{

    },
    "ipadapter":{
        "model":"model",
        "image":"image",
        "image_style": "image",
        "attn_mask":"attn_mask",
        "optional_ipadapter":"optional_ipadapter"
    },
    "inpaint":{
        "pipe": "pipe",
        "image": "image",
        "mask": "mask"
    }
};

const outputMapping = {
    "loaders":{
        "pipe": "pipe",
        "model": "model",
        "vae": "vae",
        "clip": null,
        "positive": null,
        "negative": null,
        "latent": null,
    },
    "preSampling":{
        "pipe":"pipe"
    },
    "kSampler":{
        "pipe": "pipe",
        "image": "image"
    },
    "controlnet":{
        "pipe": "pipe",
        "positive": "positive",
        "negative": "negative"
    },
    "positive_prompt":{
        "text": "positive",
        "positive": "text"
    },
    "load_image":{
        "IMAGE":"IMAGE",
        "MASK": "MASK"
    },
    "ipadapter":{
        "model":"model",
        "tiles":"tiles",
        "masks":"masks",
        "ipadapter":"ipadapter"
    },
    "inpaint":{
        "pipe": "pipe",
    }
};

// 替换节点
function replaceNode(oldNode, newNodeName, type) {
    // graph.add() throws on an unregistered type where LiteGraph.createNode
    // returned null, so the guard moves ahead of it.
    if (!comfy.defs.has(newNodeName)) {
        return;
    }
    const newNode = comfy.graph.add(newNodeName);

    newNode.setPosition(oldNode.getPosition());
    newNode.setSize(oldNode.getSize());

    oldNode.widgets.all().forEach(widget => {
        if(widgetMapping[type][widget.name]){
            const newName = widgetMapping[type][widget.name];
            if (newName) {
                const newWidget = findWidgetByName(newNode, newName);
                if (newWidget) {
                    newWidget.setValue(widget.getValue());
                    if (widget.name == 'seed_num') {
                        // seed_num's paired control_before/after_generate.
                        const from = widget.linked()[0];
                        const to = newWidget.linked()[0];
                        if (from && to) {
                            to.setValue(from.getValue());
                        }
                    }
                    // The old `widget.type == 'converted-widget'` branch called
                    // convertToInput() to recreate a widget's socket on the new
                    // node. Every widget carries its own socket now, so the
                    // branch is unreachable and its helpers are gone with it.
                }
            }
        }

    });

    if(oldNode.inputs){
        // `inputMapping[type] &&` is new, matching the outputs loop below.
        // inputMapping has no 'load_image' entry, and node.inputs now carries a
        // slot for every widget, so a connected LoadImage input reaches a
        // lookup on undefined that the legacy slot-less node never could.
        oldNode.inputs.all().forEach((input, index) => {
            if (input && input.isConnected && inputMapping[type] && inputMapping[type][input.name]) {
                const newInputName = inputMapping[type][input.name];
                // If the new node does not have this output, skip
                if (newInputName === null) {
                    return;
                }
                const newInput = newNode.inputs.byName(newInputName);
                if (newInput) {
                    const source = input.source();
                    const originOutput = source && comfy.graph.node(source.nodeId)?.outputs.at(source.outputIndex);
                    if (originOutput) {
                        originOutput.connectTo(newNode.id, {index: newInput.index});
                    }
                }
            }
        });
    }

    if(oldNode.outputs){
        oldNode.outputs.all().forEach((output, index) => {
            if (output && output.isConnected && outputMapping[type] && outputMapping[type][output.name]) {
                const newOutputName = outputMapping[type][output.name];
                // If the new node does not have this output, skip
                if (newOutputName === null) {
                    return;
                }
                const newOutput = newNode.outputs.byName(newOutputName);
                if (newOutput) {
                    output.targets().forEach(target => {
                        newOutput.connectTo(target.nodeId, {index: target.inputIndex});
                    });
                }
            }
        });
    }


    // Remove old node
    oldNode.remove();

    // Remove others
    const firstOutput = newNode.outputs.at(0)
    if(newNode.type == 'easy fullkSampler'){
        const link_output = firstOutput && firstOutput.links()[0]
        if(link_output && link_output.targetIndex == 0){
            const node = comfy.graph.node(link_output.targetNodeId)
            if(node){
                node.remove();
            }
        }
    }else if(preSampling.includes(newNode.type)){
        const link_output = firstOutput && firstOutput.links()[0]
        if(!link_output){
            const ksampler = comfy.graph.add('easy kSampler');
            const pos = newNode.getPosition();
            ksampler.setPosition({x: pos.x + newNode.getSize().width + 20, y: pos.y});
            // NB: the slot index is looked up on newNode and used as the
            // ksampler's input index, exactly as the original did.
            const newInput = newNode.inputs.byName('pipe');
            if (newInput) {
                if (firstOutput) {
                    firstOutput.connectTo(ksampler.id, {index: newInput.index});
                }
            }
        }
    }

    // autoHeight
    newNode.setSizeConstraints({autoHeight: true});
}

export function findWidgetByName(node, widgetName) {
    return node.widgets.all().find(widget => typeof widgetName == 'object' ? widgetName.includes(widget.name) : widget.name === widgetName);
}
const addMenu = (content, type, nodes_include, b) => {
    if(type == 'loaders') {
        b.addMenuItem({
            label: $t("💎 View Checkpoint Info..."),
            run: (node) => {
                let name = node.widgets.at(0).getValue();
                if (!name || name == 'None') return
                new CheckpointInfoDialog(name).show('checkpoints', name);
            }
        })
        b.addMenuItem({
            label: $t("💎 View Lora Info..."),
            run: (node) => {
                const widget = node.widgets.get('lora_name')
                let name = widget.getValue();
                if (!name || name == 'None') return
                new LoraInfoDialog(name).show('loras', name);
            }
        })
    }
    // The submenu is fixed at registration, which is enough here: it lists the
    // sibling types minus the one being extended, and b.def.type names that.
    const swapOptions = [];
    nodes_include.map(cate=>{
        if (b.def.type !== cate) {
            swapOptions.push({
                label: `${cate}`,
                run: (node) => replaceNode(node, cate, type)
            });
        }
    })
    b.addMenuItem({
        label: content,
        items: swapOptions
    })
}

// 刷新节点
// Was: remove the node, create a fresh one of the same type, re-home every link
// by hand, then copy the old widget values back — by index off the stale
// `widgets_values` array when it was there, and by walking `newWidget.inputEl`
// when it was not. `graph.replace` is that whole operation: it rebuilds the node
// from the registry, carries position, title, colour, mode, properties and
// widget values across BY NAME, re-makes the links, and does it as one undo step.
// Reloading to the same type is the degenerate case of a swap.
const reloadNode = function (node) {
    comfy.graph.replace(node.id, node.type);
}

comfy.defs.extend(/./, (b) => {
    b.addMenuItem({
        label: $t("🔃 Reload Node"),
        // The entry was `options.unshift(…)`, i.e. first.
        order: -1,
        run: (node) => {
            const selected = comfy.graph.selection();
            const targets = selected.length > 1 ? selected : [node];
            comfy.graph.batch(() => {
                for (const target of targets) {
                    reloadNode(target);
                }
            })
        }
    })
})

// ckptNames
comfy.defs.extend('easy ckptNames', (b) => {
    b.addMenuItem({
        label: $t("💎 View Checkpoint Info..."),
        run: (node) => {
            let name = node.widgets.at(0).getValue();
            if (!name || name == 'None') return
            new CheckpointInfoDialog(name).show('checkpoints', name);
        }
    })
})

// Swap提示词
comfy.defs.extend(positive_prompt, (b) => addMenu("↪️ Swap EasyPrompt", 'positive_prompt', positive_prompt, b))
// Swap加载器
comfy.defs.extend(loaders, (b) => addMenu("↪️ Swap EasyLoader", 'loaders', loaders, b))
// Swap预采样器
comfy.defs.extend(preSampling, (b) => addMenu("↪️ Swap EasyPreSampling", 'preSampling', preSampling, b))
// Swap kSampler
comfy.defs.extend(kSampler, (b) => addMenu("↪️ Swap EasyKSampler", 'preSampling', kSampler, b))
// Swap ControlNet
comfy.defs.extend(controlnet, (b) => addMenu("↪️ Swap EasyControlnet", 'controlnet', controlnet, b))
// Swap IPAdapater
comfy.defs.extend(ipadapter, (b) => addMenu("↪️ Swap EasyAdapater", 'ipadapter', ipadapter, b))
// Swap Image
comfy.defs.extend(imageNode, (b) => addMenu("↪️ Swap LoadImage", 'load_image', imageNode, b))
// Swap inpaint
comfy.defs.extend(inpaint, (b) => addMenu("↪️ Swap InpaintNode", 'inpaint', inpaint, b))
