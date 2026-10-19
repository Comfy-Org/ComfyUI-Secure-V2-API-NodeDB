"""Source-extracted node computations; host operations use the public SDK."""
from __future__ import annotations
import torch
import numpy as np
import random
from PIL import Image, ImageDraw, ImageFont
from comfy_api.latest import sdk
from ._ops import *

class ttN_compareInput:

    def debug(_, **kwargs):
        values = []
        for key, value in kwargs.items():
            if key == 'console_title':
                print(value)
            else:
                print(f'{key}: {value}')
                values.append(value)
        return tuple()
