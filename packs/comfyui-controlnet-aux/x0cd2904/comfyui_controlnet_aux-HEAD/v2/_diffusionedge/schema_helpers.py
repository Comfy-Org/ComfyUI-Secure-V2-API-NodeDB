from enum import Enum
MAX_RESOLUTION=16384

class INPUT(Enum):
    def IMAGE():
        return ("IMAGE",)
    def LATENT():
        return ("LATENT",)
    def MASK():
        return ("MASK",)
    def SEED(default=0):
        return ("INT", dict(default=default, min=0, max=0xffffffffffffffff))
    def RESOLUTION(default=512, min=64, max=MAX_RESOLUTION, step=64): 
        return ("INT", dict(default=default, min=min, max=max, step=step))
    def INT(default=0, min=0, max=MAX_RESOLUTION, step=1): 
        return ("INT", dict(default=default, min=min, max=max, step=step))
    def FLOAT(default=0, min=0, max=1, step=0.01):
        return ("FLOAT", dict(default=default, min=min, max=max, step=step))
    def STRING(default='', multiline=False): 
        return ("STRING", dict(default=default, multiline=multiline))
    def COMBO(values, default=None):
        return (values, dict(default=values[0] if default is None else default))
    def BOOLEAN(default=True):
        return ("BOOLEAN", dict(default=default))

def define_preprocessor_inputs(**arguments):
    return dict(
        required=dict(image=INPUT.IMAGE()),
        optional=arguments
    )
