"""Serial normal TEST admission; credentials stay private, no direct runtime launch."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent
BASE='http://127.0.0.1:5175'
STATE=HERE/'STATE.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value,indent=2,ensure_ascii=True)+'\n').encode()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['stage','inspect','queue-positive','poll-positive','verify-positive','queue-negative','poll-negative','verify-negative'])
    args=parser.parse_args()
    prepared=json.loads((HERE/'PREPARED.json').read_bytes())
    # Same existing authenticated local service as Root's terminal scalar TESTs.
    # Read the current key into memory only; never print or persist it.
    key=subprocess.check_output(['docker','exec','jerry-secure-cloud','cat','/runtime/secrets/api-key.txt'],timeout=10).decode().strip()
    assert key
    state=json.loads(STATE.read_bytes()) if STATE.exists() else {'owner':'NED','authority':'m_11b442b00f',
        'pack':'github:slartibart23/comfyui-sentence-filter','prepared_sha256':digest((HERE/'PREPARED.json').read_bytes()),
        'positive':{},'negative':{},'whole_pack_qualified':False,'normal_registry_adopted':False,'published':False}
    assert state['prepared_sha256']==digest((HERE/'PREPARED.json').read_bytes())

    def save():
        state['observed_utc']=datetime.now(timezone.utc).isoformat()
        STATE.write_bytes(encoded(state))

    def api(method,path,body=None):
        request=urllib.request.Request(BASE+path,method=method,headers={'X-API-Key':key,'Content-Type':'application/json'},
            data=json.dumps(body,ensure_ascii=True).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                raw=response.read(2*1024**2+1)
                status=response.status
        except urllib.error.HTTPError as error:
            raw,status=error.read(32768),error.code
        assert len(raw)<=2*1024**2
        value=json.loads(raw)
        if status>=400:
            state['last_http_failure']={'phase':args.phase,'status':status,'response':value}
            save()
            raise RuntimeError('TEST service HTTP failure:'+str(status))
        return status,value

    def prefix():
        return '/api/customnodes/editor/sessions/'+state['session_id']

    def verify_source():
        source=Path(prepared['source'])
        assert digest(Path(prepared['Root_verified_artifact_receipt']).read_bytes())==prepared['Root_verified_artifact_receipt_sha256']
        actual={p.relative_to(source).as_posix():digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()}
        assert actual==prepared['production_source_sha256'], 'Canonical production files changed'

    def request_for(kind):
        raw=(HERE/(kind.upper()+'-REQUEST.json')).read_bytes()
        assert digest(raw)==prepared[kind+'_request_sha256']
        return json.loads(raw)

    if args.phase=='stage':
        verify_source()
        if 'session_id' not in state:
            assert not state.get('session_creation_attempted'), 'Creation outcome must be diagnosed before any retry'
            state['session_creation_attempted']=True
            save()
            code,session=api('POST','/api/customnodes/editor/sessions',{'mode':'create','name':'NED SentenceFilter TEST 20261019'})
            state.update(session_id=session['id'],session_status=session['status'],session_create_http=code)
            save()
        print(json.dumps({'phase':'stage','session_id':state['session_id'],'UI_cases':prepared['UI_cases'],'nodes':prepared['workflow_nodes']}))
    elif args.phase=='inspect':
        _,session=api('GET',prefix())
        (HERE/'SESSION-READBACK.json').write_bytes(encoded(session))
        _,files=api('GET',prefix()+'/files')
        (HERE/'SESSION-FILES-READBACK.json').write_bytes(encoded(files))
        print(json.dumps({'session_id':state['session_id'],'status':session['status'],'readbacks_saved':True}))
    elif args.phase.startswith('queue-'):
        kind=args.phase.removeprefix('queue-')
        record=state[kind]
        assert not record.get('queue_attempted'), 'Poll/diagnose existing admission; never automatically resubmit'
        if kind=='negative':
            assert state['positive'].get('verification',{}).get('status')=='PASS_GVISOR_PNG64_EXACT27_STRINGS'
        verify_source()
        _,session=api('GET',prefix())
        assert session['status']=='ready', 'Session not ready; no TEST admission attempted'
        body=request_for(kind)
        record.update(queue_attempted=True,request_sha256=prepared[kind+'_request_sha256'])
        save()
        code,test=api('POST',prefix()+'/tests',body)
        record.update(test_id=test['id'],test_create_http=code,test=test)
        save()
        print(json.dumps({'kind':kind,'test_id':test['id'],'status':test['status']}))
    elif args.phase.startswith('poll-'):
        kind=args.phase.removeprefix('poll-')
        record=state[kind]
        _,test=api('GET',prefix()+'/tests/'+record['test_id'])
        record['test']=test
        save()
        result=test.get('result') or {}
        print(json.dumps({'kind':kind,'test_id':test['id'],'status':test['status'],'phase':result.get('phase'),'error':result.get('error')}))
    elif args.phase=='verify-positive':
        record=state['positive']
        test=record['test']
        assert test['status']=='passed', 'Preserve and diagnose TEST failure; no retry'
        assert test['result']['sandbox']=='gvisor'
        artifacts=[artifact for output in test['result']['outputs'] for artifact in output['artifacts']]
        assert len(artifacts)==1
        artifact=artifacts[0]
        url=artifact['url']
        assert url.startswith(prefix()+'/tests/'+record['test_id']+'/artifacts/')
        request=urllib.request.Request(BASE+url,headers={'X-API-Key':key})
        with urllib.request.urlopen(request,timeout=10) as response:
            data=response.read(4*1024**2+1)
            assert response.headers.get_content_type()=='image/png'
        assert len(data)<=4*1024**2 and data[:8]==b'\x89PNG\r\n\x1a\n' and data[12:16]==b'IHDR'
        dimensions=list(struct.unpack('>II',data[16:24]))
        assert dimensions==[64,64]
        (HERE/'positive64.png').write_bytes(data)
        verify_source()
        record['verification']={'status':'PASS_GVISOR_PNG64_EXACT27_STRINGS','sandbox':'gvisor','PNG_dimensions':dimensions,
            'PNG_sha256':digest(data),'PNG_bytes':len(data),'UI_cases':prepared['UI_cases'],'workflow_nodes':prepared['workflow_nodes'],
            'fixed_original_strings_compared_by_TEST_only_typed_helper':True,'production_entry_and_executable_bytes_unchanged':True,
            'native_direct32_coverage_distinct':True,'whole_pack_or_registry_claim':False}
        save()
        print(json.dumps(record['verification']))
    elif args.phase=='verify-negative':
        record=state['negative']
        test=record['test']
        control=prepared['negative_control']
        assert test['status']=='failed' and test['result']['phase']=='execute'
        assert test['result']['sandbox']=='gvisor'
        error=test['result']['error']
        assert error['type']==control['expected_exception_type'] and error['message']==control['expected_exception_message']
        assert any(frame.get('file','').endswith('v2/tests/sentence_filter_oracle.py') and frame.get('function')=='execute' for frame in error['frames'])
        verify_source()
        record['verification']={'status':'PASS_KNOWN_WRONG_EXPECTED_STRING_REJECTED','sandbox':'gvisor','error_type':error['type'],
            'error_message':error['message'],'phase':'execute','TEST_only_oracle_frame_verified':True,'production_bytes_unchanged':True}
        state['service_check_summary']={'positive':'PASS_GVISOR_PNG64_EXACT27_STRINGS','negative':'PASS_KNOWN_WRONG_EXPECTED_STRING_REJECTED',
            'normal_registry_adoption':False,'publication':False,'whole_pack_certificate':False,'canonical_artifact_unchanged':True}
        save()
        print(json.dumps(record['verification']))


if __name__=='__main__':
    main()
