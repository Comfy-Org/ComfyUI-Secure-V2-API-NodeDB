import { comfy } from '/comfy/api/v2.js';
import { toast} from "../common/toast.js";
import { $t } from '../common/i18n.js';

import { findWidgetByName, toggleWidget, updateNodeHeight} from "../common/utils.js";

// `control_before_generate`/`control_after_generate` were stashed on the widget
// as `last_value`. Handles hold no arbitrary properties, so they live here,
// keyed by node id, and are dropped when the node is removed.
const lastValues = new Map();

const seedNodes = ["easy seed", "easy latentNoisy", "easy wildcards", "easy preSampling", "easy preSamplingAdvanced", "easy preSamplingNoiseIn", "easy preSamplingSdTurbo", "easy preSamplingCascade", "easy preSamplingDynamicCFG", "easy preSamplingLayerDiffusion", "easy fullkSampler", "easy fullCascadeKSampler"]
const loaderNodes = ["easy fullLoader", "easy a1111Loader", "easy comfyLoader", "easy fluxLoader", "easy hunyuanDiTLoader", "easy pixArtLoader"]

function widgetLogic(node, widget) {
	if (widget.name === 'lora_name') {
		if (widget.getValue() === "None") {
			toggleWidget(node, findWidgetByName(node, 'lora_model_strength'))
			toggleWidget(node, findWidgetByName(node, 'lora_clip_strength'))
		} else {
			toggleWidget(node, findWidgetByName(node, 'lora_model_strength'), true)
			toggleWidget(node, findWidgetByName(node, 'lora_clip_strength'), true)
		}
	}
	if (widget.name === 'rescale') {
		let rescale_after_model = findWidgetByName(node, 'rescale_after_model').getValue()
		if (widget.getValue() === 'by percentage' && rescale_after_model) {
			toggleWidget(node, findWidgetByName(node, 'width'))
			toggleWidget(node, findWidgetByName(node, 'height'))
			toggleWidget(node, findWidgetByName(node, 'longer_side'))
			toggleWidget(node, findWidgetByName(node, 'percent'), true)
		} else if (widget.getValue() === 'to Width/Height' && rescale_after_model) {
			toggleWidget(node, findWidgetByName(node, 'width'), true)
			toggleWidget(node, findWidgetByName(node, 'height'), true)
			toggleWidget(node, findWidgetByName(node, 'percent'))
			toggleWidget(node, findWidgetByName(node, 'longer_side'))
		} else if (rescale_after_model) {
			toggleWidget(node, findWidgetByName(node, 'longer_side'), true)
			toggleWidget(node, findWidgetByName(node, 'width'))
			toggleWidget(node, findWidgetByName(node, 'height'))
			toggleWidget(node, findWidgetByName(node, 'percent'))
		}
		updateNodeHeight(node)
	}
	if (widget.name === 'upscale_method') {
		if (widget.getValue() === "None") {
			toggleWidget(node, findWidgetByName(node, 'factor'))
			toggleWidget(node, findWidgetByName(node, 'crop'))
		} else {
			toggleWidget(node, findWidgetByName(node, 'factor'), true)
			toggleWidget(node, findWidgetByName(node, 'crop'), true)
		}
		updateNodeHeight(node)
	}
	if (widget.name === 'image_output') {
	    if (widget.getValue() === 'Sender' || widget.getValue() === 'Sender&Save'){
	        toggleWidget(node, findWidgetByName(node, 'link_id'), true)
	    }else {
	        toggleWidget(node, findWidgetByName(node, 'link_id'))
	    }
		if (widget.getValue() === 'Hide' || widget.getValue() === 'Preview' || widget.getValue() == 'Preview&Choose' || widget.getValue() === 'Sender') {
			toggleWidget(node, findWidgetByName(node, 'save_prefix'))
			toggleWidget(node, findWidgetByName(node, 'output_path'))
			toggleWidget(node, findWidgetByName(node, 'embed_workflow'))
			toggleWidget(node, findWidgetByName(node, 'number_padding'))
			toggleWidget(node, findWidgetByName(node, 'overwrite_existing'))
		} else if (widget.getValue() === 'Save' || widget.getValue() === 'Hide&Save' || widget.getValue() === 'Sender&Save') {
			toggleWidget(node, findWidgetByName(node, 'save_prefix'), true)
			toggleWidget(node, findWidgetByName(node, 'output_path'), true)
			toggleWidget(node, findWidgetByName(node, 'embed_workflow'), true)
			toggleWidget(node, findWidgetByName(node, 'number_padding'), true)
			toggleWidget(node, findWidgetByName(node, 'overwrite_existing'), true)
		}

		if(widget.getValue() === 'Hide' || widget.getValue() === 'Hide&Save'){
			toggleWidget(node, findWidgetByName(node, 'decode_vae_name'))
		}else{
			toggleWidget(node, findWidgetByName(node, 'decode_vae_name'), true)
		}
	}
	if (widget.name === 'add_noise') {
		let control_before_widget = findWidgetByName(node, 'control_before_generate')
		let control_after_widget = findWidgetByName(node, 'control_after_generate')
		if (widget.getValue() === "disable") {
			toggleWidget(node, findWidgetByName(node, 'seed'))
			if(control_before_widget){
				lastValues.set(node.id + ':control_before_generate', control_before_widget.getValue())
				control_before_widget.setValue('fixed')
				toggleWidget(node, control_before_widget)
			}
			if(control_after_widget){
				lastValues.set(node.id + ':control_after_generate', control_after_widget.getValue())
				control_after_widget.setValue('fixed')
				toggleWidget(node, control_after_widget)
			}
		} else {
			toggleWidget(node, findWidgetByName(node, 'seed'), true)
			if(control_before_widget){
				if(lastValues.has(node.id + ':control_before_generate')) control_before_widget.setValue(lastValues.get(node.id + ':control_before_generate'))
				toggleWidget(node, control_before_widget, true)
			}
			if(control_after_widget) {
				if(lastValues.has(node.id + ':control_after_generate')) control_after_widget.setValue(lastValues.get(node.id + ':control_after_generate'))
				toggleWidget(node, findWidgetByName(node, control_after_widget, true))
			}
		}
		updateNodeHeight(node)
	}
	if (widget.name === 'num_loras') {
		let number_to_show = widget.getValue() + 1
		for (let i = 0; i < number_to_show; i++) {
			toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_name'), true)
			if (findWidgetByName(node, 'mode').getValue() === "simple") {
				toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_strength'), true)
				toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_model_strength'))
				toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_clip_strength'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_strength'))
				toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_model_strength'), true)
				toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_clip_strength'), true)
			}
		}
		for (let i = number_to_show; i < 21; i++) {
			toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_name'))
			toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_strength'))
			toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_model_strength'))
			toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_clip_strength'))
		}
		updateNodeHeight(node)
	}
	if (widget.name === 'num_controlnet') {
		let number_to_show = widget.getValue() + 1
		for (let i = 0; i < number_to_show; i++) {
			toggleWidget(node, findWidgetByName(node, 'controlnet_'+i), true)
			toggleWidget(node, findWidgetByName(node, 'controlnet_'+i+'_strength'), true)
			toggleWidget(node, findWidgetByName(node, 'scale_soft_weight_'+i),true)
			if (findWidgetByName(node, 'mode').getValue() === "simple") {
				toggleWidget(node, findWidgetByName(node, 'start_percent_'+i))
				toggleWidget(node, findWidgetByName(node, 'end_percent_'+i))
			} else {
				toggleWidget(node, findWidgetByName(node, 'start_percent_'+i),true)
				toggleWidget(node, findWidgetByName(node, 'end_percent_'+i), true)
			}
		}
		for (let i = number_to_show; i < 10; i++) {
			toggleWidget(node, findWidgetByName(node, 'controlnet_'+i))
			toggleWidget(node, findWidgetByName(node, 'controlnet_'+i+'_strength'))
			toggleWidget(node, findWidgetByName(node, 'start_percent_'+i))
			toggleWidget(node, findWidgetByName(node, 'end_percent_'+i))
			toggleWidget(node, findWidgetByName(node, 'scale_soft_weight_'+i))
		}
		updateNodeHeight(node)
	}

	if (widget.name === 'mode') {
		switch (node.comfyClass) {
			case 'easy loraStack':
				for (let i = 0; i < (findWidgetByName(node, 'num_loras').getValue() + 1); i++) {
					if (widget.getValue() === "simple") {
						toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_strength'), true)
						toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_model_strength'))
						toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_clip_strength'))
					} else {
						toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_strength'))
						toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_model_strength'), true)
						toggleWidget(node, findWidgetByName(node, 'lora_'+i+'_clip_strength'), true)}
				}
				updateNodeHeight(node)
				break
			case 'easy controlnetStack':
				for (let i = 0; i < (findWidgetByName(node, 'num_controlnet').getValue() + 1); i++) {
					if (widget.getValue() === "simple") {
						toggleWidget(node, findWidgetByName(node, 'start_percent_'+i))
						toggleWidget(node, findWidgetByName(node, 'end_percent_'+i))
					} else {
						toggleWidget(node, findWidgetByName(node, 'start_percent_' + i), true)
						toggleWidget(node, findWidgetByName(node, 'end_percent_' + i), true)
					}
				}
				updateNodeHeight(node)
				break
			case 'easy icLightApply':
				if (widget.getValue() === "Foreground") {
					toggleWidget(node, findWidgetByName(node, 'lighting'), true)
					toggleWidget(node, findWidgetByName(node, 'remove_bg'), true)
					toggleWidget(node, findWidgetByName(node, 'source'))
				} else {
					toggleWidget(node, findWidgetByName(node, 'lighting'))
					toggleWidget(node, findWidgetByName(node, 'source'), true)
					toggleWidget(node, findWidgetByName(node, 'remove_bg'))
				}
				updateNodeHeight(node)
				break
		}
	}

	if (widget.name === 'resolution') {
		if(widget.getValue() === "自定义 x 自定义"){
			widget.setValue('width x height (custom)')
		}
		if (widget.getValue() === "自定义 x 自定义" || widget.getValue() === 'width x height (custom)') {
			toggleWidget(node, findWidgetByName(node, 'empty_latent_width'), true)
			toggleWidget(node, findWidgetByName(node, 'empty_latent_height'), true)
		} else {
			toggleWidget(node, findWidgetByName(node, 'empty_latent_width'), false)
			toggleWidget(node, findWidgetByName(node, 'empty_latent_height'), false)
		}
	}
	if (widget.name === 'ratio') {
		if (widget.getValue() === "custom") {
			toggleWidget(node, findWidgetByName(node, 'empty_latent_width'), true)
			toggleWidget(node, findWidgetByName(node, 'empty_latent_height'), true)
		} else {
			toggleWidget(node, findWidgetByName(node, 'empty_latent_width'), false)
			toggleWidget(node, findWidgetByName(node, 'empty_latent_height'), false)
		}
	}
	if (widget.name === 'downscale_mode') {
		const widget_names = ['block_number', 'downscale_factor', 'start_percent', 'end_percent', 'downscale_after_skip', 'downscale_method', 'upscale_method']
		if (widget.getValue() === "None") widget_names.map(name=> toggleWidget(node, findWidgetByName(node, name)))
		else if(widget.getValue() == 'Auto') widget_names.map(name =>toggleWidget(node, findWidgetByName(node, name),name == 'block_number' ? true : false))
		else widget_names.map(name=> toggleWidget(node, findWidgetByName(node, name), true))
		updateNodeHeight(node)
	}

	if (widget.name == 'range_mode'){
		if(widget.getValue() == 'step'){
			toggleWidget(node, findWidgetByName(node, 'step'), true)
			toggleWidget(node, findWidgetByName(node, 'num_steps'))
		}else if(widget.getValue() == 'num_steps'){
			toggleWidget(node, findWidgetByName(node, 'step'))
			toggleWidget(node, findWidgetByName(node, 'num_steps'), true)
		}
		updateNodeHeight(node)
	}

	if (widget.name === 'toggle') {
		// `widget.type = 'toggle'` was a defensive no-op: core already builds a
		// `toggle` widget for a BOOLEAN input (useBooleanWidget), which is what
		// label_on / label_off mean, so only the two labels were ever doing work.
		// LIMITATION: if the backend ever declared `toggle` as something other
		// than BOOLEAN, it is no longer re-presented as a switch — widget type is
		// identity and cannot be reassigned.
		widget.setOption('on', 'Enabled')
		widget.setOption('off', 'Disabled')
	}

	if(widget.name == 'text_combine_mode'){
		if(widget.getValue() == 'replace'){
			toggleWidget(node, findWidgetByName(node, 'replace_text'), true)
		}else{
			toggleWidget(node, findWidgetByName(node, 'replace_text'))
		}
		updateNodeHeight(node)
	}

	if (widget.name === 'conditioning_mode') {
		if (["replace", "concat", "combine"].includes(widget.getValue())) {
			toggleWidget(node, findWidgetByName(node, 'average_strength'))
			toggleWidget(node, findWidgetByName(node, 'old_cond_start'))
			toggleWidget(node, findWidgetByName(node, 'old_cond_end'))
			toggleWidget(node, findWidgetByName(node, 'new_cond_start'))
			toggleWidget(node, findWidgetByName(node, 'new_cond_end'))
		} else if(widget.getValue() == 'average'){
			toggleWidget(node, findWidgetByName(node, 'average_strength'), true)
			toggleWidget(node, findWidgetByName(node, 'old_cond_start'))
			toggleWidget(node, findWidgetByName(node, 'old_cond_end'))
			toggleWidget(node, findWidgetByName(node, 'new_cond_start'))
			toggleWidget(node, findWidgetByName(node, 'new_cond_end'))
		}else if(widget.getValue() == 'timestep'){
			toggleWidget(node, findWidgetByName(node, 'average_strength'))
			toggleWidget(node, findWidgetByName(node, 'old_cond_start'), true)
			toggleWidget(node, findWidgetByName(node, 'old_cond_end'), true)
			toggleWidget(node, findWidgetByName(node, 'new_cond_start'), true)
			toggleWidget(node, findWidgetByName(node, 'new_cond_end'), true)
		}
	}

	if (widget.name === 'preset') {
		const normol_presets = [
            'LIGHT - SD1.5 only (low strength)',
            'STANDARD (medium strength)',
            'VIT-G (medium strength)',
            'PLUS (high strength)', 'PLUS FACE (portraits)',
            'FULL FACE - SD1.5 only (portraits stronger)',
        ]
		const faceid_presets = [
            'FACEID',
            'FACEID PLUS - SD1.5 only',
			'FACEID PLUS KOLORS',
            'FACEID PLUS V2',
			'FACEID PORTRAIT (style transfer)',
			'FACEID PORTRAIT UNNORM - SDXL only (strong)'
        ]
		if(normol_presets.includes(widget.getValue())){
			toggleWidget(node, findWidgetByName(node, 'lora_strength'))
			toggleWidget(node, findWidgetByName(node, 'provider'))
			toggleWidget(node, findWidgetByName(node, 'weight_faceidv2'))
			toggleWidget(node, findWidgetByName(node, 'weight_kolors'))
			toggleWidget(node, findWidgetByName(node, 'use_tiled'), true)
			let use_tiled = findWidgetByName(node, 'use_tiled')
			if(use_tiled && use_tiled.getValue()){
				toggleWidget(node, findWidgetByName(node, 'sharpening'), true)
			}else {
				toggleWidget(node, findWidgetByName(node, 'sharpening'))
			}

		}
		else if(faceid_presets.includes(widget.getValue())){
			toggleWidget(node, findWidgetByName(node, 'weight_faceidv2'), ['FACEID PLUS V2','FACEID PLUS KOLORS'].includes(widget.getValue()) ? true : false);
			toggleWidget(node, findWidgetByName(node, 'weight_kolors'), ['FACEID PLUS KOLORS'].includes(widget.getValue()) ? true : false);
			if(['FACEID PLUS KOLORS','FACEID PORTRAIT (style transfer)','FACEID PORTRAIT UNNORM - SDXL only (strong)'].includes(widget.getValue())){
				toggleWidget(node, findWidgetByName(node, 'lora_strength'), false)
			}
			else{
				toggleWidget(node, findWidgetByName(node, 'lora_strength'), true)
			}
			toggleWidget(node, findWidgetByName(node, 'provider'), true)
			toggleWidget(node, findWidgetByName(node, 'use_tiled'))
			toggleWidget(node, findWidgetByName(node, 'sharpening'))
		}
		updateNodeHeight(node)
	}

	if (widget.name === 'use_tiled') {
		if(widget.getValue())
			toggleWidget(node, findWidgetByName(node, 'sharpening'), true)
		else
			toggleWidget(node, findWidgetByName(node, 'sharpening'))
		updateNodeHeight(node)
	}

	if (widget.name === 'num_embeds') {
		let number_to_show = widget.getValue() + 1
		for (let i = 0; i < number_to_show; i++) {
			toggleWidget(node, findWidgetByName(node, 'weight'+i), true)
		}
		for (let i = number_to_show; i < 6; i++) {
			toggleWidget(node, findWidgetByName(node, 'weight'+i))
		}
		updateNodeHeight(node)
	}

	if (widget.name === 'guider'){
		switch (widget.getValue()){
			case 'Basic':
				toggleWidget(node, findWidgetByName(node, 'cfg'))
				toggleWidget(node, findWidgetByName(node, 'cfg_negative'))
				break
			case 'CFG':
				toggleWidget(node, findWidgetByName(node, 'cfg'),true)
				toggleWidget(node, findWidgetByName(node, 'cfg_negative'))
				break
			case 'IP2P+DualCFG':
			case 'DualCFG':
				toggleWidget(node, findWidgetByName(node, 'cfg'),true)
				toggleWidget(node, findWidgetByName(node, 'cfg_negative'), true)
				break

		}
		updateNodeHeight(node)
	}

	if (widget.name === 'scheduler'){
		if (['karrasADV','exponentialADV','polyExponential'].includes(widget.getValue())){
			toggleWidget(node, findWidgetByName(node, 'sigma_max'), true)
			toggleWidget(node, findWidgetByName(node, 'sigma_min'), true)
			toggleWidget(node, findWidgetByName(node, 'denoise'))
			toggleWidget(node, findWidgetByName(node, 'beta_d'))
			toggleWidget(node, findWidgetByName(node, 'beta_min'))
			toggleWidget(node, findWidgetByName(node, 'eps_s'))
			toggleWidget(node, findWidgetByName(node, 'coeff'))
			if(widget.getValue() != 'exponentialADV'){
				toggleWidget(node, findWidgetByName(node, 'rho'), true)
			}else{
				toggleWidget(node, findWidgetByName(node, 'rho'))
			}
		}else if(widget.getValue() == 'vp'){
			toggleWidget(node, findWidgetByName(node, 'sigma_max'))
			toggleWidget(node, findWidgetByName(node, 'sigma_min'))
			toggleWidget(node, findWidgetByName(node, 'denoise'))
			toggleWidget(node, findWidgetByName(node, 'rho'))
			toggleWidget(node, findWidgetByName(node, 'beta_d'),true)
			toggleWidget(node, findWidgetByName(node, 'beta_min'),true)
			toggleWidget(node, findWidgetByName(node, 'eps_s'),true)
			toggleWidget(node, findWidgetByName(node, 'coeff'))
		}
		else{
			toggleWidget(node, findWidgetByName(node, 'denoise'),true)
			toggleWidget(node, findWidgetByName(node, 'sigma_max'))
			toggleWidget(node, findWidgetByName(node, 'sigma_min'))
			toggleWidget(node, findWidgetByName(node, 'beta_d'))
			toggleWidget(node, findWidgetByName(node, 'beta_min'))
			toggleWidget(node, findWidgetByName(node, 'eps_s'))
			toggleWidget(node, findWidgetByName(node, 'rho'))
			if(widget.getValue() == 'gits') 	toggleWidget(node, findWidgetByName(node, 'coeff'), true)
			else toggleWidget(node, findWidgetByName(node, 'coeff'))
		}
		updateNodeHeight(node)
	}

	if(widget.name === 'inpaint_mode'){
		switch (widget.getValue()){
			case 'normal':
			case 'fooocus_inpaint':
				toggleWidget(node, findWidgetByName(node, 'dtype'))
				toggleWidget(node, findWidgetByName(node, 'fitting'))
				toggleWidget(node, findWidgetByName(node, 'function'))
				toggleWidget(node, findWidgetByName(node, 'scale'))
				toggleWidget(node, findWidgetByName(node, 'start_at'))
				toggleWidget(node, findWidgetByName(node, 'end_at'))
				break
			case 'brushnet_random':
			case 'brushnet_segmentation':
				toggleWidget(node, findWidgetByName(node, 'dtype'), true)
				toggleWidget(node, findWidgetByName(node, 'fitting'))
				toggleWidget(node, findWidgetByName(node, 'function'))
				toggleWidget(node, findWidgetByName(node, 'scale'), true)
				toggleWidget(node, findWidgetByName(node, 'start_at'), true)
				toggleWidget(node, findWidgetByName(node, 'end_at'), true)
				break
			case 'powerpaint':
				toggleWidget(node, findWidgetByName(node, 'dtype'), true)
				toggleWidget(node, findWidgetByName(node, 'fitting'),true)
				toggleWidget(node, findWidgetByName(node, 'function'),true)
				toggleWidget(node, findWidgetByName(node, 'scale'), true)
				toggleWidget(node, findWidgetByName(node, 'start_at'), true)
				toggleWidget(node, findWidgetByName(node, 'end_at'), true)
				break
		}
		updateNodeHeight(node)
	}

	if(widget.name == 't5_type'){
		switch (widget.getValue()){
			case 'sd3':
				toggleWidget(node, findWidgetByName(node, 'clip_name'), true)
				toggleWidget(node, findWidgetByName(node, 'padding'), true)
				toggleWidget(node, findWidgetByName(node, 't5_name'))
				toggleWidget(node, findWidgetByName(node, 'device'))
				toggleWidget(node, findWidgetByName(node, 'dtype'))
				break
			case 't5v11':
				toggleWidget(node, findWidgetByName(node, 'clip_name'))
				toggleWidget(node, findWidgetByName(node, 'padding'))
				toggleWidget(node, findWidgetByName(node, 't5_name'),true)
				toggleWidget(node, findWidgetByName(node, 'device'),true)
				toggleWidget(node, findWidgetByName(node, 'dtype'),true)
		}
		updateNodeHeight(node)
	}

	if(widget.name == 'rem_mode'){
		switch (widget.getValue()){
			case 'Inspyrenet':
				toggleWidget(node, findWidgetByName(node, 'torchscript_jit'), true)
				break
			default:
				toggleWidget(node, findWidgetByName(node, 'torchscript_jit'), false)
				break
		}
	}
}

