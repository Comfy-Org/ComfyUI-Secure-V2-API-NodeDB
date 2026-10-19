import { comfy } from '/comfy/api/v2.js';
const TITLES={"ttN_tinyLoader_c80deffd6042c4a897866d79": "tinyLoader", "ttN_conditioning_00ee7fb58d6217b61d28ffda": "tinyConditioning", "ttN_KSampler_v2_b96111c6c532990ae4d2a22d": "tinyKSampler", "ttN_pipeLoader_v2_58246dfb20bdc0271e2f0da1": "pipeLoader", "ttN_pipeKSampler_v2_384e6bf1e6bdf16dab3403be": "pipeKSampler", "ttN_pipeKSamplerAdvanced_v2_0bde6a2fc6fd2b1f3148c941": "pipeKSamplerAdvanced", "ttN_pipeLoaderSDXL_v2_2315fee49000ac73ed2b4205": "pipeLoaderSDXL", "ttN_pipeKSamplerSDXL_v2_d7a835b65f8b639485e83a20": "pipeKSamplerSDXL", "ttN_advanced_xyPlot_5660b5693fff3e6a7b6ac6be": "advanced xyPlot", "ttN_advPlot_images_9464f7f009faedbbe64f8aee": "advPlot images", "ttN_advPlot_range_ae4d61a6cbdb5c6824e46a98": "advPlot range", "ttN_advPlot_string_abb8997c9782d24ce63175fb": "advPlot string", "ttN_advPlot_combo_2175b2f2a4848cce66909124": "advPlot combo", "ttN_advPlot_merge_174e015dbe69c2712c571e31": "advPlot merge", "ttN_pipeEDIT_aa5a200004e9fb4314a1b528": "pipeEDIT", "ttN_pipe2BASIC_748c46ff86c489ba345bbb37": "pipe > basic_pipe", "ttN_pipe2DETAILER_fb799f9f4e6a3a0b893bacef": "pipe > detailer_pipe", "ttN_pipeEncodeConcat_7974130fa1ef7a3d6966bb0a": "pipeEncodeConcat", "ttN_pipeLoraStack_2ec4cdc8dd3715945346a19e": "pipeLoraStack", "ttN_multiModelMerge_9930284c5606dcc14e190be2": "multiModelMerge", "ttN_debugInput_b1bdfd3890f7007c8f93b9a5": "debugInput", "ttN_text_17f67ffa52c37f580bb94011": "text", "ttN_textDebug_0be2c3c83aa3a0e9be121654": "textDebug", "ttN_concat_98a12dae0cccc980d9c7b338": "textConcat", "ttN_text3BOX_3WAYconcat_d6bfacdd1e94a341253109a6": "3x TXT Loader MultiConcat", "ttN_text7BOX_concat_e768585a58ce525b0095c15f": "7x TXT Loader Concat", "ttN_textCycleLine_07efecfd0109e56a0112fcc3": "textCycleLine", "ttN_textOutput_561c7568d7a8609efb4c9c40": "textOutput", "ttN_imageOutput_9d7e52569d2d64b9e9e58352": "imageOutput", "ttN_imageREMBG_d75ef8a3e919f3bfc66f9795": "imageRemBG", "ttN_hiresfixScale_30b24f506f9af9321f1ae901": "hiresfixScale", "ttN_int_3b12e0212a0b8b0be03416b7": "int", "ttN_float_135744bce0eed7150cbe9f22": "float", "ttN_seed_0fffce90a3d1a81a1e11489e": "seed", "ttN_xyPlot_544de9d62d33978b709f2eee": "xyPlot", "ttN_pipeIN_0f4a584cca428eb3e2db18ec": "pipeIN (Legacy)", "ttN_pipeOUT_ddb0379afad4f093ff872f5d": "pipeOUT (Legacy)", "ttN_pipeLoader_b6c51abd124a0a79c7ba8c93": "pipeLoader v1 (Legacy)", "ttN_pipeKSampler_aab002d291a2f516b9550bf3": "pipeKSampler v1 (Legacy)", "ttN_pipeKSamplerAdvanced_ba5a6ba9874ab2faac51c05a": "pipeKSamplerAdvanced v1 (Legacy)", "ttN_pipeLoaderSDXL_48a01436a42cd167b68fb47f": "pipeLoaderSDXL v1 (Legacy)", "ttN_pipeKSamplerSDXL_a19bff1409f78f89af7781cd": "pipeKSamplerSDXL v1 (Legacy)", "ttN_compareInput_0cbbb1699b9e429b0a797dde": "compareInput"};
const findWidgetByName=(node,name)=>node.widgets.get(name);
function updateNodeHeight(node) { /* setHidden delegates layout to the host. */ }
function toggleWidget(node,widget,show=false) {
  if (!widget || node.inputs.all().some(input=>input.name===widget.name && input.isConnected)) return;
  widget.setHidden(!show);
}
function widgetLogic(node, widget) {
	switch (widget.name) {
		case 'lora_name':
			if (widget.getValue() === "None") {
				toggleWidget(node, findWidgetByName(node, 'lora_model_strength'))
				toggleWidget(node, findWidgetByName(node, 'lora_clip_strength'))
                toggleWidget(node, findWidgetByName(node, 'lora_strength'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'lora_model_strength'), true)
				toggleWidget(node, findWidgetByName(node, 'lora_clip_strength'), true)
                toggleWidget(node, findWidgetByName(node, 'lora_strength'), true)
			}
			break;

        case 'lora1_name':
            if (widget.getValue() === "None") {
                toggleWidget(node, findWidgetByName(node, 'lora1_model_strength'))
                toggleWidget(node, findWidgetByName(node, 'lora1_clip_strength'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'lora1_model_strength'), true)
                toggleWidget(node, findWidgetByName(node, 'lora1_clip_strength'), true)
            }
            break;
        
        case 'lora2_name':
            if (widget.getValue() === "None") {
                toggleWidget(node, findWidgetByName(node, 'lora2_model_strength'))
                toggleWidget(node, findWidgetByName(node, 'lora2_clip_strength'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'lora2_model_strength'), true)
                toggleWidget(node, findWidgetByName(node, 'lora2_clip_strength'), true)
            }
            break;

        case 'lora3_name':
            if (widget.getValue() === "None") {
                toggleWidget(node, findWidgetByName(node, 'lora3_model_strength'))
                toggleWidget(node, findWidgetByName(node, 'lora3_clip_strength'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'lora3_model_strength'), true)
                toggleWidget(node, findWidgetByName(node, 'lora3_clip_strength'), true)
            }
            break;

		case 'refiner_ckpt_name':
			let refiner_lora1 = findWidgetByName(node, 'refiner_lora1_name')?.getValue()
			let refiner_lora2 = findWidgetByName(node, 'refiner_lora2_name')?.getValue()
			if (widget.getValue() === "None") {
				toggleWidget(node, findWidgetByName(node, 'refiner_vae_name'))
				toggleWidget(node, findWidgetByName(node, 'refiner_config_name'))
				toggleWidget(node, findWidgetByName(node, 'refiner_clip_skip'))
				toggleWidget(node, findWidgetByName(node, 'refiner_loras'))
				toggleWidget(node, findWidgetByName(node, 'positive_ascore'))
				toggleWidget(node, findWidgetByName(node, 'negative_ascore'))

				toggleWidget(node, findWidgetByName(node, 'refiner_lora1_name'))
				toggleWidget(node, findWidgetByName(node, 'refiner_lora1_model_strength'))
				toggleWidget(node, findWidgetByName(node, 'refiner_lora1_clip_strength'))
				toggleWidget(node, findWidgetByName(node, 'refiner_lora2_name'))
				toggleWidget(node, findWidgetByName(node, 'refiner_lora2_model_strength'))
				toggleWidget(node, findWidgetByName(node, 'refiner_lora2_clip_strength'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'refiner_vae_name'), true)
				toggleWidget(node, findWidgetByName(node, 'refiner_config_name'), true)
				toggleWidget(node, findWidgetByName(node, 'refiner_clip_skip'), true)
				toggleWidget(node, findWidgetByName(node, 'refiner_loras'), true)
				toggleWidget(node, findWidgetByName(node, 'positive_ascore'), true)
				toggleWidget(node, findWidgetByName(node, 'negative_ascore'), true)
				toggleWidget(node, findWidgetByName(node, 'refiner_lora1_name'), true)
				if (refiner_lora1 !== "None") {
					toggleWidget(node, findWidgetByName(node, 'refiner_lora1_model_strength'), true)
					toggleWidget(node, findWidgetByName(node, 'refiner_lora1_clip_strength'), true)
				}
				toggleWidget(node, findWidgetByName(node, 'refiner_lora2_name'), true)
				if (refiner_lora2 !== "None") {
					toggleWidget(node, findWidgetByName(node, 'refiner_lora2_model_strength'), true)
					toggleWidget(node, findWidgetByName(node, 'refiner_lora2_clip_strength'), true)
				}
			}
			break;

		case 'rescale_after_model':
			if (widget.getValue() === false) {
				toggleWidget(node, findWidgetByName(node, 'rescale_method'))
				toggleWidget(node, findWidgetByName(node, 'rescale'))
				toggleWidget(node, findWidgetByName(node, 'percent'))
				toggleWidget(node, findWidgetByName(node, 'width'))
				toggleWidget(node, findWidgetByName(node, 'height'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'))
				toggleWidget(node, findWidgetByName(node, 'crop'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'rescale_method'), true)
				toggleWidget(node, findWidgetByName(node, 'rescale'), true)
				
				let rescale_value = findWidgetByName(node, 'rescale').getValue()

				if (rescale_value === 'by percentage') {
					toggleWidget(node, findWidgetByName(node, 'percent'), true)
				} else if (rescale_value === 'to Width/Height') {
					toggleWidget(node, findWidgetByName(node, 'width'), true)
					toggleWidget(node, findWidgetByName(node, 'height'), true)
				} else {
					toggleWidget(node, findWidgetByName(node, 'longer_side'), true)
				}
				toggleWidget(node, findWidgetByName(node, 'crop'), true)
			}
			break;

		case 'rescale':
			let rescale_after_model = findWidgetByName(node, 'rescale_after_model')?.getValue()
			let hiresfix = findWidgetByName(node, 'upscale_method') || findWidgetByName(node, 'rescale_method')
            if (typeof(hiresfix.getValue()) == 'string' && hiresfix.getValue().includes('hiresFix')) {
                hiresfix = true
            } else {
                hiresfix = false
            }
			if (widget.getValue() === 'by percentage' && (rescale_after_model || hiresfix)) {
				toggleWidget(node, findWidgetByName(node, 'width'))
				toggleWidget(node, findWidgetByName(node, 'height'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'))
				toggleWidget(node, findWidgetByName(node, 'percent'), true)
			} else if (widget.getValue() === 'to Width/Height' && (rescale_after_model || hiresfix)) {
				toggleWidget(node, findWidgetByName(node, 'width'), true)
				toggleWidget(node, findWidgetByName(node, 'height'), true)
				toggleWidget(node, findWidgetByName(node, 'percent'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'))
			} else if (widget.getValue() === 'to longer side - maintain aspect' && (rescale_after_model || hiresfix)) {
				toggleWidget(node, findWidgetByName(node, 'width'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'), true)
				toggleWidget(node, findWidgetByName(node, 'height'))
				toggleWidget(node, findWidgetByName(node, 'percent'))
			} else if (widget.getValue() === 'None' && (rescale_after_model || hiresfix)) {
				toggleWidget(node, findWidgetByName(node, 'width'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'))
				toggleWidget(node, findWidgetByName(node, 'height'))
				toggleWidget(node, findWidgetByName(node, 'percent'))
            } else {
				toggleWidget(node, findWidgetByName(node, 'width'))
				toggleWidget(node, findWidgetByName(node, 'height'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'))
				toggleWidget(node, findWidgetByName(node, 'percent'))
			}
			break;

		case 'upscale_method':
			if (widget.getValue() === "None") {
				toggleWidget(node, findWidgetByName(node, 'factor'))
				toggleWidget(node, findWidgetByName(node, 'crop'))
				toggleWidget(node, findWidgetByName(node, 'upscale_model_name'))
				toggleWidget(node, findWidgetByName(node, 'rescale'))
				toggleWidget(node, findWidgetByName(node, 'percent'))
				toggleWidget(node, findWidgetByName(node, 'width'))
				toggleWidget(node, findWidgetByName(node, 'height'))
				toggleWidget(node, findWidgetByName(node, 'longer_side'))
			} else {
				if (typeof(widget.getValue()) === 'string' && widget.getValue().includes('[hiresFix]')) {
					let rescale = findWidgetByName(node, 'rescale')
					toggleWidget(node, rescale, true)
					if (rescale?.getValue() === 'by percentage') {
						toggleWidget(node, findWidgetByName(node, 'percent'), true)
						toggleWidget(node, findWidgetByName(node, 'longer_side'))
						toggleWidget(node, findWidgetByName(node, 'width'))
						toggleWidget(node, findWidgetByName(node, 'height'))
						toggleWidget(node, findWidgetByName(node, 'factor'))
						toggleWidget(node, findWidgetByName(node, 'crop'))
					} else if (rescale?.getValue() === 'to Width/Height') {
						toggleWidget(node, findWidgetByName(node, 'percent'))
						toggleWidget(node, findWidgetByName(node, 'longer_side'))
						toggleWidget(node, findWidgetByName(node, 'width'), true)
						toggleWidget(node, findWidgetByName(node, 'height'), true)
						toggleWidget(node, findWidgetByName(node, 'factor'))
						toggleWidget(node, findWidgetByName(node, 'crop'))
					} else if (rescale?.getValue() === 'to Width/Height') {
						toggleWidget(node, findWidgetByName(node, 'percent'))
						toggleWidget(node, findWidgetByName(node, 'longer_side'), true)
						toggleWidget(node, findWidgetByName(node, 'width'))
						toggleWidget(node, findWidgetByName(node, 'height'))
						toggleWidget(node, findWidgetByName(node, 'factor'))
						toggleWidget(node, findWidgetByName(node, 'crop'))
                    } else {
						toggleWidget(node, findWidgetByName(node, 'percent'))
						toggleWidget(node, findWidgetByName(node, 'longer_side'))
						toggleWidget(node, findWidgetByName(node, 'width'))
						toggleWidget(node, findWidgetByName(node, 'height'))
						toggleWidget(node, findWidgetByName(node, 'factor'))
						toggleWidget(node, findWidgetByName(node, 'crop'))                        
                    }
					toggleWidget(node, findWidgetByName(node, 'upscale_model_name'), true)
				} else {
					toggleWidget(node, findWidgetByName(node, 'upscale_model_name'))
					toggleWidget(node, findWidgetByName(node, 'rescale'))
					toggleWidget(node, findWidgetByName(node, 'percent'))
					toggleWidget(node, findWidgetByName(node, 'width'))
					toggleWidget(node, findWidgetByName(node, 'height'))
					toggleWidget(node, findWidgetByName(node, 'longer_side'))
					toggleWidget(node, findWidgetByName(node, 'factor'), true)
					toggleWidget(node, findWidgetByName(node, 'crop'), true)
				}
			}
			break;

		case 'image_output':
			if (['Hide', 'Preview'].includes(widget.getValue())) {
				toggleWidget(node, findWidgetByName(node, 'save_prefix'))
				toggleWidget(node, findWidgetByName(node, 'output_path'))
				toggleWidget(node, findWidgetByName(node, 'embed_workflow'))
				toggleWidget(node, findWidgetByName(node, 'number_padding'))
				toggleWidget(node, findWidgetByName(node, 'overwrite_existing'))
                toggleWidget(node, findWidgetByName(node, 'file_type'))
			} else if (['Save', 'Hide/Save', 'Disabled'].includes(widget.getValue())) {
				toggleWidget(node, findWidgetByName(node, 'save_prefix'), true)
				toggleWidget(node, findWidgetByName(node, 'output_path'), true)
				toggleWidget(node, findWidgetByName(node, 'number_padding'), true)
				toggleWidget(node, findWidgetByName(node, 'overwrite_existing'), true)
                toggleWidget(node, findWidgetByName(node, 'file_type'), true)
                const fileTypeValue = findWidgetByName(node, 'file_type')?.getValue()
                if (['png', 'webp'].includes(fileTypeValue)) {
                    toggleWidget(node, findWidgetByName(node, 'embed_workflow'), true)
                } else {
                    toggleWidget(node, findWidgetByName(node, 'embed_workflow'))
                }
			}
			break;

        case 'text_output':
            if (widget.getValue() === "Preview") {
                toggleWidget(node, findWidgetByName(node, 'save_prefix'))
                toggleWidget(node, findWidgetByName(node, 'output_path'))
                toggleWidget(node, findWidgetByName(node, 'number_padding'))
                toggleWidget(node, findWidgetByName(node, 'overwrite_existing'))
                toggleWidget(node, findWidgetByName(node, 'file_type'))
            } else if (widget.getValue() === "Save") {
                toggleWidget(node, findWidgetByName(node, 'save_prefix'), true)
                toggleWidget(node, findWidgetByName(node, 'output_path'), true)
                toggleWidget(node, findWidgetByName(node, 'number_padding'), true)
                toggleWidget(node, findWidgetByName(node, 'overwrite_existing'), true)
                toggleWidget(node, findWidgetByName(node, 'file_type'), true)
            }
            
		case 'add_noise':
			if (widget.getValue() === "disable") {
				toggleWidget(node, findWidgetByName(node, 'noise_seed'))
				toggleWidget(node, findWidgetByName(node, 'control_after_generate'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'noise_seed'), true)
				toggleWidget(node, findWidgetByName(node, 'control_after_generate'), true)
			}
			break;

		case 'ckpt_B_name':
			if (widget.getValue() === "None") {
				toggleWidget(node, findWidgetByName(node, 'config_B_name'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'config_B_name'), true)
			}
			break;

		case 'ckpt_C_name':
			if (widget.getValue() === "None") {
				toggleWidget(node, findWidgetByName(node, 'config_C_name'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'config_C_name'), true)
			}
			break;

		case 'save_model':
			if (widget.getValue() === "True") {
				toggleWidget(node, findWidgetByName(node, 'save_prefix'), true)

			} else {
				toggleWidget(node, findWidgetByName(node, 'save_prefix'))
			}
			break;

		case 'num_loras':
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
			updateNodeHeight(node);
			break;

		case 'mode':
            if (TITLES[node.type] === "pipeLoraStack") {
                let number_to_show2 = findWidgetByName(node, 'num_loras')?.getValue() + 1
                for (let i = 0; i < number_to_show2; i++) {
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
                break;
            } else if (TITLES[node.type] === "advPlot combo") {
                if (widget.getValue() === 'all') {
                    toggleWidget(node, findWidgetByName(node, 'start_from'))
                    toggleWidget(node, findWidgetByName(node, 'end_with'))
                    toggleWidget(node, findWidgetByName(node, 'select'))
                    toggleWidget(node, findWidgetByName(node, 'selection'))
                } else if (widget.getValue() === 'range') {
                    toggleWidget(node, findWidgetByName(node, 'start_from'), true)
                    toggleWidget(node, findWidgetByName(node, 'end_with'), true)
                    toggleWidget(node, findWidgetByName(node, 'select'))
                    toggleWidget(node, findWidgetByName(node, 'selection'))
                } else {
                    toggleWidget(node, findWidgetByName(node, 'start_from'))
                    toggleWidget(node, findWidgetByName(node, 'end_with'))
                    toggleWidget(node, findWidgetByName(node, 'select'), true)
                    toggleWidget(node, findWidgetByName(node, 'selection'), true)
                }
            }

		case 'empty_latent_aspect':
			if (widget.getValue() !== 'width x height [custom]') {
				toggleWidget(node, findWidgetByName(node, 'empty_latent_width'))
				toggleWidget(node, findWidgetByName(node, 'empty_latent_height'))
			} else {
				toggleWidget(node, findWidgetByName(node, 'empty_latent_width'), true)
				toggleWidget(node, findWidgetByName(node, 'empty_latent_height'), true)
			}
			break;
        
        case 'conditioning_aspect':
            if (widget.getValue() !== 'width x height [custom]') {
                toggleWidget(node, findWidgetByName(node, 'conditioning_width'))
                toggleWidget(node, findWidgetByName(node, 'conditioning_height'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'conditioning_width'), true)
                toggleWidget(node, findWidgetByName(node, 'conditioning_height'), true)
            }
            break;

        case 'target_aspect':
            if (widget.getValue() !== 'width x height [custom]') {
                toggleWidget(node, findWidgetByName(node, 'target_width'))
                toggleWidget(node, findWidgetByName(node, 'target_height'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'target_width'), true)
                toggleWidget(node, findWidgetByName(node, 'target_height'), true)
            }
            break;

		case 'toggle':
			widget.setOption('on', 'Enabled'); widget.setOption('off', 'Disabled')
			break;

        case 'refiner_steps':
            if (widget.getValue() == 0) {
                toggleWidget(node, findWidgetByName(node, 'refiner_cfg'))
                toggleWidget(node, findWidgetByName(node, 'refiner_denoise'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'refiner_cfg'), true)
                toggleWidget(node, findWidgetByName(node, 'refiner_denoise'), true)
            }
            break;
        
        case 'sampler_state':
            if (widget.getValue() == 'Hold') {
                findWidgetByName(node, 'control_after_generate')?.setValue('fixed')
            }
            break;

        case 'print_to_console':
            if (widget.getValue() == false) {
                toggleWidget(node, findWidgetByName(node, 'console_title'))
                toggleWidget(node, findWidgetByName(node, 'console_color'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'console_title'), true)
                toggleWidget(node, findWidgetByName(node, 'console_color'), true)
            }
            break;

        case 'sampling':
            if (widget.getValue() == 'Default') {
                toggleWidget(node, findWidgetByName(node, 'zsnr'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'zsnr'), true)
            }
            break;
        
        case 'range_mode':
            function setWidgetOptions(widget, options) {
                widget.setOption('step', options.step);
                widget.setOption('round', options.round);
                widget.setOption('precision', options.precision);
            }

            if (widget.getValue().startsWith('step')) {
                toggleWidget(node, findWidgetByName(node, 'stop'))
                toggleWidget(node, findWidgetByName(node, 'step'), true)
                toggleWidget(node, findWidgetByName(node, 'include_stop'))
            } else {
                toggleWidget(node, findWidgetByName(node, 'stop'), true)
                toggleWidget(node, findWidgetByName(node, 'step'))
                toggleWidget(node, findWidgetByName(node, 'include_stop'), true)
            }
            if (widget.getValue().endsWith('int')) {
                const intOptions = {
                    step: 10,
                    round: 1,
                    precision: 0
                  };
                const start_widget = findWidgetByName(node, 'start')
                const stop_widget = findWidgetByName(node, 'stop')
                const step_widget = findWidgetByName(node, 'step')
                setWidgetOptions(start_widget, intOptions);
                setWidgetOptions(stop_widget, intOptions);
                setWidgetOptions(step_widget, intOptions);

            } else {
                const floatOptions = {
                    step: 0.1,
                    round: 0.01,
                    precision: 2
                  };
                const start_widget = findWidgetByName(node, 'start')
                const stop_widget = findWidgetByName(node, 'stop')
                const step_widget = findWidgetByName(node, 'step')
                setWidgetOptions(start_widget, floatOptions);
                setWidgetOptions(stop_widget, floatOptions);
                setWidgetOptions(step_widget, floatOptions);
            }
            break;

        case 'file_type':
            const imageOutputValue = findWidgetByName(node, 'image_output').getValue()
            if (['png', 'webp'].includes(widget.getValue()) && ['Save', 'Hide/Save', 'Disabled'].includes(imageOutputValue)) {
                toggleWidget(node, findWidgetByName(node, 'embed_workflow'), true)
            } else {
                toggleWidget(node, findWidgetByName(node, 'embed_workflow'))
            }
            break;

        case 'replace_mode':
            if (widget.getValue() == true) {
                toggleWidget(node, findWidgetByName(node, 'search_string'), true)
            } else {
                toggleWidget(node, findWidgetByName(node, 'search_string'))
            }
	}
}
const getSetWidgets = ['rescale_after_model', 'rescale', 'image_output', 
						'lora_name', 'lora1_name', 'lora2_name', 'lora3_name', 
						'refiner_lora1_name', 'refiner_lora2_name', 'refiner_steps', 'upscale_method', 
						'image_output', 'text_output', 'add_noise', 
						'ckpt_B_name', 'ckpt_C_name', 'save_model', 'refiner_ckpt_name',
						'num_loras', 'mode', 'toggle', 'empty_latent_aspect', 'conditioning_aspect', 'target_aspect', 'sampler_state',
                        'print_to_console', 'sampling', 'range_mode', 'file_type', 'replace_mode']
for (const type of Object.keys(TITLES)) {
  comfy.defs.extend(type,b=>{
    const setup=node=>{
      for (const w of node.widgets.all()) if (getSetWidgets.includes(w.name)) {
        widgetLogic(node,w);
        w.on('change',()=>widgetLogic(node,w));
      }
    };
    b.onCreated(setup);
    b.onConfigured(setup);
  });
}
