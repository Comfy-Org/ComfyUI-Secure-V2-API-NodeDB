"""Portable exact47-child declarative plan; not an execution authority.

The current public graph contract rejects this complete140-node plan. The
original ImageBatch core type is intentionally not renamed or substituted.
"""
def plan_specs(options, pack_namespace, image, resolution=512):
    if type(pack_namespace) is not str or not pack_namespace or ' ' in pack_namespace:
        raise ValueError('caller pack namespace must be explicitly bound')
    if len(options) != 47 or options[0] != 'none':
        raise ValueError('exact original47 preprocessor list required')
    nodes = []
    def node(class_type, **inputs):
        local_id = 'n' + str(len(nodes) + 1)
        nodes.append({'id': local_id, 'class_type': class_type, 'inputs': inputs})
        return {'node': local_id, 'output': 0}
    curr_outputs = []
    for preprocc in options:
        preprocessor = node(pack_namespace + ' AIO_Preprocessor', preprocessor=preprocc, image=image, resolution=resolution)
        label = node(pack_namespace + ' ControlNetAuxSimpleAddText', image=preprocessor, text=preprocc)
        curr_outputs.append(label)
    while len(curr_outputs) > 1:
        new_outputs = []
        for i in range(0, len(curr_outputs), 2):
            if i + 1 == len(curr_outputs):
                new_outputs.append(curr_outputs[i])
            else:
                new_outputs.append(node('ImageBatch', image1=curr_outputs[i], image2=curr_outputs[i + 1]))
        curr_outputs = new_outputs
    return {'nodes': nodes, 'outputs': [curr_outputs[0]]}
