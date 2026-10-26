"""Own stdlib source-only focused closure preparation; supplied code unrun."""
import ast,hashlib,json,stat,zipfile
from pathlib import Path
R=Path(__file__).resolve().parent
BASE=R/'giriss-all9-component-behavior-source-r3-20261020'
PACK=BASE/'packs/comfy-image-saver/x65e6903/ComfyUI-Image-Saver-HEAD'
OUT=R/'giriss-string-literal-focused-source-r1-20261026'
assert not OUT.exists()
checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,label):
 if not ok:raise AssertionError(label)
 checks.append(label)
def put(name,b):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(b if isinstance(b,bytes) else b.encode())
def save(name,value):put(name,json.dumps(value,indent=2,sort_keys=True)+'\n')
require(sha((BASE/'HANDOFF.json').read_bytes())=='261732e7cf0581d1a896c8f6eb9380f6be2fc634b800023879c5a5cee5cb70dc','Exact retained all9 source handoff')
source=(R/'giriss_string_literal_slice_source_20261026.py').read_bytes();tree=ast.parse(source)
require(not any(isinstance(n,ast.If) and '__main__' in ast.unparse(n.test) for n in tree.body),'No runnable owner or CLI')
require(not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['start','kill','Popen','setrlimit','encode_jpeg','encode_png'] for n in ast.walk(tree)), 'No lifecycle/new process/encoder call in focused source')
adapter=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='ForwardToActualGuest')
require(not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='local_call' for n in ast.walk(adapter)),'Guest adapter cannot call local proxy')
require('execution._async_map_node_over_list' in source.decode() and 'session.execute(plan, runtime, capabilities=frozenset()' in source.decode(),'Actual Core SDK and required-Guest dispatch authored')
OUT.mkdir()
files={}
for p in sorted(PACK.rglob('*')):
 if p.is_file():
  name=p.relative_to(PACK).as_posix();b=p.read_bytes();put('frozen-pack/'+name,b)
  files[name]=dict(bytes=len(b),sha256=sha(b),mode='100644')
manifest=json.loads((PACK/'v2/secure-nodes.json').read_bytes())
require(len(manifest['nodes'])==9,'All9 actual normal registrations preserved')
require(sha((PACK/'v2/secure-nodes.json').read_bytes())=='b87c0e7ac0754dc640134ae9608f9cbbce358510d87ee63f75a95ae0d2e4a6dc','Exact previously generated normal9 manifest reused')
node='String_Literal_5bb4d668d27398985246d1d5';definition=manifest['nodes'][node]
require(definition['class']=='StringLiteral' and definition['sdk_refs'] is True and definition['permissions']==[],'Exact current zero-capability scalar production definition')
candidate=ast.parse((PACK/'v2/nodes.py').read_bytes());native=ast.parse((PACK/'nodes.py').read_bytes())
for t,method in [(candidate,'execute'),(native,'get_string')]:
 cls=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='StringLiteral')
 fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==method)
 require(len(fn.body)==1 and isinstance(fn.body[0],ast.Return),'Exact original/candidate simple string pass-through source')
require(ast.unparse(next(n for n in candidate.body if isinstance(n,ast.ClassDef) and n.name=='StringLiteral').body[-1].body[-1])=='return io.NodeOutput(string)','Production uses existing NodeOutput without scientific conversion')
put('focused_consumer.py',source)
cases=[('empty',''),('ascii','hello'),('leading-space','  leading'),('trailing-space','trailing  '),
 ('newlines','first\nsecond\r\nthird'),('tabs','\tleft\tright\t'),('nul','left\x00right'),
 ('unicode-composed','caf\u00e9'),('unicode-decomposed','cafe\u0301'),('emoji','\U0001f9ea \U0001f642'),
 ('literal-template','${seed} %date {prompt}'),('quotes','"single\' slash\\'),('long','abcd'*16384)]
require(len(cases)==len({k for k,v in cases})==13,'13 unique finite valid-string cases')
save('CASES.json',dict(status='AUTHORED_UNRUN',cases=[dict(id=k,value=v) for k,v in cases],
 expected='One-item tuple containing exact same Python str and UTF8 bytes',
 controls=['changed-string','wrong-container'],source_only=True))
save('PACK_SOURCE.json',dict(pack_id='comfy-image-saver/x65e6903',files=files,
 manifest_sha256=sha((PACK/'v2/secure-nodes.json').read_bytes()),
 all9_registration_ids=list(manifest['nodes']),selected_node=node,
 normal9_generation_repeated=False,production_files_rewritten=False))
save('ACTUAL_CONFIG.SOURCE_TEMPLATE.json',dict(execution_selected=False,authorization_message=None,
 pack_root=None,tenant_id=None,actual_source_pins={name:dict(path=None,sha256=None) for name in ['execution','io','sdk','packdb']},
 actual_accepted_owner=None,actual_interpreter_profile=None,actual_Guest_creation_profile_witness=None,
 retirement_required_from_existing_owner=True,not_a_standalone_selected_job=True))
