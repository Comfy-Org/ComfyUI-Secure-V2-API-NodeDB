"""Owned artifact generation only. Never writes pristine/shared/catalogue files."""
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tarfile
import tempfile

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1]
PRISTINE=V2.parent
SNAPSHOT=PRISTINE.parent
TREE=SNAPSHOT.parents[2]
OUT=Path('/Users/ben/popbot/raw-chats/outputs')
CORE=Path(os.environ['COMFY_CORE_ROOT'])
BACK=Path('/Users/ben/comfy/ComfyUI_secure_nodes/backend')
FE=BACK.parent/'frontend/src'
sys.path[:0]=[str(CORE),str(BACK),str(V2/'tests')]
from comfy_secure_nodes import packpatch
from test_amy_readable_conversion import manifest

def ref(path):
    path=Path(path);data=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),
        'bytes':len(data),'mode':oct(path.stat().st_mode&0o777)}

def rows(root,pristine=False):
    return [dict(ref(p),relative=p.relative_to(root).as_posix()) for p in sorted(root.rglob('*'))
        if p.is_file() and (not pristine or 'v2' not in p.relative_to(root).parts)]

def write_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def runtime_refs():
    return [ref(p) for p in [CORE/'comfy_api/latest/_sdk.py',CORE/'execution.py',CORE/'comfy/samplers.py',
        BACK/'comfy_secure_nodes/transport/host.py',BACK/'comfy_secure_nodes/guest/__init__.py',
        BACK/'comfy_secure_nodes/webassets.py',BACK/'comfy_secure_nodes/packmanifest.py',
        BACK/'comfy_secure_nodes/packpatch.py',FE/'host-entry.mjs',FE/'guest.mjs',FE/'ui-renderer.mjs']]

def prepare():
    import cv2
    import av
    capture=json.loads((OUT/'amy-oct8-readable-metadata-capture.json').read_bytes())
    roots=[OUT/'many-oct8-text-input-annotation/handoff.json',
        OUT/'many-oct8-style-model-contract/handoff.json',
        OUT/'many-oct8-owned-element-access/handoff.json',
        OUT/'many-oct8-immediate-file-catalogue/handoff.json']
    provenance={'format':'amy-readable-source-provenance-v1','upstream':capture['upstream'],
        'commit':capture['commit'],'version':'2.5.4','capture':ref(OUT/'amy-oct8-readable-metadata-capture.json'),
        'pristine':capture['pristine'],'license':'MIT, copyright 2025 ShammiG; complete source LICENSE retained',
        'published_contracts':[ref(p) for p in roots],
        'selected_runtime':runtime_refs(),'python':sys.version,'platform':platform.platform(),
        'dependencies':{name:importlib.metadata.version(name) for name in
            ['torch','numpy','Pillow','opencv-python','av']},
        'native_selected_payloads':[ref(p) for module in (cv2,av) for p in sorted(
            Path(module.__file__).parent.rglob('*')) if p.is_file() and (
                p.suffix=='.so' or p.suffix=='.dylib' and p.name.startswith('libav'))],
        'opencv_build':cv2.getBuildInformation(),
        'declarations':[dict(ref(V2/'comfy-api.pyi'),origin=ref(OUT/'many-oct8-style-model-contract/comfy-api.pyi')),
            dict(ref(V2/'comfy-api.d.ts'),origin=ref(OUT/'many-oct8-owned-element-access/comfy-api.d.ts'))],
        'runtime_disposition':'Python3.13 inherited unsealed Mac development; no profile_sha256, install or deployment claim',
        'archive_provenance':{'registry_archive_sha256':'253fc479b7ecb6acc64d75a5d9d532646a7c3c77ec7b542e8857ed2b081e8e2c',
            'codeload':ref(OUT/'amy-oct8-readable-metadata-e51819a-codeload.tar.gz')},
        'immutable_predecessors':[ref(OUT/name) for name in ['amy-oct8-readable-metadata-whole-screen.json',
            'amy-oct8-readable-metadata-png-fixture.json','amy-oct8-readable-video-transport-handoff.json',
            'amy-oct8-readable-viewer-safety-proposal.json']],
        'sampling_schema':ref(V2/'sampling_names.json')}
    write_json(V2/'source-provenance.json',provenance)
    write_json(V2/'secure-nodes.json',manifest())

