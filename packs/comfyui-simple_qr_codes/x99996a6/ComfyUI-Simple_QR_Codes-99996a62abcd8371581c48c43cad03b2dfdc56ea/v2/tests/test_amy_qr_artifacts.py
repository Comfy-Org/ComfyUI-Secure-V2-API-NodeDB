"""Complete manifest and portable pair proof, bound only to explicit roots."""
import copy,hashlib,json,os,shutil
from pathlib import Path
import pytest
from test_amy_qr_algorithms import V2,PACK,NEW
from comfy_secure_nodes import packpatch,packdb
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
SNAPSHOT=PACK.parent; DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-simple_qr_codes/x99996a6/comfyui-simple_qr_codes-x99996a6'
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),
  'nodes':{node_id:{'module':'_secure_nodes','class':c.__name__,'sdk_refs':False,
   'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},
   'schema':encode_schema(copy.deepcopy(c.GET_SCHEMA()))} for node_id,c in NEW.NODE_CLASS_MAPPINGS.items()},
  'web_directory':'web','frontend_permissions':[]}
def test_complete_manifest_live_proxy_front_listing_and_unchanged_resources():
 assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest()
 proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_qr_proxy')
 assert list(proxy.node_mappings)==list(NEW.NODE_CLASS_MAPPINGS) and not proxy.routes
 assert proxy.web_directory==V2/'web'
 assert list(p.relative_to(V2/'web').as_posix() for p in (V2/'web').rglob('*.js'))==['show_data.js']
 for rel in ('LICENSE','images/logo.jpg','images/README.md','support/web_color_table.md','old_versions/README.md','old_versions/ComfyUI-Simple_QR_Codes-20250217_01.zip','.github/FUNDING.yml'):
  assert (V2/rel).read_bytes()==(PACK/rel).read_bytes()
 profile=json.loads((V2/'runtime-provenance.json').read_bytes())
 for name in ('comfy-api.d.ts','comfy-api.pyi'):
  assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==profile['owned_declarations'][name]['sha256']
 caller_roots={'COMFY_CORE_ROOT':Path(os.environ['COMFY_CORE_ROOT']),
               'QR_OVERLAY_ROOT':Path(os.environ['QR_BACKEND_ROOT']).parent}
 for row in profile['selected_runtime'].values():
  # Stored absolute paths are historical evidence, never ambient test inputs.
  current=caller_roots[row['root']]/row['relative']
  assert current.is_file() and not current.is_symlink()
  assert hashlib.sha256(current.read_bytes()).hexdigest()==row['sha256']
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
def test_plain_and_zip_pair_rebuild_exactly_twice_and_tamper_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes())==expected
 assert PAIR.with_suffix('.diff').read_bytes().decode('utf8')==diff
 bundle=packpatch.bundle(expected,diff)
 assert PAIR.with_suffix('.zip').read_bytes()==bundle
 for iteration in range(2):
  fresh=tmp_path/str(iteration)/'comfyui-simple_qr_codes/x99996a6';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if iteration==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,bundle)
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 bad=tmp_path/'wrong/comfyui-simple_qr_codes/x99996a6';bad.mkdir(parents=True)
 shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (bad/PACK.name/'__init__.py').open('ab') as stream:stream.write(b'\n#tamper')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,expected,diff)
 assert not (bad/PACK.name/'v2').exists()
