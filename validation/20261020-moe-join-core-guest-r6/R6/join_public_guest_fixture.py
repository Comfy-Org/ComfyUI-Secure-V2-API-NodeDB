"""SOURCE ONLY: reusable Core-finalized Join fixture, not a released job runner.

Importing this module loads only the standard library. No CLI or automatic
execution is provided. A separately reviewed finite supervisor must own the
controller and nested Guest process before calling exercise().
"""
import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

IDS = ('jupo.JoinPrompt.JoinStrings', 'jupo.JoinPrompt.JoinPrompt')
PYTHON = '/Users/ben/popbot/workspaces/comfyui-frontend/comfyui-frontend-1/temp/in_progress/sdk-main-rebase-20261019/core-test-venv/bin/python'
PYTHON_SHA = 'e81eb555fbfb8c6bd4ea528c60d4b3a8f9a94e53c31b0470f4f1524b4b9548c0'
VENV_CFG_SHA = 'a417db32b51d24f1817dd9d4881d8830cc1c468c5baf4e090329d4ac5a96e20b'
CORE_SHA = 'fbe39401517a8bdd15991f53efa8d2d3d03794dbc7bf77dbd0732ee59da5d20e'
FIXTURE_SHA = '17e3ccf9671c3b9de5af242196e7ff7f44850626e762be2a351307e760a362e3'
PTH = {'_pynvml_redirector.pth':'32b2e4126b0e897cf2c75e3d5077233c3a5733bba81ce0a9899bae4e857ca664',
       'distutils-precedence.pth':'2638ce9e2500e572a5e0de7faed6661eb569d1b696fcba07b0dd223da5f5d224'}

def require(value, message):
    if not value:
        raise AssertionError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inventory(root):
    rows = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Unexpected source symlink')
        if path.is_file():
            require(path.stat().st_size <= 16*1024**2, 'Source file too large')
            rows[path.relative_to(root).as_posix()] = sha(path)
    return rows