def pair():
    m,diff=packpatch.generate(SNAPSHOT)
    destination=TREE/'patches'/m['pack']/m['key'];destination.mkdir(parents=True,exist_ok=True)
    stem=m['pack']+'-'+m['key']
    mp=destination/(stem+'.json');dp=destination/(stem+'.diff')
    mp.write_text(json.dumps(m,indent=1)+'\n');dp.write_text(diff)
    artifact=packpatch.bundle(m,diff)
    zp=OUT/'amy-oct8-readable-metadata-pair.zip';zp.write_bytes(artifact)
    packpatch.validate_bundle(SNAPSHOT,artifact)
    results=[]
    for kind in ['plain','zip']:
        with tempfile.TemporaryDirectory(prefix='amy-readable-roundtrip-') as temporary:
            snapshot=Path(temporary)/m['pack']/m['key']
            base=snapshot/PRISTINE.name
            shutil.copytree(PRISTINE,base,ignore=lambda directory,names:['v2'] if Path(directory)==PRISTINE else [])
            if kind=='plain':packpatch.apply(snapshot,m,diff)
            else:packpatch.apply_bundle(snapshot,artifact)
            packpatch.validate_tree(base/'v2',V2)
            packpatch.validate_bundle(snapshot,artifact)
            results.append({'kind':kind,'all_bytes_modes':'exact'})
    receipt={'format':'amy-readable-pair-receipt-v1','pair':[ref(mp),ref(dp)],'zip':ref(zp),
        'counts':m['counts'],'roundtrips':results,'pristine':rows(PRISTINE,True),'v2':rows(V2),
        'selected_runtime':runtime_refs()}
    write_json(OUT/'amy-oct8-readable-metadata-pair-receipt.json',receipt)
    print(json.dumps({'pair':str(destination),'v2_files':len(receipt['v2']),'exact_roundtrips':2}))

def freeze(logs):
    receipt=json.loads((OUT/'amy-oct8-readable-metadata-pair-receipt.json').read_bytes())
    assert receipt['v2']==rows(V2) and receipt['pristine']==rows(PRISTINE,True)
    assert receipt['selected_runtime']==runtime_refs(),'runtime changed; selected repeat required'
    archive=OUT/'amy-oct8-readable-metadata-portable.tar.gz'
    with tarfile.open(archive,'w:gz',format=tarfile.PAX_FORMAT) as target:
        for row in receipt['pristine']+receipt['v2']:
            path=Path(row['path']);name=('pristine/' if 'v2' not in path.relative_to(PRISTINE).parts else 'v2/')+row['relative']
            member=tarfile.TarInfo(name);member.size=row['bytes'];member.mode=int(row['mode'],8);member.mtime=0
            target.addfile(member,io.BytesIO(path.read_bytes()))
    with tarfile.open(archive) as source:
        members=source.getmembers();assert len(members)==len(receipt['pristine'])+len(receipt['v2'])
        assert not any('._' in m.name or '__MACOSX' in m.name for m in members)
        for m in members:
            key=m.name.split('/',1)[1];group=receipt['pristine'] if m.name.startswith('pristine/') else receipt['v2']
            row=next(r for r in group if r['relative']==key)
            assert hashlib.sha256(source.extractfile(m).read()).hexdigest()==row['sha256'] and m.mode==int(row['mode'],8)
    handoff={'format':'amy-readable-seven-whole-handoff-v1','scope':'bounded Mac development whole7+5; root review required',
        'tree':str(TREE),'pristine_path':str(PRISTINE),'v2_path':str(V2),'commit':'e51819a7944c526dc8a545c7ec82b73e450b57c9',
        'upstream':'https://github.com/ShammiG/ComfyUI-Simple_Readable_Metadata-SG','version':'2.5.4',
        'backend':{'proposed_supported':7,'rejected':0,'pending_local_behavior':0},
        'frontend':{'proposed_supported':5,'safe_helpers':3,'rejected':0,'pending_local_behavior':0},
        'count_change':0,'deployment_change':0,'writes':'assigned owned V2/tests/pair and amy-prefixed evidence only; pristine/shared/catalogue untouched',
        'report':ref(V2/'SECURE_CONVERSION.md'),'manifest':ref(V2/'secure-nodes.json'),
        'provenance':ref(V2/'source-provenance.json'),'pair_receipt':ref(OUT/'amy-oct8-readable-metadata-pair-receipt.json'),
        'pair':receipt['pair'],'zip':receipt['zip'],'portable_archive':ref(archive),
        'pristine':receipt['pristine'],'v2':receipt['v2'],'selected_runtime':runtime_refs(),
        'logs':[ref(OUT/name) for name in logs],
        'remaining_qualifications':['Inherited unsealed Mac runtime only, no sealed/Linux/Cloud profile',
            'Native parser peak physical memory and codec universe unproved',
            'Same-size concurrent input rewrite not atomic; output first-free races refuse',
            'Workflow-owned state and execution annotation, not authenticated Cloud durable library',
            'Source positive_candidates bug/native fallback retained; unsafe eval and zero-width hang deliberately normalized',
            'No trained model/GPU/native alias or deployment claim']}
    destination=OUT/'amy-oct8-readable-metadata-handoff.json'
    with destination.open('x',encoding='utf-8') as stream:stream.write(json.dumps(handoff,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(ref(destination)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','pair','freeze']);parser.add_argument('logs',nargs='*')
    args=parser.parse_args()
    if args.mode=='prepare':prepare()
    elif args.mode=='pair':pair()
    else:freeze(args.logs)
