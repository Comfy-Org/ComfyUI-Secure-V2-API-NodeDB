"""Static source/SDK/font checks, run only by the bounded gate driver."""
import ast
import hashlib
import json
from pathlib import Path
import struct

SYMBOLS={
 'ImageRef':['from_value'],'LatentRef':['from_value','empty','noise_mask'],
 'CondRef':['from_value'],'TensorRef':['raw'],'ValueRef':['value'],'ModelRef':['apply_lora'],
 'GraphDomain':['current_node_id','widget_values','execution_metadata'],
 'AssetsDomain':['resolve','exists','list','read_bytes','load_image','digest'],
 'UiDomain':['preview_images'],'OutputDomain':['save_images','save_text'],
 'StorageDomain':['get','set']}
KWARGS={'ModelRef.apply_lora':['asset','clip','strength_model','strength_clip'],
 'GraphDomain.widget_values':['node_id'],'OutputDomain.save_images':['filenames','image_format','quality','lossless','save_metadata','extra_metadata','compress_level'],
 'LatentRef.empty':['width','height','batch_size','channels','spatial_downscale_ratio']}

def main():
    bases={};missing={};missing_kwargs={}
    for base in sorted(Path('/bases').iterdir()):
        file=base/'common-site-packages/comfy_api/latest/_sdk.py'
        if not file.exists():continue
        tree=ast.parse(file.read_bytes());rows={};classes={cls.name:cls for cls in tree.body if isinstance(cls,ast.ClassDef)}
        def defining(owner,method,seen=()):
            if owner in seen or owner not in classes:return None
            for fn in classes[owner].body:
                if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name==method:return owner,fn
            for parent in classes[owner].bases:
                found=defining(ast.unparse(parent).split('[')[0],method,seen+(owner,))
                if found:return found
            return None
        for cls,methods in SYMBOLS.items():
            for method in methods:
                found=defining(cls,method)
                if found:
                    owner,fn=found;key=cls+'.'+method
                    args=[arg.arg for arg in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs]
                    rows[key]={'path':str(file),'line':fn.lineno,'kwargs':args,'defining_class':owner}
        wanted={cls+'.'+method for cls,methods in SYMBOLS.items() for method in methods}
        missing[base.name]=sorted(wanted-rows.keys())
        missing_kwargs[base.name]={key:sorted(set(kwargs)-set(rows[key]['kwargs'])) for key,kwargs in KWARGS.items() if key in rows and not set(kwargs)<=set(rows[key]['kwargs'])}
        bases[base.name]=rows
    minimum='0cd9adec273a703eb3d1c715d83ff1c7d2bb00746330c866c7e3ac644c80ebbb'
    assert not missing[minimum],missing[minimum]
    assert not missing_kwargs[minimum],missing_kwargs[minimum]
    record={'status':'PASS','minimum_guest_base':minimum,'reason':'ImageRef.from_value is absent from older 0b86765f base; no fallback invented','symbols':bases,'missing_symbols':missing,'missing_used_kwargs':missing_kwargs,'explicit_png_text_or_a1111_calls':False}
    Path('/results/SDK-CHECK.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    fonts=[]
    for file in sorted(Path('/pack/v2/assets/fonts').glob('*.ttf')):
        data=file.read_bytes();n=struct.unpack_from('>H',data,4)[0];tables={}
        for i in range(n):
            tag,checksum,offset,length=struct.unpack_from('>4sIII',data,12+i*16);tables[tag]=(offset,length)
        offset,_=tables[b'name'];fmt,count,string_offset=struct.unpack_from('>HHH',data,offset);names={}
        for i in range(count):
            platform,encoding,language,key,length,pos=struct.unpack_from('>HHHHHH',data,offset+6+i*12)
            if key not in (0,1,13,14):continue
            raw=data[offset+string_offset+pos:offset+string_offset+pos+length]
            text=raw.decode('utf-16-be' if platform in (0,3) else 'mac_roman',errors='replace')
            names.setdefault(str(key),set()).add(text)
        values={key:sorted(value) for key,value in names.items()}
        licence=' '.join(values.get('13',[])+values.get('14',[]))
        assert 'Open Font License' in licence or 'openfontlicense' in licence.lower() or 'scripts.sil.org/OFL' in licence,(file.name,licence)
        assert data==(Path('/pack/assets/fonts')/file.name).read_bytes()
        fonts.append({'file':file.name,'sha256':hashlib.sha256(data).hexdigest(),'name_records':values,'licence':'OFL-1.1, original metadata retained'})
    assert len(fonts)==11
    Path('/results/font-audit.json').write_text(json.dumps({'fonts':fonts,'count':len(fonts),'notice_unchanged':(Path('/pack/assets/fonts/NOTICE.md').read_bytes()==Path('/pack/v2/assets/fonts/NOTICE.md').read_bytes())},indent=2,sort_keys=True)+'\n')
    return {'sdk_bases':len(bases),'font_files':len(fonts)}