def mount(root, name):
    require(name not in sys.modules, 'Original module name already in use')
    spec = importlib.util.spec_from_file_location(name, root/'__init__.py', submodule_search_locations=[str(root)])
    require(spec is not None and spec.loader is not None, 'Original entrypoint unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def compare(actual, expected):
    require(actual == expected, 'Core-finalized original and Guest outcomes differ')

async def exercise(*, actual_profile, backend_inventory, source_binding, fixtures_path,
                   snapshot, owned_root, output_path, journal, observer_binding):
    """Run only inside a separately reviewed supervisor after an explicit grant.

    journal is a synchronous host evidence sink. It records resolved Guest
    ownership after start, not atomically at creation. An independent startup
    ownership observer/cleanup supervisor is still required outside this helper.
    This helper alone cannot establish timeout cleanup or managed admission.
    """
    root = Path(owned_root).resolve(strict=True)
    snapshot = Path(snapshot).resolve(strict=True)
    output_path = Path(output_path)
    require(output_path.is_absolute() and output_path.parent.resolve() == root, 'Output outside owned root')
    require(snapshot.is_relative_to(root) and len(list(snapshot.iterdir())) == 1, 'Owned one-pack snapshot required')
    pack = next(snapshot.iterdir())
    candidate = pack/'v2'
    require(sys.platform == 'darwin' and sys.version_info[:3] == (3,13,14), 'Selected Darwin Python required')
    require(sys.flags.isolated and not sys.flags.no_site and sys.dont_write_bytecode, 'Use selected venv -I -B normal startup')
    require(str(Path(sys.executable)) == PYTHON and sha(Path(sys.executable).resolve()) == PYTHON_SHA, 'Interpreter binding differs')
    require(Path(sys.prefix).resolve() == Path(PYTHON).parent.parent.resolve(), 'Normal-site prefix is not selected venv')
    require(sha(Path(sys.prefix)/'pyvenv.cfg') == VENV_CFG_SHA, 'Venv marker changed')
    site, core = Path(actual_profile['common_site_packages']), Path(actual_profile['core_source'])
    backend = Path(backend_inventory['backend_source_root'])
    require(actual_profile['python'] == PYTHON and actual_profile['python_sha256'] == PYTHON_SHA, 'Selected profile changed')
    require({p.name for p in site.glob('*.pth')} == set(PTH), 'Applicable startup .pth set changed')
    for name, digest in PTH.items():
        require(sha(site/name) == digest, 'Startup .pth bytes changed')
    require(len(actual_profile['sdk_files']) == 141 and len(actual_profile['core_files']) == 1384, 'Selected map count differs')
    require(backend_inventory['overlay_head'] == '59bd3e1acba6520bb32717ad03833f6ab2967ecc', 'Selected backend differs')
    inputs = []
    for selected_root, pins in ((site,actual_profile['sdk_files']), (core,actual_profile['core_files'])):
        for name,digest in pins.items():
            path=selected_root/name
            require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(selected_root.resolve()), 'Unsafe selected file')
            require(sha(path)==digest, 'Selected SDK/Core file changed: '+name)
            inputs.append((path,digest))
    require(len(backend_inventory['files']) == 83, 'Backend source map count differs')
    backend_names=set()
    for name,row in backend_inventory['files'].items():
        path=backend/name.removeprefix('backend/')
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(backend.resolve()), 'Unsafe backend source')
        require(sha(path)==row['sha256'], 'Selected backend bytes changed: '+name)
        inputs.append((path,row['sha256']))
        backend_names.add(name.removeprefix('backend/'))
    for path in (backend/'comfy_secure_nodes').rglob('*'):
        if '__pycache__' in path.parts or path.is_dir():
            continue
        if path.suffix in ('.py','.so','.dylib'):
            require(path.relative_to(backend).as_posix() in backend_names, 'Extra unpinned importable backend file')
    require(sha(core/'execution.py') == CORE_SHA and sha(fixtures_path) == FIXTURE_SHA, 'Core/fixtures differ')
    before=inventory(pack)
    require({n:d for n,d in before.items() if not n.startswith('v2/')} == source_binding['original_files'], 'Pristine original43 differs')
    require(inventory(candidate) == source_binding['candidate_files'], 'Current published candidate14 differs')
    require(len(source_binding['original_files']) == 43 and len(source_binding['candidate_files']) == 14, 'Source count differs')
    require(not {'execution','comfy.cli_args','server'}.intersection(sys.modules), 'Fixture needs fresh trusted controller')
    sys.path[:0]=[str(backend),str(site),str(core)]
    owned={}
    for name in ('base','user','models','frontend','input','output','temporary','work'):
        owned[name]=root/name
        owned[name].mkdir(exist_ok=False)
    sys.argv=['join-core-guest-fixture','--cpu','--offline','--disable-assets','--disable-all-custom-nodes',
              '--base-directory',str(owned['base']),'--user-directory',str(owned['user']),
              '--models-directory',str(owned['models']),'--front-end-root',str(owned['frontend']),
              '--database-url','sqlite:///:memory:']
    import comfy.options
    comfy.options.enable_args_parsing()
    import comfy.cli_args
    import folder_paths
    folder_paths.set_user_directory(str(owned['user']))
    folder_paths.set_input_directory(str(owned['input']))
    folder_paths.set_output_directory(str(owned['output']))
    folder_paths.set_temp_directory(str(owned['temporary']))
    from comfy_api.latest import io, sdk, ComfyExtension
    from comfy_secure_nodes import packdb
    from comfy_secure_nodes.transport.host import GuestSession
    from comfy_secure_nodes.transport.wire import WireError
    import execution
    import server
    from app.assets.manager import default_asset_manager, NoAssets
    require(Path(io.__file__).resolve().is_relative_to(site.resolve()), 'SDK origin differs')
    require(Path(packdb.__file__).resolve().is_relative_to(backend.resolve()), 'Backend origin differs')
    require(Path(execution.__file__).resolve() == (core/'execution.py').resolve(), 'Executor origin differs')
    require(comfy.cli_args.args.cpu and comfy.cli_args.args.offline and comfy.cli_args.args.disable_assets, 'Headless CPU/offline mode differs')
    assets=default_asset_manager()
    require(type(assets) is NoAssets and not assets.enabled, 'Genuine disabled asset manager required')
    instance=None
    prior_instance=getattr(server.PromptServer,'instance',None)
    prior_backend=sdk.providers.execution_backend
    session=None
    creation_observer=None
    report=dict(status='SOURCE_FIXTURE_FAILED_IF_INVOKED', scope='Ordinary development Guest plus selected Core finalization only; not managed image, frontend, service or whole-pack acceptance.',
                comparisons=[], dispatches=[], wrong_controls=[], local_call_count=0,
                startup_ownership='Journal records resolved start; independent creation/timeout supervision required outside helper.')
    guest_pid=None
    sockdir=None
    try:
        instance=server.PromptServer(asyncio.get_running_loop(),assets)
        require(instance.client_session is None and instance.asset_manager is assets, 'Unexpected server setup')
        routes=Counter((r.method,r.path) for r in instance.routes)
        original=mount(pack,'_moe_join_full_original_core')
        extension=await original.comfy_entrypoint()
        require(isinstance(extension,ComfyExtension), 'Original extension is not genuine')
        native={c.GET_SCHEMA().node_id:c for c in await extension.get_node_list()}
        require(set(native)==set(IDS) and Counter((r.method,r.path) for r in instance.routes)==routes, 'Original census/routes differ')
        require(not sdk.providers.engaged, 'Reference must run before isolated provider registration')
        fixtures=json.loads(Path(fixtures_path).read_bytes())
        cases=[dict(name=f['name'],node=f['node_id'],inputs=f['authored_raw_flat_inputs'],fixture=f) for f in fixtures['fixtures']]
        cases.append(dict(name='actual-core-out-of-order-autogrow',node=IDS[0],fixture=None,
                          inputs=dict([('texts.text_2','second'),('texts.text_0','zero'),('texts.text_1','first'),('delimiter','|'),('cleanup',False)])))

        async def run_core(cls, case, number, remote=False):
            raw=dict(case['inputs'])
            cls.VALIDATE_CLASS()
            finalized,missing,v3=execution.get_input_data(raw,cls,str(number),None)
            require(not missing, 'Actual Core input finalization has missing keys')
            try:
                values=await execution._async_map_node_over_list(prompt_id='moe-join-boundary',unique_id=str(number),
                    obj=cls,input_data_all=finalized,func=cls.FUNCTION,v3_data=v3)
                require(len(values)==1 and isinstance(values[0],io.NodeOutput), 'Actual Core result shape differs')
                result=values[0].result
                require(type(result) is tuple and len(result)==1 and type(result[0]) is str, 'Expected one actual STRING output')
                return dict(kind='value',text=result[0])
            except WireError as error:
                require(remote and error.remote_phase=='execute', 'Import/startup/wire failure is not a native execution error')
                require(any(Path(str(f.get('file',''))).is_relative_to(candidate) for f in error.remote_frames), 'Missing genuine candidate execution frame')
                return dict(kind='error',type=error.remote_type,message=error.remote_message)
            except AttributeError as error:
                require(not remote, 'Local candidate error cannot substitute for Guest execution')
                return dict(kind='error',type=type(error).__name__,message=str(error))

        expected=[]
        for i,case in enumerate(cases):
            outcome=await run_core(native[case['node']],case,i)
            fixture=case['fixture']
            if fixture is not None:
                bound=(dict(kind='error',**fixture['expected_native_error']) if fixture['expected_native_error'] else dict(kind='value',text=fixture['expected_text']))
                compare(outcome,bound)
            expected.append(outcome)
        # Genuine metadata proxies from the current normal manifest; no handwritten manifest builder.
        loaded=packdb.load_pack(snapshot,mount_name='custom_nodes.moe_join_public_fixture')
        require(set(loaded.node_mappings)==set(IDS) and not loaded.routes and not loaded.frontend_permissions, 'Current pack metadata differs')
        require(os.environ.get('COMFY_SECURE_SANDBOX_MODE')=='required' and os.environ.get('COMFY_SECURE_SANDBOX_BACKEND')=='seatbelt', 'Explicit genuine confinement required')
        # Narrow existing constructor read root contains this candidate only.
        session=GuestSession('moe-join-public',runtime=None,tenant='moe-join-owned-fixture',
                             work_root=owned['work'],guest_runtime_root=candidate)
        journal(dict(event='guest_start_requested',source_root=str(candidate),runtime_mode='development/host'))
        observer_path=Path(__file__).with_name('guest_startup_observer.py')
        observer_spec=importlib.util.spec_from_file_location('_exact_amy_guest_creation_observer',observer_path)
        require(observer_spec is not None and observer_spec.loader is not None,'Pinned observer unavailable')
        observer_module=importlib.util.module_from_spec(observer_spec)
        observer_spec.loader.exec_module(observer_module)
        creation_observer=observer_module.GuestStartupObserver(root,observer_binding['subprocess_source'])
        creation_observer.begin_creation()
        try:
            await session.start()
        finally:
            creation_observer.end_creation()
            report['creation_observation']=creation_observer.snapshot()
        report['verified_actual_startup']=creation_observer.verify_session(session)
        forbidden={Path('/'),Path('/Users/ben'),Path('/Users/ben/popbot/workspaces'),Path('/private/tmp')}
        require(not any(Path(p).resolve() in forbidden for p in report['verified_actual_startup']['ordered_read_roots_source_bound']),'Broad ancestor read root forbidden')
        require(session.sandbox_kind=='seatbelt', 'No confinement downgrade permitted')
        require(session._proc is not None, 'Guest process unavailable')
        guest_pid=session._proc.pid
        sockdir=Path(session._sockdir)
        journal(dict(event='guest_start_resolved',pid=guest_pid,pgid=session._pgid,socket_directory=str(sockdir)))
        require(session._pgid==guest_pid and guest_pid!=os.getpid(), 'Guest is not a distinct owned process group')
        policy=Path(session._guest_tmp)/'guest.sb'
        report['startup']=dict(pid=guest_pid,pgid=session._pgid,sandbox=session.sandbox_kind,
            python=str(session.python_executable),venv=str(session.resolved_runtime.venv_root),
            read_roots=[str(p) for p in session.resolved_runtime.read_roots],
            policy=policy.read_text(),source_root=str(candidate),managed_runtime=False)
        class ForwardToActualGuest:
            async def dispatch(self,plan,local_call,runtime=None):
                require(runtime is not None and type(plan) is sdk.ExecutionPlan, 'Actual Core-created plan/runtime required')
                require(plan.input_mode=='values' and plan.method=='execute' and not plan.permissions, 'Plan/capability scope differs')
                module=sys.modules.get(plan.node_module)
                require(module is not None and Path(module.__file__).resolve().is_relative_to(candidate), 'Plan source outside candidate')
                report['dispatches'].append(dict(node_id=plan.node_id,node_class=plan.node_type,
                    module=plan.node_module,inputs=json.loads(json.dumps(plan.inputs)),capabilities=[]))
                # local_call is deliberately never invoked: only the genuine Guest executes candidate code.
                return await session.execute(plan,runtime,capabilities=(),tenant='moe-join-owned-fixture')
        sdk.providers.register_execution_backend(ForwardToActualGuest())
        require(sdk.providers.engaged, 'Core SDK seam did not engage')
        for i,(case,reference) in enumerate(zip(cases,expected,strict=True)):
            count=len(report['dispatches'])
            actual=await run_core(loaded.node_mappings[case['node']],case,i,remote=True)
            require(len(report['dispatches'])==count+1, 'Candidate did not cross the real dispatch seam once')
            compare(actual,reference)
            report['comparisons'].append(dict(name=case['name'],node=case['node'],original=reference,guest=actual))
        require(len(report['comparisons'])==10 and len(report['dispatches'])==10, 'Boundary coverage incomplete')
        require(session.last_guest_pid==guest_pid, 'Observed Guest execution PID differs')
        observed=next(r['guest'] for r in report['comparisons'] if r['guest']['kind']=='value' and r['guest']['text'])
        wrong=dict(kind='value',text=observed['text']+'\0wrong-output')
        try:
            compare(observed,wrong)
        except AssertionError:
            report['wrong_controls'].append(dict(name='corrupted-actual-STRING',detected=True))
        else:
            raise AssertionError('Wrong STRING escaped final comparator')
        report['status']='PASS_CORE_FINALIZATION_AND_ORDINARY_CONFINED_GUEST_ONLY'
        return report
    except BaseException as error:
        report.update(status='FAILED_BOUNDARY_FIXTURE',error_type=type(error).__name__,error=str(error)[:4096])
        raise
    finally:
        cleanup_errors=[]
        async def cleanup_step(name,action):
            try:
                await action
            except BaseException as error:
                cleanup_errors.append(name+': '+repr(error))
        try:
            sdk.providers.register_execution_backend(prior_backend)
        except BaseException as error:
            cleanup_errors.append('restore provider: '+repr(error))
        if session is not None:
            await cleanup_step('Guest kill',asyncio.wait_for(session.kill(),3))
        if guest_pid is not None:
            try:
                try:
                    os.killpg(guest_pid,0)
                except ProcessLookupError:
                    report['normal_path_guest_group_absent']=True
                else:
                    raise AssertionError('Guest group remains after normal-path cleanup')
                require(sockdir is not None and not sockdir.exists(), 'Guest socket directory remains')
            except BaseException as error:
                cleanup_errors.append('Guest retirement check: '+repr(error))
        if instance is not None:
            if instance.client_session is not None:
                await cleanup_step('client session close',asyncio.wait_for(instance.client_session.close(),1))
            await cleanup_step('server app cleanup',asyncio.wait_for(instance.app.cleanup(),1))
        try:
            # Selected Core NoAssets.shutdown is synchronous and returns None.
            assets.shutdown()
        except BaseException as error:
            cleanup_errors.append('asset manager shutdown: '+repr(error))
        server.PromptServer.instance=prior_instance
        try:
            require(inventory(pack)==before, 'Source changed during fixture')
            for path,digest in inputs:
                require(sha(path)==digest, 'Selected input changed during fixture')
            for name,digest in PTH.items():
                require(sha(site/name)==digest, 'Startup source changed during fixture')
            require(sha(Path(sys.prefix)/'pyvenv.cfg')==VENV_CFG_SHA, 'Venv marker changed during fixture')
        except BaseException as error:
            cleanup_errors.append('post-input map: '+repr(error))
        if creation_observer is not None:
            try:
                report['creation_observation']=creation_observer.snapshot()
                if creation_observer.errors:
                    cleanup_errors.append('Actual Guest creation observation has errors')
                creation_observer.close()
            except BaseException as error:
                cleanup_errors.append('creation observer close: '+repr(error))
        report['cleanup_errors']=cleanup_errors
        if cleanup_errors:
            report['status']='FAILED_CLEANUP_OR_INPUT_PRESERVATION'
        output_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        require(not cleanup_errors, 'Fixture cleanup/input preservation failed')
