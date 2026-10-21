"""Original loader configuration for admitted trained resources (approved 1.3B T2V; I2V code path behind digest admission)."""
import torch
import numpy as np


def model_type_from_state(sd, in_channels, model_name):
    """The original loader's inference (nodes_model_loading.py:1294-1306), unchanged."""
    model_type = "t2v"
    if not "text_embedding.0.weight" in sd:
        model_type = "no_cross_attn"
    elif "model_type.Wan2_1-FLF2V-14B-720P" in sd or "img_emb.emb_pos" in sd or "flf2v" in model_name.lower():
        model_type = "fl2v"
    if "blocks.0.cross_attn.k_img.weight" in sd:
        model_type = "i2v"
    elif in_channels == 16:
        model_type = "t2v"
    elif "control_adapter.conv.weight" in sd:
        model_type = "t2v"
    if "audio_injector.injector.0.k.weight" in sd:
        model_type = "s2v"
    return model_type


def model_variant_for(model_type, dim, model_name):
    """The original loader's variant rules (nodes_model_loading.py:1374-1392), unchanged."""
    model_variant = "14B"
    if model_type == "i2v" or model_type == "fl2v":
        if "480" in model_name or "fun" in model_name.lower() or "a2" in model_name.lower() or "540" in model_name:
            model_variant = "i2v_480"
        elif "720" in model_name:
            model_variant = "i2v_720"
    elif model_type == "t2v":
        model_variant = "14B"
    if dim == 1536:
        model_variant = "1_3B"
    if "high" in model_name.lower() or "low" in model_name.lower():
        if "i2v" in model_name.lower():
            model_variant = "i2v_14B_2.2"
        else:
            model_variant = "14B_2.2"
    return model_variant


