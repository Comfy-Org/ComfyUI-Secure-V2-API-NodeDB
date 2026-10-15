"""Trusted test orchestration; pack runtime never imports this script."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

V2=Path(__file__).resolve().parents[1]
OUT=Path('/Users/ben/popbot/raw-chats/outputs')
CORE='/Users/ben/comfy/ComfyUI-secure-nodes'
BACK='/Users/ben/comfy/ComfyUI_secure_nodes/backend'
PY='/Users/ben/comfy/ComfyUI/.venv/bin/python'
tag=sys.argv[1]
assert tag in ('first','second','selected-first','selected-second')
prefix='amy-oct8-readable-whole-final-'+tag
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',COMFY_CORE_ROOT=CORE,
    PYTHONPATH=CORE+':'+BACK+':'+BACK+'/tests',AMY_READABLE_V2=str(V2),
    COMFY_SECURE_API_STUB=str(V2/'comfy-api.pyi'),AMY_PROFILE_RUN='whole-final-'+tag)
sys.path[:0]=[CORE,BACK,str(V2/'tests')]
from amy_finalize_readable_artifacts import rows,runtime_refs,ref
before={'pristine':rows(V2.parent,True),'v2':rows(V2),'runtime':runtime_refs()}
commands=[('python',[PY,'-B','-m','pytest','-p','no:cacheprovider','-q','-s',str(V2/'tests')]),
    ('stub',[PY,'-B','-m','pytest','-p','no:cacheprovider','-q',BACK+'/tests/test_api_stubs.py']),
    ('frontend',['node',str(V2/'tests/amy_readable_frontend_bridge.mjs')]),
    ('viewer-profile',['node',str(V2/'tests/amy_readable_viewer_profile.mjs')])]
results=[]
for kind,command in commands:
    log=OUT/(prefix+'-'+kind+'.log')
    started=time.monotonic()
    with log.open('x',encoding='utf-8') as stream:
        result=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
    results.append({'kind':kind,'command':command,'exit_code':result.returncode,
        'seconds':time.monotonic()-started,'log':ref(log)})
    print(kind,result.returncode,flush=True)
    if result.returncode:raise SystemExit('final gate failed: '+str(log))
    assert before=={'pristine':rows(V2.parent,True),'v2':rows(V2),'runtime':runtime_refs()},'selected bytes changed'
receipt={'format':'amy-readable-unchanged-final-gate-v1','tag':tag,'environment':{
    key:env[key] for key in ('COMFY_CORE_ROOT','PYTHONPATH','PYTHONDONTWRITEBYTECODE','COMFY_SECURE_API_STUB','AMY_READABLE_V2','AMY_PROFILE_RUN')},
    'before':before,'after':before,'results':results,'unchanged_owned_and_runtime':True}
path=OUT/(prefix+'.json')
with path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(ref(path)),flush=True)
