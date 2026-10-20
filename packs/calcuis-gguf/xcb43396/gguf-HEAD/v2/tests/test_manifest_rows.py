"""Static guard (no core needed): the shipped manifest declares each node's own validator as the generator would.

The generator marks methods.validate_inputs from the class's own __dict__ and encodes getfullargspec (receiver kept).
"""
import ast
import json
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]


def test_manifest_validator_rows_match_source():
    tree = ast.parse((V2 / 'nodes.py').read_text())
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    manifest = json.loads((V2 / 'secure-nodes.json').read_text())
    assert len(manifest['nodes']) == 13
    for node_id, definition in manifest['nodes'].items():
        own = [item for item in classes[definition['class']].body
               if isinstance(item, ast.AsyncFunctionDef) and item.name == 'validate_inputs']
        assert len(own) == 1, node_id
        arguments = own[0].args
        assert definition['methods']['validate_inputs'] is True, node_id
        assert definition['validation_inputs'] == {'args': [a.arg for a in arguments.posonlyargs + arguments.args],
                                                   'kwargs': arguments.kwarg is not None}, node_id
