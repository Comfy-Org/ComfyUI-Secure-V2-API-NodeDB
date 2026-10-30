"""Current-SDK accounting regressions; legacy algorithm/Guest suites stay separate."""
import inspect,json
from pathlib import Path
import pytest
from _current_sdk_test_support import module,torch,V2
def values(ledger,node,**changes):
    row=json.loads((V2/(ledger+'-draft-ledger.json')).read_text())[node]
    args={}
    for group,items in row['source_inputs'].items():
        for key,spec in items.items():
            typ=spec[0];opts=spec[1] if len(spec)>1 else {}
            args[key]=torch.empty((2,32,48,3),device='meta') if typ=='IMAGE' else opts.get('default',typ[0] if isinstance(typ,list) else None)
    args.update(changes);return args
def call(name,node,args):
    f=module(name)._preflight
    return f(args) if len(inspect.signature(f).parameters)==1 else f(node,args)
CASES=[
 ('secure_animation_values','animation-values','CR Cycle Text',{'text_list':[('a','text')]*256,'loops':1000}),
 ('secure_animation_values','animation-values','CR Simple Prompt List Keyframes',{'simple_prompt_list':['x'*4096]*3,'loops':100}),
 ('secure_layout','layout','CR Color Panel',{'panel_width':4096,'panel_height':4096}),
 ('secure_layout','layout','CR Overlay Transparent Image',{'overlay_scale_factor':100.}),
 ('secure_lists','list','CR Float Range List',{'start':0.,'end':4097.,'step':1.,'loops':1}),
 ('secure_masked_text','masked-text','CR Draw Text',{'text':'x'*4097}),
 ('secure_matplot','matplot','CR Color Bars',{'width':4097,'height':1}),
 ('secure_patterns','patterns','CR Draw Shape',{'width':4096,'height':4096}),
 ('secure_seeded_random','seeded-random','CR Random Hex Color',{'seed':2**4096}),
 ('secure_seeded_random','seeded-random','CR Random Multiline Values',{'rows':2049}),
 ('secure_seeded_random','seeded-random','CR Random Panel Codes',{'rows':2048,'string_length':1024}),
 ('secure_style_bars','style-bars','CR Style Bars',{'width':2048,'height':2048,'orientation':'vertical'}),
 ('secure_templates','templates','CR Comic Panel Templates',{'page_width':8193}),
 ('secure_text_panels','text-panels','CR Simple Text Panel',{'text':'x'*4097}),
]
@pytest.mark.parametrize('name,ledger,node,changes',CASES,ids=[r[2]+'-'+str(i) for i,r in enumerate(CASES)])
def test_former_fixed_cap_vectors_are_admitted_without_native_allocation(name,ledger,node,changes):
    # No tensor data, model inference, PIL canvas or literal cubic grid allocated.
    call(name,node,values(ledger,node,**changes))
@pytest.mark.parametrize('name,ledger,node',[('secure_matplot','matplot','CR Color Bars'),('secure_patterns','patterns','CR Draw Shape')])
def test_absurd_final_geometry_still_refuses(name,ledger,node):
    with pytest.raises(ValueError,match='IMAGE|runtime'):call(name,node,values(ledger,node,width=10**9,height=10**9))
def test_preview_infinite_factor_refuses_before_allocation():
    with pytest.raises(ValueError,match='finite'):call('secure_template_previews','CR Thumbnail Preview',values('template-previews','CR Thumbnail Preview',rescale_factor=float('inf')))
def test_scalar_and_list_previous_cap_vectors_are_admitted():
    module('secure_schedules')._guard({'text':'x'*262145,'lines':['x']*4097,'items':['a']*16385,'seed':1<<4097})
    module('secure_pipes')._guard({'value':['x']*17000})
    module('secure_graphics')._text_budget('x'*4097,32,0,0)
def test_depth64_liveness_guard_is_explicit():
    value=0
    for _ in range(66):value=[value]
    with pytest.raises(ValueError,match='depth|nesting'):module('secure_tensors')._preflight('control',{'value':value})