function widgetLogic2(node, widget) {
	if (widget.name === 'sampler_name') {
		const widget_names = ['eta','s_noise','upscale_ratio','start_step','end_step','upscale_n_step','unsharp_kernel_size','unsharp_sigma','unsharp_strength']
		if (["euler_ancestral", "dpmpp_2s_ancestral", "dpmpp_2m_sde", "lcm"].includes(widget.getValue())) {
			widget_names.map(name=> toggleWidget(node, findWidgetByName(node, name)), true)
		} else {
			widget_names.map(name=> toggleWidget(node, findWidgetByName(node, name)))
		}
		updateNodeHeight(node)
	}
}

function widgetLogic3(node, widget){
	if (widget.name === 'target_parameter') {
		if (node.comfyClass == 'easy XYInputs: Steps'){
			switch (widget.getValue()){
				case "steps":
					toggleWidget(node, findWidgetByName(node, 'first_step'), true)
					toggleWidget(node, findWidgetByName(node, 'last_step'), true)
					toggleWidget(node, findWidgetByName(node, 'first_start_step'))
					toggleWidget(node, findWidgetByName(node, 'last_start_step'))
					toggleWidget(node, findWidgetByName(node, 'first_end_step'))
					toggleWidget(node, findWidgetByName(node, 'last_end_step'))
					break
				case "start_at_step":
					toggleWidget(node, findWidgetByName(node, 'first_step'))
					toggleWidget(node, findWidgetByName(node, 'last_step'))
					toggleWidget(node, findWidgetByName(node, 'first_start_step'), true)
					toggleWidget(node, findWidgetByName(node, 'last_start_step'), true)
					toggleWidget(node, findWidgetByName(node, 'first_end_step'))
					toggleWidget(node, findWidgetByName(node, 'last_end_step'))
					break
				case "end_at_step":
					toggleWidget(node, findWidgetByName(node, 'first_step'))
					toggleWidget(node, findWidgetByName(node, 'last_step'))
					toggleWidget(node, findWidgetByName(node, 'first_start_step'))
					toggleWidget(node, findWidgetByName(node, 'last_start_step'))
					toggleWidget(node, findWidgetByName(node, 'first_end_step'),true)
					toggleWidget(node, findWidgetByName(node, 'last_end_step'),true)
					break
			}
		}
		if (node.comfyClass == 'easy XYInputs: Sampler/Scheduler'){
			let number_to_show = findWidgetByName(node, 'input_count').getValue() + 1
			for (let i = 0; i < number_to_show; i++) {
				switch (widget.getValue()) {
					case "sampler":
						toggleWidget(node, findWidgetByName(node, 'sampler_'+i), true)
						toggleWidget(node, findWidgetByName(node, 'scheduler_'+i))
						break
					case "scheduler":
						toggleWidget(node, findWidgetByName(node, 'scheduler_'+i), true)
						toggleWidget(node, findWidgetByName(node, 'sampler_'+i))
						break
					default:
						toggleWidget(node, findWidgetByName(node, 'sampler_'+i), true)
						toggleWidget(node, findWidgetByName(node, 'scheduler_'+i), true)
						break
				}
			}
			updateNodeHeight(node)
		}
		if (node.comfyClass == 'easy XYInputs: ControlNet'){
			switch (widget.getValue()){
				case "strength":
					toggleWidget(node, findWidgetByName(node, 'first_strength'), true)
					toggleWidget(node, findWidgetByName(node, 'last_strength'), true)
					toggleWidget(node, findWidgetByName(node, 'strength'))
					toggleWidget(node, findWidgetByName(node, 'start_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'end_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'first_start_percent'))
					toggleWidget(node, findWidgetByName(node, 'last_start_percent'))
					toggleWidget(node, findWidgetByName(node, 'first_end_percent'))
					toggleWidget(node, findWidgetByName(node, 'last_end_percent'))
					break
				case "start_percent":
					toggleWidget(node, findWidgetByName(node, 'first_strength'))
					toggleWidget(node, findWidgetByName(node, 'last_strength'))
					toggleWidget(node, findWidgetByName(node, 'strength'), true)
					toggleWidget(node, findWidgetByName(node, 'start_percent'))
					toggleWidget(node, findWidgetByName(node, 'end_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'first_start_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'last_start_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'first_end_percent'))
					toggleWidget(node, findWidgetByName(node, 'last_end_percent'))
					break
				case "end_percent":
					toggleWidget(node, findWidgetByName(node, 'first_strength'))
					toggleWidget(node, findWidgetByName(node, 'last_strength'))
					toggleWidget(node, findWidgetByName(node, 'strength'), true)
					toggleWidget(node, findWidgetByName(node, 'start_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'end_percent'))
					toggleWidget(node, findWidgetByName(node, 'first_start_percent'))
					toggleWidget(node, findWidgetByName(node, 'last_start_percent'))
					toggleWidget(node, findWidgetByName(node, 'first_end_percent'), true)
					toggleWidget(node, findWidgetByName(node, 'last_end_percent'), true)
					break
			}
			updateNodeHeight(node)
		}

	}
	if (node.comfyClass == 'easy XYInputs: PromptSR'){
		let number_to_show = findWidgetByName(node, 'replace_count').getValue() + 1
		for (let i = 0; i < number_to_show; i++) {
			toggleWidget(node, findWidgetByName(node, 'replace_'+i), true)
		}
		for (let i = number_to_show; i < 31; i++) {
			toggleWidget(node, findWidgetByName(node, 'replace_'+i))
		}
		updateNodeHeight(node)
	}

	if(widget.name == 'input_count'){
		let number_to_show = widget.getValue() + 1
		for (let i = 0; i < number_to_show; i++) {
			if (findWidgetByName(node, 'target_parameter').getValue() === "sampler") {
				toggleWidget(node, findWidgetByName(node, 'sampler_'+i), true)
				toggleWidget(node, findWidgetByName(node, 'scheduler_'+i))
			}
			else if (findWidgetByName(node, 'target_parameter').getValue() === "scheduler") {
				toggleWidget(node, findWidgetByName(node, 'scheduler_'+i), true)
				toggleWidget(node, findWidgetByName(node, 'sampler_'+i))
			} else {
				toggleWidget(node, findWidgetByName(node, 'sampler_'+i), true)
				toggleWidget(node, findWidgetByName(node, 'scheduler_'+i), true)
			}
		}
		for (let i = number_to_show; i < 31; i++) {
			toggleWidget(node, findWidgetByName(node, 'sampler_'+i))
			toggleWidget(node, findWidgetByName(node, 'scheduler_'+i))
		}
		updateNodeHeight(node)
	}
	if (widget.name === 'lora_count') {
		let number_to_show = widget.getValue() + 1
		const isWeight = findWidgetByName(node, 'input_mode').getValue().indexOf("Weights") == -1
		for (let i = 0; i < number_to_show; i++) {
			toggleWidget(node, findWidgetByName(node, 'lora_name_'+i), true)
			if (isWeight) {
				toggleWidget(node, findWidgetByName(node, 'lora_name_'+i), true)
				toggleWidget(node, findWidgetByName(node, 'model_str_'+i))
				toggleWidget(node, findWidgetByName(node, 'clip_str_'+i))
			} else {
				toggleWidget(node, findWidgetByName(node, 'lora_name_'+i), true)
				toggleWidget(node, findWidgetByName(node, 'model_str_'+i),true)
				toggleWidget(node, findWidgetByName(node, 'clip_str_'+i), true)
			}
		}
		for (let i = number_to_show; i < 11; i++) {
			toggleWidget(node, findWidgetByName(node, 'lora_name_'+i))
			toggleWidget(node, findWidgetByName(node, 'model_str_'+i))
			toggleWidget(node, findWidgetByName(node, 'clip_str_'+i))
		}
		updateNodeHeight(node)
	}
	if (widget.name === 'ckpt_count') {
		let number_to_show = widget.getValue() + 1
		const hasClipSkip = findWidgetByName(node, 'input_mode').getValue().indexOf("ClipSkip") != -1
		const hasVae = findWidgetByName(node, 'input_mode').getValue().indexOf("VAE") != -1
		for (let i = 0; i < number_to_show; i++) {
			toggleWidget(node, findWidgetByName(node, 'ckpt_name_'+i), true)
			if (hasClipSkip && hasVae) {
				toggleWidget(node, findWidgetByName(node, 'clip_skip_'+i), true)
				toggleWidget(node, findWidgetByName(node, 'vae_name_'+i), true)
			} else if (hasVae){
				toggleWidget(node, findWidgetByName(node, 'clip_skip_' + i))
				toggleWidget(node, findWidgetByName(node, 'vae_name_' + i), true)
			}else{
				toggleWidget(node, findWidgetByName(node, 'clip_skip_' + i))
				toggleWidget(node, findWidgetByName(node, 'vae_name_' + i))
			}
		}
		for (let i = number_to_show; i < 11; i++) {
			toggleWidget(node, findWidgetByName(node, 'ckpt_name_'+i))
			toggleWidget(node, findWidgetByName(node, 'clip_skip_'+i))
			toggleWidget(node, findWidgetByName(node, 'vae_name_'+i))
		}
		updateNodeHeight(node)
	}

	if (widget.name === 'input_mode') {
		if(node.comfyClass == 'easy XYInputs: Lora'){
			let number_to_show = findWidgetByName(node, 'lora_count').getValue() + 1
			const hasWeight = widget.getValue().indexOf("Weights") != -1
			for (let i = 0; i < number_to_show; i++) {
				toggleWidget(node, findWidgetByName(node, 'lora_name_'+i), true)
				if (hasWeight) {
					toggleWidget(node, findWidgetByName(node, 'model_str_'+i), true)
					toggleWidget(node, findWidgetByName(node, 'clip_str_'+i), true)
				} else {
					toggleWidget(node, findWidgetByName(node, 'model_str_' + i))
					toggleWidget(node, findWidgetByName(node, 'clip_str_' + i))
				}
			}
			if(hasWeight){
				toggleWidget(node, findWidgetByName(node, 'model_strength'))
				toggleWidget(node, findWidgetByName(node, 'clip_strength'))
			}else{
				toggleWidget(node, findWidgetByName(node, 'model_strength'), true)
				toggleWidget(node, findWidgetByName(node, 'clip_strength'),true)
			}
		}
		else if(node.comfyClass == 'easy XYInputs: Checkpoint'){
			let number_to_show = findWidgetByName(node, 'ckpt_count').getValue() + 1
			const hasClipSkip = widget.getValue().indexOf("ClipSkip") != -1
			const hasVae = widget.getValue().indexOf("VAE") != -1
			for (let i = 0; i < number_to_show; i++) {
				toggleWidget(node, findWidgetByName(node, 'ckpt_name_'+i), true)
				if (hasClipSkip && hasVae) {
					toggleWidget(node, findWidgetByName(node, 'clip_skip_'+i), true)
					toggleWidget(node, findWidgetByName(node, 'vae_name_'+i), true)
				} else if (hasClipSkip){
					toggleWidget(node, findWidgetByName(node, 'clip_skip_' + i), true)
					toggleWidget(node, findWidgetByName(node, 'vae_name_' + i))
				}else{
					toggleWidget(node, findWidgetByName(node, 'clip_skip_' + i))
					toggleWidget(node, findWidgetByName(node, 'vae_name_' + i))
				}
			}
		}

		updateNodeHeight(node)
	}

	// if(widget.name == 'replace_count'){
	// 	let number_to_show = widget.getValue() + 1
	// 	for (let i = 0; i < number_to_show; i++) {
	// 		toggleWidget(node, findWidgetByName(node, 'replace_'+i), true)
	// 	}
	// 	for (let i = number_to_show; i < 31; i++) {
	// 		toggleWidget(node, findWidgetByName(node, 'replace_'+i))
	// 	}
	// 	updateNodeHeight(node)
	// }
}

const getSetterNodes = ["easy fullLoader", "easy a1111Loader", "easy fluxLoader", "easy comfyLoader", "easy cascadeLoader",
	"easy svdLoader", "easy dynamiCrafterLoader", "easy hunyuanDiTLoader", "easy pixArtLoader", "easy kolorsLoader",
	"easy loraStack", "easy controlnetStack", "easy latentNoisy", "easy preSampling", "easy preSamplingAdvanced",
	"easy preSamplingNoiseIn", "easy preSamplingCustom", "easy preSamplingSdTurbo", "easy preSamplingCascade",
	"easy preSamplingLayerDiffusion", "easy fullkSampler", "easy kSampler", "easy kSamplerSDTurbo", "easy kSamplerTiled",
	"easy kSamplerLayerDiffusion", "easy kSamplerInpainting", "easy kSamplerDownscaleUnet", "easy fullCascadeKSampler",
	"easy cascadeKSampler", "easy hiresFix", "easy detailerFix", "easy imageRemBg", "easy imageColorMatch",
	"easy imageDetailTransfer", "easy loadImageBase64", "easy XYInputs: Steps", "easy XYInputs: Sampler/Scheduler",
	"easy XYInputs: Checkpoint", "easy XYInputs: Lora", "easy XYInputs: PromptSR", "easy XYInputs: ControlNet",
	"easy rangeInt", "easy rangeFloat", "easy latentCompositeMaskedWithCond", "easy pipeEdit", "easy icLightApply",
	"easy ipadapterApply", "easy ipadapterApplyADV", "easy ipadapterApplyFaceIDKolors", "easy ipadapterApplyEncoder",
	"easy applyInpaint"]

// The mounted wildcard readouts, keyed by node id and slot name.
const promptInputs = new Map();

function addText(arr_text) {
	var text = '';
	for (let i = 0; i < arr_text.length; i++) {
		text += arr_text[i];
	}
	return text
}

comfy.defs.extend([...getSetterNodes, "easy wildcards", "easy XYInputs: ModelMergeBlocks"], (b) => {

	b.onCreated((node) => {
		switch (node.comfyClass){
			case "easy wildcards":
				const wildcard_text_widget = node.widgets.get('text');

				// lora selector, wildcard selector
				let combo_id = 1;

				const lora_widget = node.widgets.at(combo_id);
				const wildcard_widget = node.widgets.at(combo_id + 1);

				// The old getter/setter pair existed to (a) append the picked entry to
				// the text box and (b) keep the combo reading back as its placeholder.
				// Resetting the value does both, and `change` only fires for a real
				// pick — a workflow load assigns directly, which is the same thing the
				// `inner_value_change` stack sniff was testing for.
				lora_widget.on('change', (value) => {
						if(value != "Select the LoRA to add to the text") {
							let lora_name = value;
							if (lora_name.endsWith('.safetensors')) {
								lora_name = lora_name.slice(0, -12);
							}

							wildcard_text_widget.setValue(wildcard_text_widget.getValue() + `<lora:${lora_name}>`);
							lora_widget.setValue("Select the LoRA to add to the text");
						}
					});

				wildcard_widget.on('change', (value) => {
						if(value != "Select the Wildcard to add to the text") {
							let text = wildcard_text_widget.getValue()
							if(text != '')
								text += ', '

							wildcard_text_widget.setValue(text + value);
							wildcard_widget.setValue("Select the Wildcard to add to the text");
						}
					});
				break
			case "easy XYInputs: ModelMergeBlocks":
 				let preset_i = 3;
		    	let vector_i = 4;

				let valuesWidget = node.widgets.at(vector_i)
				const presetWidget = node.widgets.at(preset_i)
				presetWidget.on('change', (value) => {
								if(value != "Preset") {
									let values = valuesWidget.getValue()
									if(!value.startsWith('@') && values)
										values += "\n";
									if(value.startsWith('@')) {
										let spec = value.split(':')[1];
										var n;
										var sub_n = null;
										var block = null;

										if(isNaN(spec)) {
											let sub_spec = spec.split(',');

											if(sub_spec.length != 3) {
												presetWidget.setValue('');
												return;
											}

											n = parseInt(sub_spec[0].trim());
											sub_n = parseInt(sub_spec[1].trim());
											block = parseInt(sub_spec[2].trim());
										}
										else {
											n = parseInt(spec.trim());
										}

										values = "";
										if(sub_n == null) {
											for(let i=1; i<=n; i++) {
												var temp = "1,1";
												for(let j=1; j<=n; j++) {
													if(temp!='')
														temp += ',';
													if(j==i)
														temp += '1';
													else
														temp += '0';
												}
												temp += ',1; ';

												values += `B${i}:${temp}\n`;
											}
										}
										else {
											for(let i=1; i<=sub_n; i++) {
												var temp = "";
												for(let j=1; j<=n; j++) {
													if(temp!='')
														temp += ',';

													if(block!=j)
														temp += '0';
													else {
														temp += ' ';
														for(let k=1; k<=sub_n; k++) {
															if(k==i)
																temp += '1 ';
															else
																temp += '0 ';
														}
													}
												}

												values += `B${block}.SUB${i}:${temp}\n`;
											}
										}
									}
									else {
										values += `${value}; `;
									}
									valuesWidget.setValue(values);
								}
					});

				// upload .csv
				async function uploadFile(file) {
					try {
						// The legacy route only read the upload line-by-line and joined
						// the lines with semicolons. Keep the file on the user's machine
						// and do the same deterministic transformation in the browser.
						const rows = (await file.text())
							.split(/\r?\n/)
							.map((line) => line.trim())
							.filter(Boolean);
						valuesWidget.setValue(rows.map((line) => `${line}; \n`).join(""));
					} catch (error) {
						alert(error);
					}
				}

				const fileInput = document.createElement("input");
				Object.assign(fileInput, {
					type: "file",
					accept: "text/csv",
					style: "show: none",
					onchange: async (event) => {
						if (fileInput.files.length) {
							await uploadFile(fileInput.files[0], true);
							event.target.value = ''
						}
					},
				});
				document.body.append(fileInput);

				const name = "choose .csv file into values"
				let uploadWidget = node.widgets.add({ type: "button", name, value: "csv", serialize: false });
				uploadWidget.setLabel(name);
				uploadWidget.on('activate', () => {
					fileInput.click();
				});

				break
			default:
				getSetters(node)
				break
		}
	})

	// A workflow load assigns widget values straight onto the widget, which
	// raises no change event, so visibility has to be recomputed once the node
	// is configured. This is what the value setter used to catch.
	b.onConfigured((node) => {
		if (!getSetterNodes.includes(node.comfyClass)) return
		for (const w of node.widgets) {
			if (getSetWidgets.includes(w.name)) applyWidgetLogic(node, w);
		}
	})

	b.onRemoved((node) => {
		lastValues.delete(node.id + ':control_before_generate')
		lastValues.delete(node.id + ':control_after_generate')
	})
})

comfy.defs.extend(["easy showSpentTime"], (b) => {
	function populate(text) {
		const w = this.widgets.get("spent_time")
		if (w) {
			console.log(text)
			w.setValue(text);
		}
	}

	// When the node is executed we will be sent the input text, show this in the widget
	b.onExecuted((node, result) => {
		const text = addText(result.text)
		populate.call(node, text);
	});
})

comfy.defs.extend(["easy showLoaderSettingsNames"], (b) => {
	function populate(text) {
		const w = this.widgets.get("names")
		if (w) {
			w.setValue(text);
		}
	}

	// When the node is executed we will be sent the input text, show this in the widget
	b.onExecuted((node, result) => {
		const text = addText(result.text)
		populate.call(node, text);
	});
})

comfy.defs.extend(loaderNodes, (b) => {
	function populate(text, type = 'positive') {
		const node = this;
		const key = node.id + ':' + type;
		const name = type + "_prompt";
		const existing = node.widgets.get(name);
		if (!existing && text) {
			const inputEl = document.createElement("textarea");
			inputEl.className = "comfy-multiline-input wildcard_" + type + '_' + node.id.toString();
			inputEl.placeholder = "Wildcard Prompt (" + type + ")"
			inputEl.readOnly = true
			node.widgets.mount({
				name,
				render(container) {
					container.append(inputEl);
					promptInputs.set(key, inputEl);
				},
				destroy() {
					promptInputs.delete(key);
					inputEl.remove();
				}
			});
			inputEl.value = text;
		} else if (existing) {
			if (text) {
				const inputEl = promptInputs.get(key);
				if (inputEl) inputEl.value = text;
			} else {
				node.widgets.remove(name);
			}
		}
	}

	b.onExecuted((node, result) => {
		const positive = addText(result.raw.positive ?? [])
		const negative = addText(result.raw.negative ?? [])
		populate.call(node, positive, "positive");
		populate.call(node, negative, "negative");
	});
})

comfy.defs.extend(["easy sv3dLoader"], (b) => {
	// Was `inputEl.readOnly = true` plus `inputEl.style.opacity = 0.6` on the
	// scheduler's textarea. setDisabled is what that pair meant, said once, and
	// without the pack deciding what "not editable" looks like.
	function changeSchedulerText(mode, batch_size, scheduler) {
		console.log(mode)
		switch (mode){
			case 'azimuth':
				scheduler.setDisabled(true)
				return `0:(0.0,0.0)` + (batch_size > 1 ? `\n${batch_size-1}:(360.0,0.0)` : '')
			case 'elevation':
				scheduler.setDisabled(true)
				return `0:(-90.0,0.0)` + (batch_size > 1 ? `\n${batch_size-1}:(90.0,0.0)` : '')
			case 'custom':
				scheduler.setDisabled(false)
				return `0:(0.0,0.0)\n9:(180.0,0.0)\n20:(360.0,0.0)`
		}
	}

	b.onCreated((node) => {
		const easing_mode_widget = node.widgets.get('easing_mode')
		const batch_size = node.widgets.get('batch_size')
		const scheduler = node.widgets.get('scheduler')
		setTimeout(_=>{
			if(!scheduler.getValue()) scheduler.setValue(changeSchedulerText(easing_mode_widget.getValue(), batch_size.getValue(), scheduler))
		},1)
		easing_mode_widget.on('change', value=>{
			scheduler.setValue(changeSchedulerText(value, batch_size.getValue(), scheduler))
		})
		batch_size.on('change', value =>{
			scheduler.setValue(changeSchedulerText(easing_mode_widget.getValue(), value, scheduler))
		})
	})
})

comfy.defs.extend(seedNodes, (b) => {
	b.onCreated((node) => {
		const seed_widget = node.widgets.get('seed_num') || node.widgets.get('seed')
		const seed_control = node.widgets.get('control_before_generate') || node.widgets.get('control_after_generate')
		if(node.comfyClass == 'easy seed'){
			const randomSeedButton = node.widgets.add({ type: "button", name: "🎲 Manual Random Seed", value: null, options: { serialize: false } })
			randomSeedButton.on('activate', _=>{
				if(seed_control.getValue() != 'fixed') seed_control.setValue('fixed')
				seed_widget.setValue(Math.floor(Math.random() * 1125899906842624))
				void comfy.queue.run()
			})
		}
		setTimeout(_=>{
			if(seed_control && seed_control.name == 'control_before_generate' && seed_widget.getValue() === 0) {
				seed_widget.setValue(Math.floor(Math.random() * 1125899906842624))
			}
		},1)
	})
})

comfy.defs.extend(['easy imageInsetCrop'], (b) => {
	function setWidgetStep(a) {
		const measurementWidget = a.widgets.at(0)
		for (let i = 1; i <= 4; i++) {
			if (measurementWidget.getValue() === 'Pixels') {
				a.widgets.at(i).setOption('step', 80);
				a.widgets.at(i).setOption('max', 8192);
			} else {
				a.widgets.at(i).setOption('step', 10);
				a.widgets.at(i).setOption('max', 99);
			}
		}
	}

	b.onCreated((node) => {
		node.widgets.at(0).on('change', () => setWidgetStep(node));
		setTimeout(_=>{
			setWidgetStep(node);
		},1)
	})
})

// The readouts these three nodes append were N widgets ALL named "text", made
// with ComfyWidgets.STRING — which for a multiline STRING is an addDOMWidget of
// type 'customtext', so `mount` is the same widget with the pack owning the
// element. A name is identity now (widgetValueStore keys on
// graphId:nodeId:name), so they have to be distinguishable, and the naming is
// chosen to keep the wire exactly as it was:
//
//  - widgets_values is POSITIONAL and carries no names, so N entries in N
//    order is unchanged whatever the widgets are called.
//  - the prompt is `inputs[widget.name]` per widget, so N same-named widgets
//    collapsed to the LAST one's value. The last readout therefore keeps the
//    name "text" and sends; the earlier ones are numbered and set
//    sendToPrompt:false, so no key is added and `inputs.text` still holds the
//    last element. For the ordinary single-element case there is one widget,
//    called "text", exactly as before.
const readoutNames = new Map();

comfy.defs.extend(['easy showAnything', 'easy showTensorShape', 'easy imageInterrogator'], (b) => {
	function populate(node, text) {
		for (const name of readoutNames.get(node.id) ?? []) {
			node.widgets.remove(name);
		}
		const names = text.map((list, i) => {
			const name = i === text.length - 1 ? "text" : `text_${i}`;
			let stopWatching = null;
			node.widgets.mount({
				name,
				defaultValue: list,
				serialize: true,
				sendToPrompt: i === text.length - 1,
				render(container, value) {
					const inputEl = document.createElement("textarea");
					inputEl.className = "comfy-multiline-input";
					inputEl.readOnly = true;
					inputEl.style.opacity = 0.6;
					inputEl.value = value.get();
					container.append(inputEl);
					stopWatching = value.onChange((v) => { inputEl.value = v; });
				},
				// These are torn down and rebuilt on every execution, so the
				// subscription has to go with them.
				destroy() {
					if (stopWatching) stopWatching();
					stopWatching = null;
				}
			});
			return name;
		});
		readoutNames.set(node.id, names);
		// Was a requestAnimationFrame that recomputed the node's size and grew it
		// to fit the new boxes, on every execution.
		node.setSizeConstraints({ autoHeight: true });
	}

	// When the node is executed we will be sent the input text, display this in the widget
	b.onExecuted((node, result) => {
		populate(node, result.text);
	});

	b.onConfigured((node, data) => {
		// imageInterrogator was excluded from this hook: it has declared widgets,
		// so its widgets_values is not the readout array.
		if (node.type === 'easy imageInterrogator') return;
		if (data.widgets_values?.length) {
			populate(node, data.widgets_values);
		}
	});

	b.onRemoved((node) => {
		readoutNames.delete(node.id);
	});
})

comfy.defs.extend(['easy convertAnything'], (b) => {
	b.onCreated((node) => {
		setTimeout(_=>{
			const type_control = node.widgets.get("output_type")
			type_control.on('change', (value) => {
				node.outputs.at(0).modify({ type: String(value).toUpperCase(), name: value, label: value })
			})
		},300)
	})
})

comfy.defs.extend(['easy promptLine'], (b) => {
	b.onCreated((node) => {
		let prompt_widget = node.widgets.get("prompt")
		const button = node.widgets.add({ type: "button", name: "get values from COMBO link", value: '', options: { serialize: false } })
		button.on('activate', () => {
			const output_link = node.outputs.at(1)?.links()[0] || null
			const target = output_link ? comfy.graph.node(output_link.targetNodeId) : null
			if(!output_link || !target){
				toast.error($t('No COMBO link'), 3000)
				return
			}
			else{
				// Was input.widget.name. The slot and the widget it stands in for are
				// created from the same string — litegraphService.ts:316 passes
				// `inputName` as both the slot name and `widget: { name: inputName }`,
				// and core's own getWidgetFromSlot matches on it — so the slot's name
				// IS the widget's name, and the back-reference was never carrying
				// anything the slot did not already say.
				const input = target.inputs.at(output_link.targetIndex)
				const widget = input ? target.widgets.get(input.name) : undefined
				let values = widget?.getOptions()?.values || null
				if(values){
					values = values.join('\n')
					prompt_widget.setValue(values)
				}
			}
		})
	})
})


const getSetWidgets = ['rescale_after_model', 'rescale',
						'lora_name', 'lora1_name', 'lora2_name', 'lora3_name', 
						'refiner_lora1_name', 'refiner_lora2_name', 'upscale_method', 
						'image_output', 'add_noise', 'info', 'sampler_name',
						'ckpt_B_name', 'ckpt_C_name', 'save_model', 'refiner_ckpt_name',
						'num_loras', 'num_controlnet', 'mode', 'toggle', 'resolution', 'ratio', 'target_parameter',
	'input_count', 'replace_count', 'downscale_mode', 'range_mode','text_combine_mode', 'input_mode',
	'lora_count','ckpt_count', 'conditioning_mode', 'preset', 'use_tiled', 'use_batch', 'num_embeds',
	"easing_mode", "guider", "scheduler", "inpaint_mode", 't5_type', 'rem_mode'
]

function applyWidgetLogic(node, w) {
	if(node.comfyClass.indexOf("easy XYInputs:") != -1) widgetLogic3(node, w)
	else if(w.name == 'sampler_name' && node.comfyClass == 'easy preSamplingSdTurbo') widgetLogic2(node, w);
	else widgetLogic(node, w);
}

function getSetters(node) {
	for (const w of node.widgets) {
		if (getSetWidgets.includes(w.name)) {
			applyWidgetLogic(node, w);

			// Replaces the value getter/setter pair the pack installed on the
			// widget. Listeners are additive, so no other pack can drop this one.
			w.on('change', () => applyWidgetLogic(node, w));
		}
	}
}
