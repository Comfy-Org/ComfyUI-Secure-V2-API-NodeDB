"""Genuine pinned node components; explicitly NOT a full original package import.

The two original node files and common.py are loaded unchanged. Only the source
definitions AUTHOR, mk_name and mk_category are selected from original utils.py,
excluding its unused server-dependent Endpoint. No server or SDK is fabricated.
The calling isolated job must select and verify its real SDK before using this.
"""
import ast
import hashlib
import importlib.util
from pathlib import Path
import sys
import types

def mount_components(original: Path):
    root = original.resolve(strict=True)
    prefix = '_moe_join_original_components'
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules)
    paths = {'': root, '.py': root / 'py', '.py.nodes': root / 'py/nodes',
             '.py.nodes.join_prompt': root / 'py/nodes/join_prompt'}
    for suffix, path in paths.items():
        module = types.ModuleType(prefix + suffix)
        module.__path__ = [str(path)]
        module.__package__ = prefix + suffix
        sys.modules[module.__name__] = module
    utility_path = root / 'py/utils.py'
    utility_bytes = utility_path.read_bytes()
    tree = ast.parse(utility_bytes)
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'AUTHOR':
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in ('mk_name', 'mk_category'):
            selected.append(node)
    assert len(selected) == 3 and not any(isinstance(n, (ast.Import, ast.ImportFrom, ast.ClassDef)) for n in selected)
    utility_module = types.ModuleType(prefix + '.py.utils')
    utility_module.__file__ = str(utility_path)
    utility_module.__package__ = prefix + '.py'
    sys.modules[utility_module.__name__] = utility_module
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(utility_path), 'exec'), utility_module.__dict__)
    assert utility_module.AUTHOR == 'jupo'
    records = {'py/utils.py': hashlib.sha256(utility_bytes).hexdigest()}
    loaded = {}
    for name in ('common', 'join_strings', 'join_prompt'):
        path = root / ('py/nodes/join_prompt/' + name + '.py')
        module_name = prefix + '.py.nodes.join_prompt.' + name
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        loaded[name] = module
        records[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        'jupo.JoinPrompt.JoinStrings': loaded['join_strings'].JoinStrings,
        'jupo.JoinPrompt.JoinPrompt': loaded['join_prompt'].JoinPrompt,
    }, {
        'scope': 'Genuine unchanged original node components and common.py; original utility AUTHOR/naming function AST subset only.',
        'full_original_package_imported': False, 'server_module_injected': False,
        'sdk_substituted': False, 'original_files_sha256': records,
        'utility_selected_ast_sha256': hashlib.sha256(ast.dump(ast.Module(body=selected, type_ignores=[]), include_attributes=False).encode()).hexdigest(),
        'not_executed': ['original __init__.py', 'original py/__init__.py dynamic discovery', 'original utils.Endpoint class-time server usage'],
    }
