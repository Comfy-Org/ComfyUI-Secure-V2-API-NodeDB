"""Local data profile adapter to unchanged approved canonical generator."""
import argparse
import importlib.util
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser()
    for name in ('backend', 'site', 'core', 'v2', 'generator'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.backend), str(args.site), str(args.core)]
    sys.argv = ['join-normal-manifest', '--cpu']
    import comfy.options
    comfy.options.enable_args_parsing()
    spec = importlib.util.spec_from_file_location('_approved_generator', args.generator)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.PROFILES['comfy-join-prompt'] = {
        'nodes': 2, 'node_ids': ('jupo.JoinPrompt.JoinStrings', 'jupo.JoinPrompt.JoinPrompt'),
        'extension_entrypoint': True, 'web_directory': 'web'}
    return generator.main(['comfy-join-prompt', str(args.v2), str(args.v2 / 'secure-nodes.json')])

if __name__ == '__main__':
    raise SystemExit(main())
