"""Unrun fixed six-node normal manifest/pair/ZIP and four replay/control joins.

Called synchronously only after the existing async owner path has completed its
Guest cleanup. All generated files are in that invocation's owned output. The
frozen original/candidate and canonical generator/tool source are never edited.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import sys
import zipfile

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    root = Path(root).resolve(strict=True)
    rows = {}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            rows[path.relative_to(root).as_posix()] = dict(bytes=path.stat().st_size,
                sha256=digest(path), mode=stat.S_IMODE(path.stat().st_mode))
    return rows


def save(path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=True)+'\n').encode()
    assert len(raw) <= 512*1024
    path.write_bytes(raw)


def module_at(name, path):
    assert name not in sys.modules
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def copy_files(source, destination, rows):
    assert not destination.exists()
    destination.mkdir(parents=True)
    for relative, row in rows.items():
        assert row['mode'] == 0o644
        src, dst = source/relative, destination/relative
        assert src.is_file() and not src.is_symlink() and digest(src) == row['sha256']
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        dst.chmod(row['mode'])
    assert inventory(destination) == rows


def run_fixed_packaging(config, output):
    assert config['execution_selected'] is True and config['authorization_message']
    assert sys.version_info[:2] == (3, 13) and sys.dont_write_bytecode
    output = Path(output).resolve(strict=True)
    source = json.loads((HERE/'consumer/PACK_SOURCE.json').read_bytes())
    schemas = json.loads((HERE/'consumer/SCHEMAS.json').read_bytes())
    frozen = Path(config['pack_root']).resolve(strict=True)
    assert frozen == (HERE/source['packet_pack_relative']).resolve(strict=True)
    assert inventory(frozen) == source['files']
    assert len(source['original_files']) == 15 and len(source['candidate_files']) == 20
    generator_path = HERE/'generate_image_size_manifest.py'
    tool_path = HERE/'packpatch.py'
    assert digest(generator_path) == config['packaging_source_pins']['generator']['sha256']
    assert generator_path.resolve() == Path(config['packaging_source_pins']['generator']['path']).resolve(strict=True)
    assert digest(tool_path) == config['packaging_source_pins']['packpatch']['sha256'] == (
        '268df53fa640b4eb42ee342850e686790016ad15a207cf6a5a7e57ee5d5953a2')
    assert tool_path.resolve() == Path(config['packaging_source_pins']['packpatch']['path']).resolve(strict=True)
    generator = module_at('_image_size_normal_manifest_generator', generator_path)
    tool = module_at('_image_size_canonical_packpatch', tool_path)
    generated = output/'generated'/source['packet_pack_relative']
    copy_files(frozen, generated, source['files'])
    v2 = generated/'v2'
    manifest_path = v2/'secure-nodes.json'
    assert inventory(v2) == source['candidate_files'] and not manifest_path.exists()
    # Existing normal generator implementation; only its closed PROFILES entry
    # is new. This is outside asyncio.run(image_size_entry), after Guest cleanup.
    assert generator.main(['image-size-tools', str(v2), str(manifest_path)]) == 0
    manifest_path.chmod(0o644)
    manifest = json.loads(manifest_path.read_bytes())
    assert set(manifest) == {'format', 'runtime', 'nodes'}
    assert manifest['format'] == 'comfy-secure-nodes-v1'
    assert set(manifest['nodes']) == set(source['node_ids']) and len(manifest['nodes']) == 6
    assert manifest['runtime']['python']['requires'] == '>=3.13,<3.14'
    assert manifest['runtime']['python']['resolved'] == '3.13'
    for expected in schemas:
        definition = manifest['nodes'][expected['id']]
        assert definition['module'] == 'image_size_nodes' and definition['class'] == expected['id']
        assert definition['sdk_refs'] is True and definition['permissions'] == expected['permissions']
        assert definition['methods'] == dict(validate_inputs=False, fingerprint_inputs=False, check_lazy_status=False)
        encoded = definition['schema']
        assert encoded['hidden'] == []
        assert encoded['attrs']['node_id'] == expected['id']
        assert encoded['attrs']['display_name'] == expected['display_name']
        assert encoded['attrs']['category'] == expected['category']
        assert encoded['attrs']['is_input_list'] is False and encoded['attrs']['is_output_node'] is False
        assert len(encoded['inputs']) == len(expected['inputs'])
        assert len(encoded['outputs']) == len(expected['output_types'])
        for actual, inp in zip(encoded['inputs'], expected['inputs']):
            assert actual['io_type'] == inp['type'] and actual['attrs']['id'] == inp['id']
            assert not actual['attrs']['optional']
            if 'options' in inp:
                assert actual['attrs']['options'] == inp['options']
            if 'default' in inp:
                assert actual['attrs']['default'] == inp['default']
        assert [item['io_type'] for item in encoded['outputs']] == expected['output_types']
        assert [item['attrs']['display_name'] for item in encoded['outputs']] == expected['output_names']
    candidate_after = inventory(v2)
    assert len(candidate_after) == 21 and set(candidate_after) == set(source['candidate_files']) | {'secure-nodes.json'}
    assert {key:value for key, value in candidate_after.items() if key != 'secure-nodes.json'} == source['candidate_files']
    snapshot = generated.parent
    patches = output/'patch-pair'
    commands = []

    def invoke(argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = tool.main(argv)
        assert code == 0 and not stderr.getvalue()
        commands.append(dict(argv=argv, exit_code=code, stdout=stdout.getvalue(), stderr=stderr.getvalue()))

    invoke(['generate', str(snapshot), str(patches)])
    prefix = patches/'image-size-tools-x1cb252c'
    pair = json.loads(prefix.with_suffix('.json').read_bytes())
    assert pair['pack'] == 'image-size-tools' and pair['key'] == 'x1cb252c'
    assert pair['counts'] == dict(copy=12, convert=3, add=6, delete=0)
    assert len(pair['files']) == 21
    invoke(['bundle', str(prefix)])
    with zipfile.ZipFile(prefix.with_suffix('.zip')) as archive:
        assert set(archive.namelist()) == {prefix.with_suffix('.json').name, prefix.with_suffix('.diff').name}
        for suffix in ('.json', '.diff'):
            assert archive.read(prefix.with_suffix(suffix).name) == prefix.with_suffix(suffix).read_bytes()
    replays, controls = [], []
    for kind in ('pair', 'zip'):
        replay = output/('pristine-'+kind)/'image-size-tools'/'x1cb252c'/generated.name
        copy_files(frozen, replay, source['original_files'])
        before = inventory(replay)
        save(output/('REPLAY-'+kind+'-BEFORE.json'), before)
        argv = ['apply', str(replay.parent), str(prefix)] if kind == 'pair' else [
            'apply-zip', str(replay.parent), str(prefix.with_suffix('.zip'))]
        invoke(argv)
        after = inventory(replay)
        save(output/('REPLAY-'+kind+'-AFTER.json'), after)
        expected_after = dict(source['original_files'])
        expected_after.update({'v2/'+name:row for name, row in candidate_after.items()})
        assert after == expected_after and len(after) == 36
        replays.append(dict(kind=kind, original_files=15, generated_v2_files=21,
            all_bytes_modes_equal=True, raw_before_and_after_inventories_retained=True))

        bad = output/('changed-base-'+kind)/'image-size-tools'/'x1cb252c'/generated.name
        copy_files(frozen, bad, source['original_files'])
        target = bad/'image_size_nodes.py'
        target.write_bytes(target.read_bytes()+b'\n')
        bad_before = inventory(bad)
        save(output/('BADBASE-'+kind+'-BEFORE.json'), bad_before)
        bad_argv = ['apply', str(bad.parent), str(prefix)] if kind == 'pair' else [
            'apply-zip', str(bad.parent), str(prefix.with_suffix('.zip'))]
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                tool.main(bad_argv)
        except tool.PackPatchError as error:
            assert str(error).startswith('base file does not match the manifest: image_size_nodes.py')
            refusal = dict(type=type(error).__name__, message=str(error))
        else:
            raise AssertionError('Specific changed-base control was accepted')
        bad_after = inventory(bad)
        save(output/('BADBASE-'+kind+'-AFTER.json'), bad_after)
        assert bad_after == bad_before and not (bad/'v2').exists()
        controls.append(dict(kind=kind, changed_file='image_size_nodes.py',
            exception=refusal['type'], message=refusal['message'], refused=True,
            destination_unchanged=True, raw_before_and_after_inventories_retained=True))
    assert inventory(frozen) == source['files']
    result = dict(status='PASS_FIXED_NORMAL_MANIFEST_PAIR_ZIP_TWO_PRISTINE_TWO_BADBASE_ONLY',
        normal_generator_runs=1, generated_nodes=6, generated_v2_files=21,
        original_files=15, source_frozen_unchanged=True, pair_counts=pair['counts'],
        manifest=dict(path=str(manifest_path), sha256=digest(manifest_path)),
        commands=commands, replays=replays, changed_base_controls=controls,
        whole_pack_or_runtime_or_service_accepted=False)
    save(output/'PACKAGING_RESULT.json', result)
    return result
