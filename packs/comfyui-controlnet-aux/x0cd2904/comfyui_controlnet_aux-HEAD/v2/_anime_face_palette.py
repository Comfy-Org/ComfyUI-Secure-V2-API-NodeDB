import numpy as np

COLOR_BACKGROUND = (255,255,0)

COLOR_HAIR = (0,0,255)

COLOR_EYE = (255,0,0)

COLOR_MOUTH = (255,255,255)

COLOR_FACE = (0,255,0)

COLOR_SKIN = (0,255,255)

COLOR_CLOTHES = (255,0,255)

PALETTE = [COLOR_BACKGROUND,COLOR_HAIR,COLOR_EYE,COLOR_MOUTH,COLOR_FACE,COLOR_SKIN,COLOR_CLOTHES]

def seg2img(src):
    src = np.moveaxis(src,0,2)
    dst = [[PALETTE[np.argmax(val)] for val in buf]for buf in src]
    
    return np.array(dst).astype(np.uint8)
