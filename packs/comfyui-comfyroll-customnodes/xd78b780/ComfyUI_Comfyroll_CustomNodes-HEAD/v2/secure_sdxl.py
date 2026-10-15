"""Pinned SDXL token padding, four unscheduled encodes and preset math stay pack-side."""
from comfy_api.latest import io
from .categories import icons
from .secure_schedules import _guard

def _bounded(tokens):
    if not isinstance(tokens,dict):
        raise TypeError('CLIP tokenization must return a dictionary')
    if len(tokens)>16:
        raise ValueError('CLIP token component count exceeds bound')
    _guard(dict(enumerate(tokens.values())))
    if sum(len(rows) for rows in tokens.values() if isinstance(rows,(list,tuple)))>4096:
        raise ValueError('CLIP token row workload exceeds bound')

def _pad(tokens,empty):
    _bounded(tokens)
    if len(tokens['l'])!=len(tokens['g']):
        while len(tokens['l'])<len(tokens['g']):
            if not empty['l']:
                raise ValueError('Empty l token padding would not terminate')
            tokens['l']+=empty['l']
            _bounded(tokens)
        while len(tokens['l'])>len(tokens['g']):
            if not empty['g']:
                raise ValueError('Empty g token padding would not terminate')
            tokens['g']+=empty['g']
            _bounded(tokens)
    return tokens

class CR_SDXLBasePromptEncoder(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR SDXL Base Prompt Encoder',display_name='🌟 CR SDXL Base Prompt Encoder',category=icons['Comfyroll/SDXL'],
            inputs=[io.Clip.Input('base_clip'),io.String.Input('pos_g',multiline=True,default='POS_G'),
                    io.String.Input('pos_l',multiline=True,default='POS_L'),io.String.Input('neg_g',multiline=True,default='NEG_G'),
                    io.String.Input('neg_l',multiline=True,default='NEG_L'),io.Combo.Input('preset',options=['preset A','preset B','preset C']),
                    io.Int.Input('base_width',default=4096.0,min=0,max=16384,step=64),
                    io.Int.Input('base_height',default=4096.0,min=0,max=16384,step=64),
                    io.Int.Input('crop_w',default=0,min=0,max=16384,step=64),
                    io.Int.Input('crop_h',default=0,min=0,max=16384,step=64),
                    io.Int.Input('target_width',default=4096.0,min=0,max=16384,step=64),
                    io.Int.Input('target_height',default=4096.0,min=0,max=16384,step=64)],
            outputs=[io.Conditioning.Output(display_name='base_positive'),io.Conditioning.Output(display_name='base_negative'),io.String.Output(display_name='show_help')])
    @classmethod
    async def execute(cls,base_clip,pos_g,pos_l,neg_g,neg_l,base_width,base_height,crop_w,crop_h,target_width,target_height,preset):
        _guard(dict(pos_g=pos_g,pos_l=pos_l,neg_g=neg_g,neg_l=neg_l,preset=preset))
        empty=await base_clip.tokenize('')
        _bounded(empty)
        meta=dict(width=base_width,height=base_height,crop_w=crop_w,crop_h=crop_h,target_width=target_width,target_height=target_height)
        # Preserve source order: no memoizing even repeated or unused preset calls.
        async def encode(g,l):
            tokens=await base_clip.tokenize(g)
            tokens['l']=(await base_clip.tokenize(l))['l']
            result=await base_clip.encode_from_tokens(_pad(tokens,empty))
            return await result.with_metadata(**meta)
        res1=await encode(pos_g,pos_l)
        res2=await encode(neg_g,neg_l)
        res3=await encode(pos_l,neg_l)  # Pinned positive-style quirk, not pos_l/pos_l.
        res4=await encode(neg_l,neg_l)
        if preset=='preset A':
            base_positive,base_negative=res1,res2
        elif preset=='preset B':
            base_positive,base_negative=res3,res4
        elif preset=='preset C':
            base_positive=await res1.combine(res3)
            base_negative=await res2.combine(res4)
        return io.NodeOutput(base_positive,base_negative,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/SDXL-Nodes#cr-sdxl-base-prompt-encoder')

NODE_CLASS_MAPPINGS={'CR SDXL Base Prompt Encoder':CR_SDXLBasePromptEncoder}
NODE_DISPLAY_NAME_MAPPINGS={'CR SDXL Base Prompt Encoder':'🌟 CR SDXL Base Prompt Encoder'}