def configuration_admitted(sd, model_name, admitted):
    dim = sd['patch_embedding.weight'].shape[0]
    in_channels = sd['patch_embedding.weight'].shape[1]
    in_features = sd['blocks.0.self_attn.k.weight'].shape[1]
    out_features = sd['blocks.0.self_attn.k.weight'].shape[0]
    ffn_dim = sd['blocks.0.ffn.0.bias'].shape[0]
    ffn2_dim = sd['blocks.0.ffn.2.weight'].shape[1]
    if list(sd['patch_embedding.weight'].shape) != admitted['patch_embedding']:
        raise ValueError('Admitted resource architecture differs from its admission record')
    model_type = model_type_from_state(sd, in_channels, model_name)
    if model_type != admitted['model_type'] or model_type not in ('t2v', 'i2v'):
        raise ValueError('Admitted resource model type differs from its admission record')
    if 'vace_blocks.0.after_proj.weight' in sd or dim in (3072, 4096):
        raise NotImplementedError('VACE, 5B and LongCat resources are outside the admitted domain')
    patch_size = (1, 2, 2)
    out_dim = 16
    if dim == 5120:
        num_heads, num_layers = 40, 40
    else:
        num_heads, num_layers = 12, 30
    attention_mode = 'sdpa'
    base_dtype = torch.bfloat16
    device = offload_device = torch.device('cpu')
    model_variant = model_variant_for(model_type, dim, model_name)
    vace_layers = vace_in_dim = None
    is_humo = 'audio_proj.audio_proj_glob_1.layer.weight' in sd
    is_wananimate = 'pose_patch_embedding.weight' in sd
    rms_norm_function = 'default'
    lynx_ip_layers = lynx_ref_layers = None
    teacache_coefficients_map = {
        "1_3B": {
            "e": [2.39676752e+03, -1.31110545e+03, 2.01331979e+02, -8.29855975e+00, 1.37887774e-01],
            "e0": [-5.21862437e+04, 9.23041404e+03, -5.28275948e+02, 1.36987616e+01, -4.99875664e-02],
        },
        "14B": {
            "e": [-5784.54975374, 5449.50911966, -1811.16591783, 256.27178429, -13.02252404],
            "e0": [-3.03318725e+05, 4.90537029e+04, -2.65530556e+03, 5.87365115e+01, -3.15583525e-01],
        },
        "i2v_480": {
            "e": [-3.02331670e+02, 2.23948934e+02, -5.25463970e+01, 5.87348440e+00, -2.01973289e-01],
            "e0": [2.57151496e+05, -3.54229917e+04, 1.40286849e+03, -1.35890334e+01, 1.32517977e-01],
        },
        "i2v_720":{
            "e": [-114.36346466, 65.26524496, -18.82220707, 4.91518089, -0.23412683],
            "e0": [8.10705460e+03, 2.13393892e+03, -3.72934672e+02, 1.66203073e+01, -4.17769401e-02],
        },
        # Placeholders until TeaCache for Wan2.2 is obtained
        "14B_2.2": {
            "e": [-5784.54975374, 5449.50911966, -1811.16591783, 256.27178429, -13.02252404],
            "e0": [-3.03318725e+05, 4.90537029e+04, -2.65530556e+03, 5.87365115e+01, -3.15583525e-01],
        },
        "i2v_14B_2.2":{
            "e": [-114.36346466, 65.26524496, -18.82220707, 4.91518089, -0.23412683],
            "e0": [8.10705460e+03, 2.13393892e+03, -3.72934672e+02, 1.66203073e+01, -4.17769401e-02],
        },
    }
    magcache_ratios_map = {
        "1_3B": np.array([1.0]*2+[1.0124, 1.02213, 1.00166, 1.0041, 0.99791, 1.00061, 0.99682, 0.99762, 0.99634, 0.99685, 0.99567, 0.99586, 0.99416, 0.99422, 0.99578, 0.99575, 0.9957, 0.99563, 0.99511, 0.99506, 0.99535, 0.99531, 0.99552, 0.99549, 0.99541, 0.99539, 0.9954, 0.99536, 0.99489, 0.99485, 0.99518, 0.99514, 0.99484, 0.99478, 0.99481, 0.99479, 0.99415, 0.99413, 0.99419, 0.99416, 0.99396, 0.99393, 0.99388, 0.99386, 0.99349, 0.99349, 0.99309, 0.99304, 0.9927, 0.9927, 0.99228, 0.99226, 0.99171, 0.9917, 0.99137, 0.99135, 0.99068, 0.99063, 0.99005, 0.99003, 0.98944, 0.98942, 0.98849, 0.98849, 0.98758, 0.98757, 0.98644, 0.98643, 0.98504, 0.98503, 0.9836, 0.98359, 0.98202, 0.98201, 0.97977, 0.97978, 0.97717, 0.97718, 0.9741, 0.97411, 0.97003, 0.97002, 0.96538, 0.96541, 0.9593, 0.95933, 0.95086, 0.95089, 0.94013, 0.94019, 0.92402, 0.92414, 0.90241, 0.9026, 0.86821, 0.86868, 0.81838, 0.81939]),
        "14B": np.array([1.0]*2+[1.02504, 1.03017, 1.00025, 1.00251, 0.9985, 0.99962, 0.99779, 0.99771, 0.9966, 0.99658, 0.99482, 0.99476, 0.99467, 0.99451, 0.99664, 0.99656, 0.99434, 0.99431, 0.99533, 0.99545, 0.99468, 0.99465, 0.99438, 0.99434, 0.99516, 0.99517, 0.99384, 0.9938, 0.99404, 0.99401, 0.99517, 0.99516, 0.99409, 0.99408, 0.99428, 0.99426, 0.99347, 0.99343, 0.99418, 0.99416, 0.99271, 0.99269, 0.99313, 0.99311, 0.99215, 0.99215, 0.99218, 0.99215, 0.99216, 0.99217, 0.99163, 0.99161, 0.99138, 0.99135, 0.98982, 0.9898, 0.98996, 0.98995, 0.9887, 0.98866, 0.98772, 0.9877, 0.98767, 0.98765, 0.98573, 0.9857, 0.98501, 0.98498, 0.9838, 0.98376, 0.98177, 0.98173, 0.98037, 0.98035, 0.97678, 0.97677, 0.97546, 0.97543, 0.97184, 0.97183, 0.96711, 0.96708, 0.96349, 0.96345, 0.95629, 0.95625, 0.94926, 0.94929, 0.93964, 0.93961, 0.92511, 0.92504, 0.90693, 0.90678, 0.8796, 0.87945, 0.86111, 0.86189]),
        "i2v_480": np.array([1.0]*2+[0.98783, 0.98993, 0.97559, 0.97593, 0.98311, 0.98319, 0.98202, 0.98225, 0.9888, 0.98878, 0.98762, 0.98759, 0.98957, 0.98971, 0.99052, 0.99043, 0.99383, 0.99384, 0.98857, 0.9886, 0.99065, 0.99068, 0.98845, 0.98847, 0.99057, 0.99057, 0.98957, 0.98961, 0.98601, 0.9861, 0.98823, 0.98823, 0.98756, 0.98759, 0.98808, 0.98814, 0.98721, 0.98724, 0.98571, 0.98572, 0.98543, 0.98544, 0.98157, 0.98165, 0.98411, 0.98413, 0.97952, 0.97953, 0.98149, 0.9815, 0.9774, 0.97742, 0.97825, 0.97826, 0.97355, 0.97361, 0.97085, 0.97087, 0.97056, 0.97055, 0.96588, 0.96587, 0.96113, 0.96124, 0.9567, 0.95681, 0.94961, 0.94969, 0.93973, 0.93988, 0.93217, 0.93224, 0.91878, 0.91896, 0.90955, 0.90954, 0.92617, 0.92616]),
        "i2v_720": np.array([1.0]*2+[0.99428, 0.99498, 0.98588, 0.98621, 0.98273, 0.98281, 0.99018, 0.99023, 0.98911, 0.98917, 0.98646, 0.98652, 0.99454, 0.99456, 0.9891, 0.98909, 0.99124, 0.99127, 0.99102, 0.99103, 0.99215, 0.99212, 0.99515, 0.99515, 0.99576, 0.99572, 0.99068, 0.99072, 0.99097, 0.99097, 0.99166, 0.99169, 0.99041, 0.99042, 0.99201, 0.99198, 0.99101, 0.99101, 0.98599, 0.98603, 0.98845, 0.98844, 0.98848, 0.98851, 0.98862, 0.98857, 0.98718, 0.98719, 0.98497, 0.98497, 0.98264, 0.98263, 0.98389, 0.98393, 0.97938, 0.9794, 0.97535, 0.97536, 0.97498, 0.97499, 0.973, 0.97301, 0.96827, 0.96828, 0.96261, 0.96263, 0.95335, 0.9534, 0.94649, 0.94655, 0.93397, 0.93414, 0.91636, 0.9165, 0.89088, 0.89109, 0.8679, 0.86768]),
        "14B_2.2": np.array([1.0]*2+[0.99505, 0.99389, 0.99441, 0.9957, 0.99558, 0.99551, 0.99499, 0.9945, 0.99534, 0.99548, 0.99468, 0.9946, 0.99463, 0.99458, 0.9946, 0.99453, 0.99408, 0.99404, 0.9945, 0.99441, 0.99409, 0.99398, 0.99403, 0.99397, 0.99382, 0.99377, 0.99349, 0.99343, 0.99377, 0.99378, 0.9933, 0.99328, 0.99303, 0.99301, 0.99217, 0.99216, 0.992, 0.99201, 0.99201, 0.99202, 0.99133, 0.99132, 0.99112, 0.9911, 0.99155, 0.99155, 0.98958, 0.98957, 0.98959, 0.98958, 0.98838, 0.98835, 0.98826, 0.98825, 0.9883, 0.98828, 0.98711, 0.98709, 0.98562, 0.98561, 0.98511, 0.9851, 0.98414, 0.98412, 0.98284, 0.98282, 0.98104, 0.98101, 0.97981, 0.97979, 0.97849, 0.97849, 0.97557, 0.97554, 0.97398, 0.97395, 0.97171, 0.97166, 0.96917, 0.96913, 0.96511, 0.96507, 0.96263, 0.96257, 0.95839, 0.95835, 0.95483, 0.95475, 0.94942, 0.94936, 0.9468, 0.94678, 0.94583, 0.94594, 0.94843, 0.94872, 0.96949, 0.97015]),
        "i2v_14B_2.2": np.array([1.0]*2+[0.99512, 0.99559, 0.99559, 0.99561, 0.99595, 0.99577, 0.99512, 0.99512, 0.99546, 0.99534, 0.99543, 0.99531, 0.99496, 0.99491, 0.99504, 0.99499, 0.99444, 0.99449, 0.99481, 0.99481, 0.99435, 0.99435, 0.9943, 0.99431, 0.99411, 0.99406, 0.99373, 0.99376, 0.99413, 0.99405, 0.99363, 0.99359, 0.99335, 0.99331, 0.99244, 0.99243, 0.99229, 0.99229, 0.99239, 0.99236, 0.99163, 0.9916, 0.99149, 0.99151, 0.99191, 0.99192, 0.9898, 0.98981, 0.9899, 0.98987, 0.98849, 0.98849, 0.98846, 0.98846, 0.98861, 0.98861, 0.9874, 0.98738, 0.98588, 0.98589, 0.98539, 0.98534, 0.98444, 0.98439, 0.9831, 0.98309, 0.98119, 0.98118, 0.98001, 0.98, 0.97862, 0.97859, 0.97555, 0.97558, 0.97392, 0.97388, 0.97152, 0.97145, 0.96871, 0.9687, 0.96435, 0.96434, 0.96129, 0.96127, 0.95639, 0.95638, 0.95176, 0.95175, 0.94446, 0.94452, 0.93972, 0.93974, 0.93575, 0.9359, 0.93537, 0.93552, 0.96655, 0.96616]),
    }
    TRANSFORMER_CONFIG= {
        "dim": dim,
        "in_features": in_features,
        "out_features": out_features,
        "patch_size": patch_size,
        "ffn_dim": ffn_dim,
        "ffn2_dim": ffn2_dim,
        "eps": 1e-06,
        "freq_dim": 256,
        "in_dim": in_channels,
        "model_type": model_type,
        "out_dim": out_dim,
        "text_len": 512,
        "num_heads": num_heads,
        "num_layers": num_layers,
        "attention_mode": attention_mode,
        "rope_func": "comfy",
        "main_device": device,
        "offload_device": offload_device,
        "dtype": base_dtype,
        "teacache_coefficients": teacache_coefficients_map[model_variant],
        "magcache_ratios": magcache_ratios_map[model_variant],
        "vace_layers": vace_layers,
        "vace_in_dim": vace_in_dim,
        "inject_sample_info": True if "fps_embedding.weight" in sd else False,
        "add_ref_conv": True if "ref_conv.weight" in sd else False,
        "in_dim_ref_conv": sd["ref_conv.weight"].shape[1] if "ref_conv.weight" in sd else None,
        "add_control_adapter": True if "control_adapter.conv.weight" in sd else False,
        "use_motion_attn": True if "blocks.0.motion_attn.k.weight" in sd else False,
        "enable_adain": True if "audio_injector.injector_adain_layers.0.linear.weight" in sd else False,
        "cond_dim": sd["cond_encoder.weight"].shape[1] if "cond_encoder.weight" in sd else 0,
        "zero_timestep": model_type == "s2v",
        "humo_audio": is_humo,
        "is_wananimate": is_wananimate,
        "rms_norm_function": rms_norm_function,
        "lynx_ip_layers": lynx_ip_layers,
        "lynx_ref_layers": lynx_ref_layers,
        "is_longcat": dim == 4096,

    }
    return TRANSFORMER_CONFIG
