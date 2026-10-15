"""Pack-owned frozen selection; metadata alone is not runtime admission."""
import json
from pathlib import Path

FILENAMES = (
    'depth_anything_v2_vitg.pth', 'depth_anything_v2_vitl.pth',
    'depth_anything_v2_vitb.pth', 'depth_anything_v2_vits.pth',
)
REQUIRED_EVIDENCE = (
    'verified_payload', 'restricted_raw_state_correspondence',
    'ordered_tensor_transport', 'published_sdk_distribution',
    'source_to_installed_graph', 'operator_abi', 'device_auto_policy',
    'image_model_realm', 'current_invocation_exclusive_lifetime',
    'finite_workspace_capacity_cleanup',
)

def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

def selected_asset(filename):
    if filename not in FILENAMES:
        raise ValueError('Only the four pinned relative node modes are exposed')
    selection = json.loads(Path(__file__).with_name('_depth_v2_asset_selection.json').read_text())
    row = selection['assets'][filename]
    def refuse(detail):
        raise RuntimeError('DepthAnythingV2 managed selection unapproved: ' + detail)
    if selection.get('approved') is not True or row.get('approved') is not True:
        refuse('actual catalogue/state/SDK/device/invocation selection required; owner GERALD/MERVYN')
    if not all(_digest(selection.get('evidence', {}).get(k)) for k in REQUIRED_EVIDENCE):
        refuse('incomplete actual evidence bindings')
    for k in ('catalogue_folder', 'catalogue_name'):
        if type(row.get(k)) is not str or not row[k] or '\x00' in row[k]:
            refuse('missing actual sealed catalogue identity')
    if type(row.get('verified_bytes')) is not int or row['verified_bytes'] <= 0 or not _digest(row.get('verified_sha256')):
        refuse('missing verified payload count/digest')
    contract = row.get('state_contract')
    if not isinstance(contract, dict):
        refuse('missing actual restricted reader correspondence')
    # The published reader may unwrap/prioritize a child; this integration
    # supports only a proved native flat tensor root. No flattening occurs here.
    if contract.get('raw_root') != 'flat_string_to_tensor' or contract.get('contains_state_dict_key') is not False:
        refuse('unsupported native checkpoint root/reader priority')
    if contract.get('has_metadata_attribute') is not False or contract.get('cpu_saved_storage') is not True:
        refuse('unsupported native metadata/saved storage')
    if contract.get('restricted_weights_only') is not True or contract.get('custom_globals_required') is not False:
        refuse('unsupported restricted code/container contract')
    specs = contract.get('ordered_tensors')
    if type(specs) is not list or not specs:
        refuse('missing actual ordered tensor census')
    keys = []
    for spec in specs:
        if not isinstance(spec, dict) or type(spec.get('key')) is not str or spec['key'] in keys:
            refuse('invalid actual ordered tensor keys')
        keys.append(spec['key'])
        if spec['key'] == 'state_dict' or type(spec.get('dtype')) is not str or not spec['dtype'].startswith('torch.'):
            refuse('unsupported tensor entry')
        if type(spec.get('shape')) is not list or any(type(d) is not int or d < 0 for d in spec['shape']):
            refuse('missing actual tensor shape')
    if type(contract.get('materialized_bytes')) is not int or contract['materialized_bytes'] <= 0:
        refuse('missing actual state size')
    budget = selection.get('selected_state_byte_budget')
    if type(budget) is not int or budget < contract['materialized_bytes']:
        refuse('missing fitting state transport budget')
    device = selection.get('torch_device')
    if type(device) is not str or not device:
        refuse('missing actual selected placement')
    if not _digest(selection.get('issued_invocation_receipt_sha256')):
        refuse('missing actual finite owner invocation binding')
    # Invocation/generation/device authority is an external owner gate; there
    # is no invented SDK generation API or cross-invocation local model cache.
    return selection, row
