"""All twelve legacy algorithms run through public V3 declarations."""
import re
import unicodedata
from comfy_api.latest import io,sdk
from . import nodes as algorithms
from . import _rng,_limits

def typed_input(name,spec,optional=False):
    kind=spec[0]
    options=dict(spec[1]) if len(spec)>1 else {}
    if 'display' in options:
        options['display_mode']=io.NumberDisplay(options.pop('display'))
    options['optional']=optional
    if type(kind) is list:
        return io.Combo.Input(name,options=kind,**options)
    domain={'STRING':io.String,'INT':io.Int,'FLOAT':io.Float,'BOOLEAN':io.Boolean}[kind]
    return domain.Input(name,**options)

def preflight(node_id,kwargs):
    total=0
    for value in kwargs.values():
        if type(value) is str:
            _limits.check_text(value);total+=len(value.encode('utf-8'))
    if total>_limits.MAX_TEXT_BYTES:
        raise ValueError('aggregate text byte budget exceeded')
    if node_id=='EbuPromptHelperRandomize':
        value=kwargs['replacement_options']
        delim=kwargs['delimit_options_with']
        values=value.split(',') if delim=='commas' else value.split(';') if delim=='semi-colons' else value.splitlines()
        work=0
        for option in values:
            option=option.strip()
            if not option:
                continue
            match=re.match(r'^\s*(\d+)\s*>>(.*)$',option)
            if match:
                weight=int(match.group(1))
                if weight>0 and match.group(2).strip():work+=weight
            else:work+=1
            if work>_limits.MAX_TICKETS:
                raise ValueError('weighted ticket budget exceeded')

def logical_name(directory,file_name):
    for value in (directory,file_name):
        _limits.check_text(value)
        if len(value.encode('utf-8'))>1024 or '\\' in value or ':' in value or value.startswith('/') or any(unicodedata.category(c)=='Cc' for c in value):
            raise ValueError('managed INPUT logical label required')
        if any(part in ('.','..') for part in value.split('/')):
            raise ValueError('managed INPUT traversal refused')
    return '/'.join(v for v in (directory.rstrip('/'),file_name) if v)

async def load_text(directory,file_name):
    name=logical_name(directory,file_name)
    if not name:return ('',)
    if not await sdk.ctx().assets.exists('input',name):
        return ('',)
    try:
        ref=await sdk.ctx().assets.resolve('input',name)
        size=await sdk.ctx().assets.size(ref)
    except FileNotFoundError:
        return ('',)
    if size>_limits.MAX_TEXT_BYTES:
        raise ValueError('managed text asset byte budget exceeded')
    try:
        data=await sdk.ctx().assets.read_range(ref,offset=0,length=_limits.MAX_TEXT_BYTES+1)
    except FileNotFoundError:
        return ('',)
    if len(data)>_limits.MAX_TEXT_BYTES or len(data)!=size:
        raise ValueError('managed text asset changed or exceeded byte budget')
    try:
        return (data.decode('utf-8').replace('\r\n','\n').replace('\r','\n'),)
    except UnicodeDecodeError:
        return ('',)

def make(source,node_id):
    class Secure(io.ComfyNode):
        SDK_REFS=False
        SDK_PERMISSIONS=('assets',) if node_id=='EbuPromptHelperLoadFileAsString' else ()
        @classmethod
        def define_schema(cls):
            spec=source.INPUT_TYPES()
            return io.Schema(node_id=node_id,
                display_name=algorithms.NODE_DISPLAY_NAME_MAPPINGS[node_id],
                category=source.CATEGORY,
                inputs=[typed_input(name,value,kind=='optional') for kind,rows in spec.items() for name,value in rows.items()],
                outputs=[io.String.Output(display_name=name) for name in getattr(source,'RETURN_NAMES',['STRING']*len(source.RETURN_TYPES))])
        @classmethod
        async def execute(cls,**kwargs):
            preflight(node_id,kwargs)
            with _rng.scope(),_limits.scope():
                result=await load_text(**kwargs) if node_id=='EbuPromptHelperLoadFileAsString' else getattr(source(),source.FUNCTION)(**kwargs)
            for text in result:_limits.check_text(text)
            return io.NodeOutput(*result)
    Secure.__name__=source.__name__+'Secure'
    globals()[Secure.__name__]=Secure
    return Secure
NODE_CLASS_MAPPINGS={identity:make(source,identity) for identity,source in algorithms.NODE_CLASS_MAPPINGS.items()}
NODE_DISPLAY_NAME_MAPPINGS=dict(algorithms.NODE_DISPLAY_NAME_MAPPINGS)
