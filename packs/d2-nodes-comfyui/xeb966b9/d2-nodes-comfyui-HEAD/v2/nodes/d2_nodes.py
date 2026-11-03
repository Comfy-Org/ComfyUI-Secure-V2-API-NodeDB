from comfy_api.latest import io, sdk
from ._secure_boundary import SecureConversionRefusal, data_input


class D2_KSampler(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 KSampler', display_name='D2 KSampler', category='D2', is_output_node=True, inputs=[io.Model.Input('model', optional=True), io.Clip.Input('clip', optional=True), io.Vae.Input('vae', optional=True), io.Int.Input('seed', default=0, min=0, max=18446744073709551615), io.Int.Input('steps', default=20, min=1, max=10000), io.Float.Input('cfg', default=7.0, min=0.0, max=100.0, step=0.01), io.Combo.Input('sampler_name', options=['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'cfgpp_ud10_ab', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']), io.Combo.Input('scheduler', options=['simple', 'sgm_uniform', 'karras', 'exponential', 'ddim_uniform', 'beta', 'normal', 'linear_quadratic', 'kl_optimal']), io.Latent.Input('latent_image'), io.Float.Input('denoise', default=1.0, min=0.0, max=1.0, step=0.01), io.Combo.Input('preview_method', options=['auto', 'latent2rgb', 'taesd', 'vae_decoded_only', 'none']), io.String.Input('positive', default='', multiline=True), io.String.Input('negative', default='', multiline=True), io.Custom('D2_CNET_STACK').Input('cnet_stack', optional=True), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.Latent.Output(display_name='LATENT'), io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='positive'), io.String.Output(display_name='formatted_positive'), io.String.Output(display_name='negative'), io.Conditioning.Output(display_name='positive_cond'), io.Conditioning.Output(display_name='negative_cond'), io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe')], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo, io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 KSampler is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 KSampler is not yet converted to Secure Nodes V2: The source emits a D2_TD2Pipe dataclass containing live objects, mutates process preview policy, and uses a pack-specific controlnet stack; its complete output contract has no faithful public guest representation.')


class D2_KSamplerAdvanced(D2_KSampler):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 KSampler(Advanced)', display_name='D2 KSampler(Advanced)', category='D2', is_output_node=True, inputs=[io.Model.Input('model', optional=True), io.Clip.Input('clip', optional=True), io.Vae.Input('vae', optional=True), io.Combo.Input('add_noise', options=['enable', 'disable']), io.Int.Input('noise_seed', default=0, min=0, max=18446744073709551615), io.Int.Input('steps', default=20, min=1, max=10000), io.Float.Input('cfg', default=7.0, min=0.0, max=100.0, step=0.01), io.Combo.Input('sampler_name', options=['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'cfgpp_ud10_ab', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']), io.Combo.Input('scheduler', options=['simple', 'sgm_uniform', 'karras', 'exponential', 'ddim_uniform', 'beta', 'normal', 'linear_quadratic', 'kl_optimal']), io.Latent.Input('latent_image'), io.Int.Input('start_at_step', default=0, min=0, max=10000), io.Int.Input('end_at_step', default=10000, min=0, max=10000), io.Combo.Input('return_with_leftover_noise', options=['disable', 'enable']), io.Combo.Input('token_normalization', options=['none', 'mean', 'length', 'length+mean']), io.Combo.Input('weight_interpretation', options=['comfy', 'A1111', 'compel', 'comfy++', 'down_weight']), io.Combo.Input('preview_method', options=['auto', 'latent2rgb', 'taesd', 'vae_decoded_only', 'none']), io.String.Input('positive', default='', multiline=True), io.String.Input('negative', default='', multiline=True), io.Conditioning.Input('positive_cond', optional=True), io.Conditioning.Input('negative_cond', optional=True), io.Custom('D2_CNET_STACK').Input('cnet_stack', optional=True), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True)], outputs=[io.Image.Output(display_name='IMAGE'), io.Latent.Output(display_name='LATENT'), io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='positive'), io.String.Output(display_name='formatted_positive'), io.String.Output(display_name='negative'), io.Conditioning.Output(display_name='positive_cond'), io.Conditioning.Output(display_name='negative_cond'), io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe')], hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo, io.Hidden.unique_id])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 KSampler(Advanced) is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 KSampler(Advanced) is not yet converted to Secure Nodes V2: The inherited sampler contract includes the live-object D2_TD2Pipe and process preview policy; no faithful public guest representation.')


