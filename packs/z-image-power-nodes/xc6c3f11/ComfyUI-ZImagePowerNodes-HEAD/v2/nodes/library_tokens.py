"""Closed plain-data encoding of this pack's native style and palette values.

No host object, executable name, callback, or ref is represented here. Keep
parsed native commands and colors verbatim, including native constructor quirks.
"""
from .core.style import Style
from .core.palette import Palette

STYLE_FORMAT='zimage-style-data/1'
PALETTE_FORMAT='zimage-palette-data/1'

def encode_style(value):
    if value is None:return None
    if not isinstance(value,Style):raise TypeError('Expected native Style data')
    return {'format':STYLE_FORMAT,'name':value.name,'template':value.template,
            'description':value.description,'tags':value.tags,'category':value.category,
            'order':list(value.order),'version':list(value.version_tuple),
            'commands':[list(row) for row in value._commands]}

def decode_style(value):
    if not isinstance(value,dict) or value.get('format')!=STYLE_FORMAT:return value
    fields={'format','name','template','description','tags','category','order','version','commands'}
    if set(value)!=fields:raise ValueError('Invalid style data fields')
    if not all(isinstance(value[k],str) for k in ('name','template','description','tags','category')):
        raise TypeError('Style text fields must be strings')
    if not isinstance(value['order'],(list,tuple)) or len(value['order'])!=2 or not all(type(v) is int for v in value['order']):
        raise TypeError('Style order must contain two integers')
    if not isinstance(value['version'],(list,tuple)) or len(value['version'])!=3 or not all(type(v) is int for v in value['version']):
        raise TypeError('Style version must contain three integers')
    if not isinstance(value['commands'],(list,tuple)) or not all(isinstance(row,(list,tuple)) and len(row)==4 and all(isinstance(v,str) for v in row) for row in value['commands']):
        raise TypeError('Style commands must contain four strings')
    result=Style.__new__(Style)
    result.name=value['name'];result.template=value['template'];result.description=value['description']
    result.tags=value['tags'];result.category=value['category'];result.order=tuple(value['order'])
    result._versiontup=tuple(value['version']);result._commands=[tuple(row) for row in value['commands']]
    return result

def encode_palette(value):
    if value is None:return None
    if not isinstance(value,Palette):raise TypeError('Expected native Palette data')
    return {'format':PALETTE_FORMAT,'name':value.name,'description':value.description,
            'tags':value.tags,'version':list(value.version_tuple),
            'colors':[list(row) for row in value.items()]}

def decode_palette(value):
    if not isinstance(value,dict) or value.get('format')!=PALETTE_FORMAT:return value
    if set(value)!={'format','name','description','tags','version','colors'}:raise ValueError('Invalid palette data fields')
    if not all(isinstance(value[k],str) for k in ('name','description','tags')):raise TypeError('Palette text fields must be strings')
    if not isinstance(value['version'],(list,tuple)) or len(value['version'])!=3 or not all(type(v) is int for v in value['version']):
        raise TypeError('Palette version must contain three integers')
    if not isinstance(value['colors'],(list,tuple)) or not all(isinstance(row,(list,tuple)) and len(row)==4 and all(isinstance(v,str) for v in row) for row in value['colors']):
        raise TypeError('Palette colors must contain four strings')
    result=Palette.__new__(Palette)
    result.name=value['name'];result.description=value['description'];result.tags=value['tags']
    result._versiontup=tuple(value['version']);result._color_tuples=[tuple(row) for row in value['colors']]
    return result
