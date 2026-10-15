"""Exact native key loop and strict load, after explicit managed container selection."""
def load_checkpoint(checkpoint_model, model):
    ckpt = checkpoint_model

    load_dict = {}
    for k, v in ckpt.items():
        if k.startswith('module.'):
            k_ = k.replace('module.', '')
            load_dict[k_] = v
        else:
            load_dict[k] = v

    model.load_state_dict(load_dict)
    return model
