"""Trusted observation only: actual Popen intent/profile and assigned birth PID.

No SDK, Popen, asyncio, sandbox or provider functions are replaced. A narrow
sys.setprofile hook observes the pinned real stdlib constructor's return/unwind.
The pre-exec audit event alone does not prove creation. No observer can close
the uncatchable parent-kill interval between OS creation and durable recording.
"""
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _require(value,message):
    if not value:raise RuntimeError(message)
def _plain(value):return json.loads(json.dumps(value,default=str))

class GuestStartupObserver:
    def __init__(self,output,expected_subprocess_source):
        self.output=Path(output).resolve()
        _require(self.output.is_dir(),'Prepared owned output directory required')
        source=Path(subprocess.__file__).resolve()
        _require(source==Path(expected_subprocess_source['path']).resolve(),'Exact actual stdlib subprocess origin required')
        _require(_sha(source)==expected_subprocess_source['sha256'],'Actual subprocess source pin changed')
        self.constructor_code=subprocess.Popen.__init__.__code__
        _require(Path(self.constructor_code.co_filename).resolve()==source,'Real pinned constructor code required')
        self.source={'path':str(source),'sha256':_sha(source),'qualified_callable':'subprocess.Popen.__init__'}
        self.launches=[];self.births=[];self.errors=[];self.enabled=True;self.previous_profile=None;self.profiling=False
        self.journal_path=self.output/'GUEST_CREATION.jsonl'
        self.fd=os.open(self.journal_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_APPEND,0o600)
        self._write({'event':'observer-installed','source':self.source,'parent_pid':os.getpid()})
        sys.addaudithook(self._audit)

    def _write(self,row):
        row=dict(row,monotonic=time.monotonic(),observer_parent_pid=os.getpid())
        data=(json.dumps(row,default=str)+'\n').encode()
        written=os.write(self.fd,data)
        _require(written==len(data),'Incomplete durable observation write')
        os.fsync(self.fd)

    @staticmethod
    def _guest(argv):
        return isinstance(argv,(tuple,list)) and 'comfy_secure_nodes.guest' in argv

    def _audit(self,event,args):
        if not self.enabled or event!='subprocess.Popen' or not self._guest(args[1]):return
        row={'event':'Guest-launch-intent-not-yet-creation','argv':[str(x) for x in args[1]],
             'cwd':args[2],'environment':dict(args[3] or {})}
        try:
            argv=row['argv']
            _require(argv[0]=='<private-path:41a9a3021907ff35>' and '-f' in argv,'Actual required Seatbelt command must be observed')
            profile=Path(argv[argv.index('-f')+1])
            _require(profile.is_file() and not profile.is_symlink(),'Genuine regular generated Guest profile required')
            body=profile.read_bytes()
            saved=self.output/('GUEST_PROFILE_'+str(len(self.launches))+'.sb')
            saved.write_bytes(body)
            row.update(profile_path=str(profile),saved_profile=str(saved),profile_sha256=hashlib.sha256(body).hexdigest())
            self.launches.append(row);self._write(row)
        except Exception as error:
            self.errors.append({'phase':'before-exec-audit','error_type':type(error).__name__,'error':str(error)})

    def _profile(self,frame,event,arg):
        if not self.enabled or event!='return' or frame.f_code is not self.constructor_code:return
        process=frame.f_locals.get('self')
        argv=getattr(process,'args',None)
        if not self._guest(argv):return
        try:
            pid=getattr(process,'pid',None)
            row={'event':'Pinned-Popen-constructor-return-or-unwind','argv':[str(x) for x in argv],
                 'assigned_child_pid':pid,'start_new_session':frame.f_locals.get('start_new_session'),
                 'constructor_source':self.source,
                 'scope':'Return profile event also occurs during exception unwind; creation is not successful Guest startup.'}
            if type(pid) is int and pid>0:
                try:row['observed_pgid']=os.getpgid(pid)
                except ProcessLookupError:row['observed_pgid']=None;row['already_exited_before_group_lookup']=True
                row['source_session_group_candidate']=pid if row['start_new_session'] is True else None
            self.births.append(row);self._write(row)
        except Exception as error:
            self.errors.append({'phase':'constructor-return-observation','error_type':type(error).__name__,'error':str(error)})

    def begin_creation(self):
        _require(not self.profiling and sys.getprofile() is None,'Do not overwrite another profiler')
        _require(_sha(self.source['path'])==self.source['sha256'],'Stdlib constructor source changed')
        self.previous_profile=sys.getprofile();self.profiling=True;sys.setprofile(self._profile)

    def end_creation(self):
        if self.profiling:
            sys.setprofile(self.previous_profile);self.profiling=False

    def verify_session(self,session):
        from comfy_secure_nodes.transport import host,sandbox
        _require(not self.errors and len(self.launches)==len(self.births)==1,'Exactly one fully observed real Guest creation required')
        birth,launch=self.births[0],self.launches[0]
        _require(birth['assigned_child_pid']==session.pid and birth['start_new_session'] is True,'Actual session PID and source creation identity differ')
        _require(launch['argv']==birth['argv'],'Actual intent/assigned-PID argv mismatch')
        _require(session.sandbox_kind==sandbox.KIND_SEATBELT and sandbox.mode()==sandbox.MODE_REQUIRED,'Genuine required Guest Seatbelt only')
        resolved=session.resolved_runtime
        _require(resolved is not None,'Actual resolved runtime missing')
        roots=[str(session.guest_runtime_root),host._overlay_backend_root(),host._secure_sdk_root()]
        node_sdk=host._node_sdk_package_root();custom_nodes=os.path.join(os.path.dirname(node_sdk),'custom_nodes')
        if os.path.isdir(custom_nodes):roots.append(custom_nodes)
        read_roots=[*roots,node_sdk,resolved.spec.pack_root,*resolved.read_roots]
        env=launch['environment']
        expected=sandbox.seatbelt_profile(socket_path=env['COMFY_GUEST_SOCKET'],tmpdir=env['TMPDIR'],
                                         ro_paths=read_roots,allow_host_toolchain=True).encode()
        actual=Path(launch['saved_profile']).read_bytes()
        _require(actual==expected,'Observed actual Guest profile differs from exact supported Host source recipe')
        _require(Path(sys.prefix).resolve()==resolved.venv_root.resolve() and resolved.venv_root.resolve() in resolved.read_roots,'Actual venv root missing')
        return {'status':'ACTUAL_GUEST_STARTUP_AND_PROFILE_OBSERVED','pid':session.pid,'sandbox_kind':session.sandbox_kind,
                'resolved_runtime':_plain(dataclasses.asdict(resolved)),
                'ordered_read_roots_source_bound':[str(p) for p in read_roots],
                'actual_profile_matches_genuine_supported_source_recipe':True,'observations':self.snapshot()}

    def snapshot(self):
        return _plain({'stdlib_source':self.source,'intent_events':self.launches,'assigned_PID_events':self.births,
                       'errors':self.errors,'durable_journal':str(self.journal_path),
                       'remaining_gap':'Uncatchable parent kill between OS creation and observer fsync; polling is not proof for that gap. Constructor unwind is not successful Guest startup. Owner must independently retire/probe all recorded PIDs/group candidates.'})

    def close(self):
        self.end_creation();self.enabled=False
        _require(_sha(self.source['path'])==self.source['sha256'],'Stdlib source changed')
        os.close(self.fd)