class D2_CheckpointLoader(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Checkpoint Loader', display_name='D2 Checkpoint Loader', category='D2', inputs=[io.Combo.Input('ckpt_name', options=[], remote=io.RemoteOptions(route='/models/checkpoints', refresh_button=True)), io.Boolean.Input('auto_vpred', default=True), io.Combo.Input('sampling', options=['normal', 'eps', 'v_prediction', 'lcm', 'x0']), io.Boolean.Input('zsnr', default=False), io.Float.Input('multiplier', default=0.6, min=0.0, max=1.0, step=0.01), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True)], outputs=[io.Model.Output(display_name='model'), io.Clip.Output(display_name='clip'), io.Vae.Output(display_name='vae'), io.String.Output(display_name='ckpt_name'), io.String.Output(display_name='ckpt_hash'), io.String.Output(display_name='ckpt_fullpath'), io.String.Output(display_name='sampling'), io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe')], hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo, io.Hidden.prompt])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Checkpoint Loader is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Checkpoint Loader is not yet converted to Secure Nodes V2: The source emits a cached SHA prefix and the absolute checkpoint path, and constructs a live-object D2_TD2Pipe; these are not public guest values.')


class D2_LoadDiffusionModel(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load Diffusion Model', display_name='D2 Load Diffusion Model', category='D2', inputs=[io.Combo.Input('unet_name', options=[], remote=io.RemoteOptions(route='/models/diffusion_models', refresh_button=True)), io.Combo.Input('weight_dtype', options=['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2']), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True)], outputs=[io.Model.Output(display_name='model'), io.String.Output(display_name='ckpt_name'), io.String.Output(display_name='ckpt_hash'), io.String.Output(display_name='ckpt_fullpath'), io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load Diffusion Model is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load Diffusion Model is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_LoadDiffusionModelSet(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load Diffusion Model Set', display_name='D2 Load Diffusion Model Set', category='D2', inputs=[io.Combo.Input('unet_name', options=[], remote=io.RemoteOptions(route='/models/diffusion_models', refresh_button=True)), io.Combo.Input('weight_dtype', options=['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2']), io.Combo.Input('vae_name', options=['pixel_space'], remote=io.RemoteOptions(route='/models/vae', refresh_button=True)), io.Combo.Input('clip_name', options=[], remote=io.RemoteOptions(route='/models/text_encoders', refresh_button=True)), io.Combo.Input('clip_type', options=['stable_diffusion', 'stable_cascade', 'sd3', 'stable_audio', 'mochi', 'ltxv', 'pixart', 'cosmos', 'lumina2', 'wan', 'hidream', 'chroma', 'ace', 'omnigen2', 'qwen_image', 'hunyuan_image', 'flux2', 'ovis', 'longcat_image', 'cogvideox', 'lens', 'pixeldit', 'ideogram4', 'boogu', 'krea2', 'joyimage', 'mage', 'minimax', 'yue2']), io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True)], outputs=[io.Model.Output(display_name='model'), io.Clip.Output(display_name='clip'), io.Vae.Output(display_name='vae'), io.String.Output(display_name='ckpt_name'), io.String.Output(display_name='ckpt_hash'), io.String.Output(display_name='ckpt_fullpath'), io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load Diffusion Model Set is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load Diffusion Model Set is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_ControlnetLoader(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Controlnet Loader', display_name='D2 Controlnet Loader', category='D2', inputs=[io.Combo.Input('controlnet_type', options=['StableDiffusion', 'Anima']), io.Combo.Input('controlnet_name', options=[], remote=io.RemoteOptions(route='/models/controlnet', refresh_button=True)), io.Image.Input('image'), io.Float.Input('strength', default=1.0, min=0.0, max=10.0, step=0.001), io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.001), io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.001), io.Mask.Input('mask', optional=True), io.Vae.Input('vae', optional=True), io.Custom('D2_CNET_STACK').Input('cnet_stack', optional=True)], outputs=[io.Custom('D2_CNET_STACK').Output(display_name='cnet_stack')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Controlnet Loader is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Controlnet Loader is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_MergeCnet(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Merge Cnet', display_name='D2 Merge Cnet', category='D2', inputs=[io.Int.Input('cnet_stack_count', default=2, min=1, max=10, step=1)], outputs=[io.Custom('D2_CNET_STACK').Output(display_name='cnet_stack')], accept_all_inputs=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Merge Cnet is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Merge Cnet is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_LoadLora(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Load Lora', display_name='D2 Load Lora', category='D2', inputs=[io.Model.Input('model'), io.Clip.Input('clip'), io.String.Input('prompt', multiline=True), io.Combo.Input('mode', options=['a1111', 'simple']), io.Combo.Input('insert_lora', options=['CHOOSE'], remote=io.RemoteOptions(route='/models/loras', refresh_button=True))], outputs=[io.Model.Output(display_name='MODEL'), io.Clip.Output(display_name='CLIP'), io.String.Output(display_name='prompt'), io.String.Output(display_name='formatted_prompt')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Load Lora is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Load Lora is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_Pipe(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Pipe', display_name='D2 Pipe', category='D2', inputs=[io.Custom('D2_TD2Pipe').Input('d2_pipe', optional=True), io.String.Input('ckpt_name', force_input=True, optional=True), io.String.Input('positive', force_input=True, optional=True), io.String.Input('negative', force_input=True, optional=True), io.Int.Input('seed', force_input=True, optional=True), io.Int.Input('steps', force_input=True, optional=True), io.Float.Input('cfg', force_input=True, optional=True), io.String.Input('sampler_name', force_input=True, optional=True), io.String.Input('scheduler', force_input=True, optional=True), io.Float.Input('denoise', force_input=True, optional=True), io.Int.Input('width', force_input=True, optional=True), io.Int.Input('height', force_input=True, optional=True), io.Model.Input('model', optional=True), io.Clip.Input('clip', optional=True), io.Vae.Input('vae', optional=True), io.Conditioning.Input('positive_cond', optional=True), io.Conditioning.Input('negative_cond', optional=True)], outputs=[io.Custom('D2_TD2Pipe').Output(display_name='d2_pipe'), io.String.Output(display_name='ckpt_name'), io.String.Output(display_name='positive'), io.String.Output(display_name='negative'), io.Int.Output(display_name='seed'), io.Int.Output(display_name='steps'), io.Float.Output(display_name='cfg'), io.String.Output(display_name='sampler_name'), io.String.Output(display_name='scheduler'), io.Float.Output(display_name='denoise'), io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Model.Output(display_name='model'), io.Clip.Output(display_name='clip'), io.Vae.Output(display_name='vae'), io.Conditioning.Output(display_name='positive_cond'), io.Conditioning.Output(display_name='negative_cond')])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Pipe is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Pipe is not yet converted to Secure Nodes V2: The source consumes and emits a D2_TD2Pipe dataclass containing live MODEL/CLIP/VAE/CONDITIONING objects; opaque refs cannot be read and replacing the dataclass with a dict would change the output type.')


class D2_AnyDelivery(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Any Delivery', display_name='D2 Any Delivery', category='D2', inputs=[io.Custom('D2_TDelivery').Input('_package', optional=True), io.String.Input('_label', default='', optional=True), io.Custom('D2_BUTTON').Input('_update', optional=True)], outputs=[io.Custom('D2_TDelivery').Output(display_name='_package')], hidden=[io.Hidden.prompt], accept_all_inputs=True)

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Any Delivery is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Any Delivery is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


class D2_PresetSelector(io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(node_id='D2 Preset Selector', display_name='D2 Preset Selector', category='D2', inputs=[io.Combo.Input('preset', options=[]), io.String.Input('preset_text', multiline=True, default='cfg;steps\nFLOAT;INT\nAnima;2;15\nIllustrious;5;20'), io.String.Input('preset_name', force_input=True, optional=True), io.Custom('D2_BUTTON').Input('_update', optional=True)], outputs=[])

    @classmethod
    def validate_inputs(cls, **kwargs):
        return 'd2-nodes-comfyui/D2 Preset Selector is not yet converted to Secure Nodes V2'

    @classmethod
    async def execute(cls, **kwargs):
        raise SecureConversionRefusal('d2-nodes-comfyui/D2 Preset Selector is not yet converted to Secure Nodes V2: This node is outside the completed backend subset; its original implementation is not imported into the guest.')


NODE_CLASS_MAPPINGS = {
    "D2 KSampler": D2_KSampler,
    "D2 KSampler(Advanced)": D2_KSamplerAdvanced,
    "D2 Checkpoint Loader": D2_CheckpointLoader,
    "D2 Load Diffusion Model": D2_LoadDiffusionModel,
    "D2 Load Diffusion Model Set": D2_LoadDiffusionModelSet,
    "D2 Controlnet Loader": D2_ControlnetLoader,
    "D2 Merge Cnet": D2_MergeCnet,
    "D2 Load Lora": D2_LoadLora,
    "D2 Pipe": D2_Pipe,
    "D2 Any Delivery": D2_AnyDelivery,
    "D2 Preset Selector": D2_PresetSelector,
}
