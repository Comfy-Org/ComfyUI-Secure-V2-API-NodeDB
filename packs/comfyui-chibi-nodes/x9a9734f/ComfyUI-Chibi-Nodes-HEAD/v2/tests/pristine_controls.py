"""Pinned algorithm/schema controls, with discovery authority explicitly doubled."""
import ast
import math
import types
import random
import json
import re
import hashlib
import time
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageOps, ImageFont, ImageDraw
from PIL.PngImagePlugin import PngInfo

SOURCE = Path(__file__).resolve().parents[2]
BUNDLED = sorted(p.name for p in (SOURCE/'extras/chibi-wildcards').glob('*.txt'))
FONTS = sorted(p.name for p in (SOURCE/'extras/fonts').glob('*.ttf'))
IDS = ['Loader','SimpleSampler','Prompts','ImageTool','Wildcards','LoadEmbedding',
       'ConditionText','ConditionTextPrompts','ConditionTextMulti','Textbox',
       'ImageSizeInfo','ImageSimpleResize','ImageAddText','Int2String',
       'LoadImageExtended','SeedGenerator','SaveImages','TextSplit','RandomResolutionLatent']

def control(name, **extra):
    # Extract the actual complete pinned class, not rewritten algorithms. Import
    # side effects and ambient discovery are trapped by the test-only namespace.
    tree = ast.parse((SOURCE/'nodes'/f'{name}.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    def catalogue(folder):
        return {'chibi-wildcards':BUNDLED,'chibi-fonts':FONTS,
                'checkpoints':['fixture.safetensors'],'vae':['fixture.vae'],
                'embeddings':['fixture.pt']}[folder]
    folders=types.SimpleNamespace(get_filename_list=catalogue,
        get_full_path=lambda folder,label:str(SOURCE/'extras'/
            ('fonts' if folder=='chibi-fonts' else 'chibi-wildcards')/label),
        get_input_directory=lambda:'INPUT-SENTINEL')
    env=dict(folder_paths=folders,os=types.SimpleNamespace(listdir=lambda p:[],
        path=types.SimpleNamespace(isfile=lambda p:False,join=lambda *s:'/'.join(s)),name='posix'),
        random=random,math=math,torch=torch,np=np,Image=Image,ImageOps=ImageOps,
        ImageFont=ImageFont,ImageDraw=ImageDraw,PngInfo=PngInfo,json=json,re=re,
        hashlib=hashlib,time=time,MAX_RESOLUTION=32768,args=types.SimpleNamespace(disable_metadata=False))
    env.update(extra)
    exec(compile(tree,str(SOURCE/'nodes'/f'{name}.py'),'exec'),env)
    return env[name]

def schemas():
    result={}
    for name in IDS:
        cls=control(name)
        result[name]={'inputs':cls.INPUT_TYPES(),'outputs':cls.RETURN_TYPES,
            'names':getattr(cls,'RETURN_NAMES',None),'category':cls.CATEGORY,
            'output_node':getattr(cls,'OUTPUT_NODE',False),'function':cls.FUNCTION}
    return result

if __name__=='__main__':
    print(json.dumps(schemas(),indent=2))
