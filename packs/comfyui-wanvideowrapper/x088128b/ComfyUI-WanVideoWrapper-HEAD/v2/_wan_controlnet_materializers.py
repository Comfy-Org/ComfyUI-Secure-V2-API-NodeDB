"""Pack-owned ControlNet construction, awaiting the shared device/lifecycle binding.

These complete constructors preserve the pinned original loader math. They are
deliberately not registered graph nodes. The consumer must supply its actual
main/offload device policy, genuine safe-loaded state on the selected device,
and its scoped empty-cache operation. No Core imports or hidden CPU fallback.
"""
import gc
import logging
import torch
from accelerate import init_empty_weights
from accelerate.utils import set_module_tensor_to_device

log = logging.getLogger(__name__)


def _base_dtype(base_precision):
    return {'fp8_e4m3fn':torch.float8_e4m3fn,'fp8_e4m3fn_fast':torch.float8_e4m3fn,
            'bf16':torch.bfloat16,'fp16':torch.float16,'fp16_fast':torch.float16,
            'fp32':torch.float32}[base_precision]


def _effective_quantization(state, quantization):
    if quantization == 'disabled':
        for key, value in state.items():
            if isinstance(value,torch.Tensor):
                if value.dtype == torch.float8_e4m3fn:
                    quantization = 'fp8_e4m3fn'
                    break
                elif value.dtype == torch.float8_e5m2:
                    quantization = 'fp8_e5m2'
                    break
    return quantization


def _weight_dtype(quantization, base_dtype):
    if 'fp8_e4m3fn' in quantization:
        return torch.float8_e4m3fn
    elif quantization == 'fp8_e5m2':
        return torch.float8_e5m2
    return base_dtype


def materialize_controlnet(sd, base_precision, load_device, quantization, *,
                          main_device, offload_device, soft_empty_cache):
    """Materialize the original TheDenk architecture from owned safe state.

    Device arguments and cleanup are injected by the lifecycle owner. Callers
    must already have read the state onto main_device for 'main_device', and
    onto offload_device otherwise, matching the original read order.
    """
    transformer_load_device = main_device if load_device == 'main_device' else offload_device
    base_dtype = _base_dtype(base_precision)
    num_layers = 8 if 'blocks.7.scale_shift_table' in sd else 6
    out_proj_dim = sd['controlnet_blocks.0.bias'].shape[0]
    downscale_coef = 16 if out_proj_dim == 3072 else 8
    vae_channels = 48 if out_proj_dim == 3072 else 16
    if 'control_encoder.0.0.weight' not in sd:
        raise ValueError('Invalid ControlNet model')
    controlnet_cfg = {
        'added_kv_proj_dim':None,'attention_head_dim':128,'cross_attn_norm':None,
        'downscale_coef':downscale_coef,'eps':1e-06,'ffn_dim':8960,'freq_dim':256,
        'image_dim':None,'in_channels':3,'num_attention_heads':12,'num_layers':num_layers,
        'out_proj_dim':out_proj_dim,'patch_size':[1,2,2],'qk_norm':'rms_norm_across_heads',
        'rope_max_seq_len':1024,'text_dim':4096,'vae_channels':vae_channels,
    }
    from .controlnet.wan_controlnet import WanControlnet
    with init_empty_weights():
        controlnet = WanControlnet(**controlnet_cfg)
    controlnet.eval()
    quantization = _effective_quantization(sd,quantization)
    dtype = _weight_dtype(quantization,base_dtype)
    params_to_keep = {'norm','head','time_in','vector_in','controlnet_patch_embedding',
                     'time_','img_emb','modulation','text_embedding','adapter'}
    for name, param in controlnet.named_parameters():
        dtype_to_use = base_dtype if any(keyword in name for keyword in params_to_keep) else dtype
        if 'controlnet_patch_embedding' in name:
            dtype_to_use = torch.float32
        set_module_tensor_to_device(controlnet,name,device=transformer_load_device,dtype=dtype_to_use,value=sd[name])
    del sd
    if load_device == 'offload_device' and controlnet.device != offload_device:
        controlnet.to(offload_device)
        gc.collect()
        soft_empty_cache()
    return controlnet


def materialize_uni3c_controlnet(sd, base_precision, load_device, quantization,
                               attention_mode, compile_args=None, *,
                               main_device, offload_device, soft_empty_cache):
    """Materialize the whole original Uni3C architecture and compile policy.

    The constructor's quantized flag intentionally uses the *requested* value
    before checkpoint dtype autodetection, as it does in the native loader.
    """
    transformer_load_device = main_device if load_device == 'main_device' else offload_device
    base_dtype = _base_dtype(base_precision)
    if 'controlnet_patch_embedding.weight' not in sd:
        raise ValueError('Invalid ControlNet model')
    in_channels = sd['controlnet_patch_embedding.weight'].shape[1]
    ffn_dim = sd['controlnet_blocks.0.ffn.0.bias'].shape[0]
    controlnet_cfg = {
        'in_channels':in_channels,'conv_out_dim':5120,'time_embed_dim':5120,
        'dim':1024,'ffn_dim':ffn_dim,'num_heads':16,'num_layers':20,
        'add_channels':7,'mid_channels':256,'attention_mode':attention_mode,
        'quantized':True if quantization != 'disabled' else False,'base_dtype':base_dtype,
    }
    from .uni3c.controlnet import WanControlNet
    with init_empty_weights():
        controlnet = WanControlNet(controlnet_cfg)
    controlnet.eval()
    quantization = _effective_quantization(sd,quantization)
    dtype = _weight_dtype(quantization,base_dtype)
    params_to_keep = {'norm','head','time_in','vector_in','controlnet_patch_embedding',
                     'time_','img_emb','modulation','text_embedding','adapter','proj_in'}
    for name, param in controlnet.named_parameters():
        dtype_to_use = base_dtype if any(keyword in name for keyword in params_to_keep) else dtype
        if 'controlnet_patch_embedding' in name:
            dtype_to_use = torch.float32
        set_module_tensor_to_device(controlnet,name,device=transformer_load_device,dtype=dtype_to_use,value=sd[name])
    del sd
    if compile_args is not None:
        if hasattr(torch,'_dynamo') and hasattr(torch._dynamo,'config'):
            torch._dynamo.config.cache_size_limit = compile_args['dynamo_cache_size_limit']
            torch._dynamo.config.force_parameter_static_shapes = compile_args['force_parameter_static_shapes']
            try:
                torch._dynamo.config.recompile_limit = compile_args['dynamo_recompile_limit']
            except Exception as error:
                log.warning(f'Could not set recompile_limit: {error}')
        if compile_args['compile_transformer_blocks_only']:
            for i, block in enumerate(controlnet.controlnet_blocks):
                controlnet.controlnet_blocks[i] = torch.compile(block,fullgraph=compile_args['fullgraph'],
                    dynamic=compile_args['dynamic'],backend=compile_args['backend'],mode=compile_args['mode'])
        else:
            controlnet = torch.compile(controlnet,fullgraph=compile_args['fullgraph'],
                dynamic=compile_args['dynamic'],backend=compile_args['backend'],mode=compile_args['mode'])
    if load_device == 'offload_device' and controlnet.device != offload_device:
        controlnet.to(offload_device)
        gc.collect()
        soft_empty_cache()
    return controlnet
