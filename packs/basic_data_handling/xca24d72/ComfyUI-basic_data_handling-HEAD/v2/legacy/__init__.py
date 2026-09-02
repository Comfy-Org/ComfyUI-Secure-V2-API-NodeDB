"""Guest-safe pinned algorithms for Basic Data Handling."""
from . import (boolean_nodes, casting_nodes, comparison_nodes, control_flow_nodes,
    data_list_nodes, dict_nodes, float_nodes, int_nodes, list_nodes, math_nodes,
    math_formula_node, regex_nodes, set_nodes, string_nodes, tensor_nodes, time_nodes)

MODULES = (boolean_nodes, casting_nodes, comparison_nodes, control_flow_nodes,
    data_list_nodes, dict_nodes, float_nodes, int_nodes, list_nodes, math_nodes,
    math_formula_node, regex_nodes, set_nodes, string_nodes, tensor_nodes, time_nodes)
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
for module in MODULES:
    NODE_CLASS_MAPPINGS.update(module.NODE_CLASS_MAPPINGS)
    NODE_DISPLAY_NAME_MAPPINGS.update(module.NODE_DISPLAY_NAME_MAPPINGS)