save('PURPOSE_SCOPE.json',dict(authority='m_1053376416',status='SOURCE_CLOSED_FOCUSED_EXISTING_API_COMPARISON_UNRUN',
 selected_original_purpose='String Literal exact scalar pass-through',node_id=node,
 cheapest_reason='No encoder/output/raw/assets/checkpoint catalogue/model work;13small string cases using existing Core/SDK/Guest route',
 unneeded_global_prerequisite_removed_for_this_slice='Paired JPEG/PNG encoder adoption belongs to saver; not needed for this zero-permission literal',
 source_apis=['Existing io.ComfyNode/io.String/io.NodeOutput','Existing Core map/settle','Existing InProcess SDK providers','Existing packdb manifest proxies','Existing ordinary observed GuestSession.execute'],
 untouched=['All9 production IDs/code/manifest/frontend','All69native/61Guest source matrix','Tiny consumer/unsupported Hold source','Kimara sealedR4','Public API/generated contract/model files'],
 proposed_runtime=dict(original_calls=13,default_Core_calls=13,actual_Guest_calls=13,Guest_instances='Reuse one actual observed session from accepted owner',counterfactual_controls=2),
 actual_calls_here=0,accepted_purposes=0,all9_or_whole_pack_acceptance=False,
 review_required='Root concrete source review; existing owner/bootstrap/session/profile/complete maps and exact runtime selection remain separate; any general facility requires MIKE review'))
put('README.txt','''Focused GIRISS String Literal source closure, unrun.

This source isolates one inexpensive original purpose from the previously
authored all9-node encoder-gated comparison worker. It preserves the complete
frozen production pack and exact previously generated normal9 manifestb87c.
No generated contracts, public APIs, model files, owner lifecycle, production
or frontend code change. The all9 worker remains intact for its broader scope.

An accepted observing owner must supply a real required-Seatbelt ordinary
GuestSession, actual source/profile bindings and a separately selected config.
focused_consumer.compare_string_literal does not start/kill a session or claim
its retirement. It checks exact original/frozen candidate bytes, uses the full
genuine original and SDK candidate, and invokes both default and Guest paths
through actual Core-created plans. A tiny trusted dispatch adapter forwards the
real plan/runtime to the actual Guest with no permissions; it never local_calls.
Thirteen cases preserve spaces, CR/LF, tabs, NUL, Unicode normalization forms,
emoji, literal templates and a64KiB string. Both routes must preserve one-item
tuple and str identity. Changed-string/wrong-container controls remain separate.

This slice has no JPEG/PNG encoder dependency and requests no capability. It
still needs the real existing interpreter/dependencies to import the original
module and its untouched sibling classes. No stubs or fabricated providers
replace those imports. Actual accepted profile/source/whole source-site maps,
scope-specific owner budget/current capacity, captured Guest profile/live
identity and twice retirement remain unbound. No runtime authority is inferred
from the source slice or the Oct26 resume instruction.

No source/helper/science import, comparison, Guest, generator, model download,
shared service or test ran during preparation. Source closure is not behavioral
acceptance. Root reviews the concrete handoff; no new general API is proposed.
''')
put('references/PARENT_ALL9_HANDOFF.json',(BASE/'HANDOFF.json').read_bytes())
put('references/PARENT_EXECUTION_CONTRACT.json',(BASE/'EXECUTION_CONTRACT.json').read_bytes())
put('prepare_giriss_string_slice_20261026.py',Path(__file__).read_bytes())
asts=[]
for p in OUT.rglob('*.py'):
 ast.parse(p.read_bytes());asts.append(p.relative_to(OUT).as_posix())
save('SOURCE_STATIC_RECEIPT.json',dict(status='OWN_STDLIB_SOURCE_AST_HASH_ONLY',checks=len(checks),details=checks,AST_files=asts,
 supplied_imports_or_invocations=0,actual_comparisons=0,normalgen=0,Guest_instances_created=0))
rows=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes()),mode=0o644) for p in sorted(OUT.rglob('*')) if p.is_file()]
save('INPUTS.json',dict(files=rows))
save('HANDOFF.json',dict(status='FOCUSED_GIRISS_STRING_LITERAL_SOURCE_READY_FOR_REVIEW_UNRUN',authority='m_1053376416',
 parent_handoff_sha256=sha((BASE/'HANDOFF.json').read_bytes()),worker_sha256=sha(source),node_id=node,
 frozen_production_files=len(files),all9_manifest_preserved=True,planned_cases=13,planned_route_comparisons=26,
 planned_controls=2,new_public_APIs=0,generated_contract_edits=0,normalgen_runs=0,
 actual_source_imports_tests_comparisons_or_service_runs=0,execution_selected=False,whole_pack='PARTIAL',
 inputs_sha256=sha((OUT/'INPUTS.json').read_bytes()),next='Root concrete source review, later actual accepted owner/profile/session binding; no runtime selection here'))
archive=OUT.with_suffix('.SOURCE.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(OUT.rglob('*')):
  if p.is_file():
   info=zipfile.ZipInfo(p.relative_to(OUT).as_posix(),(2026,10,26,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,p.read_bytes())
with zipfile.ZipFile(archive) as z:
 require(len(z.namelist())==len(set(z.namelist()))==len(rows)+2,'Unique closed source archive')
 for n in z.namelist():require(z.read(n)==(OUT/n).read_bytes(),'Source archive exact bytes '+n)
print(json.dumps(dict(path=str(OUT),handoff_sha256=sha((OUT/'HANDOFF.json').read_bytes()),archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,
 checks=len(checks),AST_files=len(asts),production_files=len(files),supplied_execution=0)))
