"""Current catalogue facts and explicitly admitted external widget descriptors."""
import copy
from ._plot_plan import PlotProfilePending


async def schema_for_node(class_type, name, node_id):
    from comfy_api.latest import sdk
    from ._runtime import SCHEMAS, CANONICAL
    original = CANONICAL.get(class_type,class_type)
    if original in SCHEMAS:
        inputs = copy.deepcopy(SCHEMAS[original]['inputs'])
        info = {**inputs.get('required',{}),**inputs.get('optional',{})}.get(name)
        if info and type(info[0]) is list:
            choices = []
            for value in info[0]:
                if isinstance(value,str) and value.startswith('@catalog:'):
                    choices.extend(await sdk.ctx().assets.list(value[9:]))
                else:choices.append(value)
            info[0][:] = choices
        return inputs
    descriptor = await sdk.ctx().graph.input_options(str(node_id),name)
    kind = descriptor['type']
    if kind == 'COMBO':kind = descriptor['options']
    elif kind not in ('INT','FLOAT','STRING','BOOLEAN'):
        raise PlotProfilePending('external widget has no scalar descriptor')
    return {'required':{name:[kind]}}


async def prepare_axis_schemas(prompt,settings):
    # Resolve facts once, but defer any error to the original axis update.
    # A malformed later point must not erase prior planned cell effects.
    resolved = {}
    for axis in ('z_plot','x_plot','y_plot'):
        for point in (settings.get(axis) or {}).values():
            for node_id,values in point.items():
                if node_id == 'label' or node_id not in prompt:continue
                for key in values:
                    name = key.replace('.append','');pair = node_id,name
                    if pair in resolved:continue
                    try:
                        resolved[pair] = await schema_for_node(
                            prompt[node_id]['class_type'],name,node_id)
                    except Exception as error:
                        resolved[pair] = error
    def lookup(class_type,name,node_id):
        result = resolved[node_id,name]
        if isinstance(result,Exception):raise result
        return result
    return lookup
