import torch
def load_checkpoint(loaded, model):
    ckpt = loaded

    load_dict = {}
    for k, v in ckpt.items():
        if k.startswith('module.'):
            k_ = k.replace('module.', '')
            load_dict[k_] = v
        else:
            load_dict[k] = v

    # Load compatible weights only
    model_state = model.state_dict()
    compatible_dict = {}
    skipped_keys = []
    
    for k, v in load_dict.items():
        if k in model_state:
            if model_state[k].shape == v.shape:
                compatible_dict[k] = v
            else:
                skipped_keys.append(f"{k}: checkpoint {v.shape} vs model {model_state[k].shape}")
        else:
            skipped_keys.append(f"{k}: not found in model")
    
    print(f"Loading checkpoint: {len(compatible_dict)} compatible, {len(skipped_keys)} skipped")
    if skipped_keys:
        print("Skipped keys with shape mismatches:")
        for key in skipped_keys[:5]:  # Show first 5 mismatches
            print(f"  {key}")
        if len(skipped_keys) > 5:
            print(f"  ... and {len(skipped_keys) - 5} more")
    
    model.load_state_dict(compatible_dict, strict=False)
    return model
