import atexit
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import types


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def constructor_code(code):
    popen = next(value for value in code.co_consts if isinstance(value, types.CodeType) and value.co_name == 'Popen')
    return next(value for value in popen.co_consts if isinstance(value, types.CodeType) and value.co_name == '__init__')


def record_imports(output):
    names = ['comfy_api.latest._sdk', 'comfy_api.latest._sdk_public', 'comfy_api.latest._io',
             'comfy_secure_nodes.asset_media', 'comfy_secure_nodes.remote_assets',
             'comfy_secure_nodes.packruntime', 'comfy_secure_nodes.transport.host',
             'comfy_secure_nodes.guest', 'torch', 'torch._C', 'numpy', 'PIL', 'httpx']
    rows = {}
    for name in names:
        module = sys.modules.get(name)
        source = getattr(module, '__file__', None)
        if source is None:
            rows[name] = {'imported': False}
        else:
            path = Path(source).resolve()
            rows[name] = {'imported': True, 'path': str(path), 'sha256': digest(path),
                          'version': getattr(module, '__version__', None)}
    output.write_text(json.dumps({'actual_loaded_modules': rows, 'forced_scientific_imports': False}, indent=2) + '\n')


def main():
    driver, observer_binding, readback, *tail = sys.argv[1:]
    source_row = json.loads(Path(observer_binding).read_bytes())['subprocess_source']
    source = Path(subprocess.__file__).resolve()
    if source != Path(source_row['path']).resolve() or digest(source) != source_row['sha256']:
        raise RuntimeError('Actual stdlib subprocess source differs from the sealed binding')
    actual = subprocess.Popen.__init__.__code__
    expected = constructor_code(compile(source.read_bytes(), actual.co_filename, 'exec', dont_inherit=True,
                                         optimize=sys.flags.optimize))
    if Path(actual.co_filename).resolve() != source or actual.co_firstlineno != 817 or actual != expected:
        raise RuntimeError('Actual Popen constructor differs from compile-only pinned source')
    if not sys.flags.isolated or sys.flags.no_site:
        raise RuntimeError('Selected isolated normal-site payload startup required')
    output = Path(readback)
    output.parent.mkdir(parents=True, exist_ok=True)
    (output.parent / 'ACTUAL-STDLIB-CODE-BINDING.json').write_text(json.dumps({
        'source_path': str(source), 'sha256': digest(source), 'co_firstlineno': actual.co_firstlineno,
        'actual_code_matches_compile_only_source': True, 'compiled_source_executed': False,
        'observer_or_launch_function_replaced': False, 'python': sys.executable,
        'prefix': sys.prefix, 'base_prefix': sys.base_prefix}, indent=2) + '\n')
    atexit.register(record_imports, output)
    sys.argv = [driver] + tail
    runpy.run_path(driver, run_name='__main__')


if __name__ == '__main__':
    main()
