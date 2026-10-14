"""Real Torch/NumPy helper checks, separate from SDK/registered guest acceptance.

Run with an admitted interpreter, pristine find_mask_size.py, V2 file, and a
new writable report path. This script imports genuine installed dependencies;
it neither imports pack modules nor supplies SDK/provider/dependency mocks.
"""
import ast
import copy
import hashlib
import itertools
import json
import os
import platform
import sys
import time
from pathlib import Path

if not __debug__:
    raise SystemExit('Assertions disabled; refusing to produce a PASS report')
if sys.platform != 'linux':
    raise SystemExit('This bounded dependency verifier requires Linux')
assert len(sys.argv) == 4, 'interpreter script.py pristine.py converted.py NEW_report.json'
if os.name == 'posix':
    import resource
    import signal
    resource.setrlimit(resource.RLIMIT_AS, (8589934592, 8589934592))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    signal.alarm(45)
started = time.monotonic()
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import torch
import numpy as np
import PIL
from PIL import Image

torch.set_num_threads(1)
old_path, new_path, report_path = map(Path, sys.argv[1:])
assert not report_path.exists()
assert hashlib.sha256(old_path.read_bytes()).hexdigest() == '8b710c1f561fac7b0939ba322995a4e337a66441a962844d291d8e7cef5e2a72'
def helper(path):
    tree = ast.parse(path.read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'QImageCropCalculator')
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'calculate_optimal_crop')
before, after = helper(old_path), helper(new_path)
assert ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)
def bind(node):
    node = copy.deepcopy(node)
    for item in ast.walk(node):
        assert not isinstance(item, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal))
    scope = {'torch': torch, 'np': np}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<source-bound-real-dependency-helper>', 'exec'), scope)
    return scope[node.name]
old, new = bind(before), bind(after)
def capture(fn, mask, args):
    try:
        value = fn(None, mask, *args)
        return {'kind': 'result', 'values': [int(v) if isinstance(v, np.integer) else v for v in value],
                'types': [type(v).__module__ + '.' + type(v).__qualname__ for v in value]}
    except Exception as error:
        return {'kind': 'error', 'type': type(error).__name__, 'message': str(error)}
count = 0
errors = 0
def compare(mask, args):
    global count, errors
    expected, actual = capture(old, mask, args), capture(new, mask, args)
    assert actual == expected, (args, expected, actual)
    count += 1
    errors += actual['kind'] == 'error'
    return actual
for height, width in ((1, 1), (3, 7), (32, 48), (64, 96)):
    for dtype in (np.float32, np.float64, np.int32):
        patterns = []
        patterns.append(np.zeros((height, width), dtype=dtype))
        patterns.append(np.ones((height, width), dtype=dtype))
        single = np.zeros((height, width), dtype=dtype)
        single[height // 2, width // 2] = 1
        patterns.append(single)
        edge = np.zeros((height, width), dtype=dtype)
        edge[0, 0] = edge[-1, -1] = 1
        patterns.append(edge)
        rectangle = np.zeros((height, width), dtype=dtype)
        rectangle[max(0, height // 3):max(1, 2 * height // 3), max(0, width // 3):max(1, 2 * width // 3)] = 1
        patterns.append(rectangle)
        for mask, step, padding, minimum in itertools.product(patterns, (4, 8, 32), (0, 2, 8), (0, 16, 128)):
            args = (step, padding, minimum)
            array = compare(mask, args)
            tensor = compare(torch.from_numpy(mask.copy())[None], args)
            assert array == tensor
            batch = torch.stack((torch.from_numpy(mask.copy()), torch.ones_like(torch.from_numpy(mask.copy()))))
            assert compare(batch, args) == tensor, 'Native first-batch behavior changed'
threshold_records = []
for dtype in (np.float32, np.float64):
    boundary = dtype(0.1)
    for value in (np.nextafter(boundary, dtype(-np.inf)), boundary, np.nextafter(boundary, dtype(np.inf)), dtype(np.nan), dtype(np.inf), dtype(-np.inf)):
        mask = np.full((8, 12), value, dtype=dtype)
        outcome = compare(mask, (8, 0, 128))
        assert compare(torch.from_numpy(mask.copy())[None], (8, 0, 128)) == outcome
        expected = [12, 8, 0, 0] if bool((mask > 0.1).any()) else [128, 128, 0, 0]
        assert outcome['values'] == expected
        threshold_records.append({'dtype': np.dtype(dtype).name, 'value': str(value), 'expected': expected})
assert compare(np.zeros((640, 768), np.float32), (8, 8, 128))['values'] == [128, 128, 320, 256]
assert compare(np.ones((64, 96), np.float32), (8, 0, 128))['values'] == [96, 64, 0, 0]
point = np.zeros((32, 48), np.float32)
point[12, 23] = 1
assert compare(point, (8, 0, 0))['values'] == [0, 0, 23, 12], 'Preserve native coordinate span without+1'
assert compare(np.zeros((640, 768), np.float32), ())['values'] == [256, 256, 256, 192], 'Omitted helper defaults'
assert compare(np.zeros((640, 768), np.float32), (8, 8, 520))['values'] == [520, 520, 124, 60], 'Schema defaults remain distinct'
rng = np.random.default_rng(20261012)
for index in range(128):
    mask = rng.choice(np.array([0, 0.1, 0.10000001, 0.11, 1, np.nan], dtype=np.float32), size=(19, 31))
    args = ((4, 8, 32, 128)[index % 4], (0, 2, 8, 256)[(index // 4) % 4], (0, 128, 520)[index % 3])
    assert compare(mask, args) == compare(torch.from_numpy(mask.copy())[None], args)
bad_masks = [np.array(1), np.zeros((3,)), np.ones((3,)), np.zeros((2, 3, 4)), np.ones((2, 3, 4)),
             torch.empty((0, 3, 4)), torch.ones((3, 4)), torch.zeros((3, 4)),
             torch.ones((1, 3, 4), requires_grad=True), torch.ones((1, 3, 4), dtype=torch.bfloat16),
             None, [[0, 1], [0, 0]]]
bad_records = [compare(mask, (8, 0, 128)) for mask in bad_masks]
for args in ((0, 0, 128), (-4, 0, 128), (8, -2, -3), (8, 0, 0), (8, 0, 1.5), ('8', 0, 128), (8, None, 128)):
    bad_records.append(compare(point, args))
result = {'schema': 'ned-q-crop-real-dependency-helper-differential/1', 'status': 'PASS_HELPER_ONLY',
          'old_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(), 'new_sha256': hashlib.sha256(new_path.read_bytes()).hexdigest(),
          'interpreter': sys.executable, 'python': platform.python_version(), 'platform': platform.platform(),
          'genuine_dependencies': {name: {'version': module.__version__, 'path': module.__file__} for name, module in [('torch', torch), ('numpy', np), ('PIL', PIL)]},
          'comparisons': count, 'native_error_comparisons': errors, 'threshold_records': threshold_records,
          'malformed_and_out_of_schema_records': bad_records, 'elapsed_seconds': time.monotonic() - started,
          'target_module_imported': False, 'SDK_or_provider_mocked': False,
          'actual_installed_pack_profile': None, 'SDK_schema_manifest_raw_transport_guest_registered': 'NOT_RUN', 'accepted_delta': 0}
report_path.parent.mkdir(parents=True, exist_ok=True)
with report_path.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps({'status': result['status'], 'comparisons': count, 'report': str(report_path)}))
