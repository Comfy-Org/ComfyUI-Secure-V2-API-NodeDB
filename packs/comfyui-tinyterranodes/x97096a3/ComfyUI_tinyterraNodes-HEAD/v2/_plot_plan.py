"""Pack-owned literal-axis compilation for the original IMAGE plot path."""
import copy
import re


class PlotProfilePending(RuntimeError):
    pass


def list_nodes(count):
    # Selected Core CreateList uses the native default ten-name template.
    total=1
    while count>10:
        count=(count+9)//10;total+=count
    return total


def parse_value(input_name,value,node_inputs,input_types):
    if '.append' in input_name:
        input_name=input_name.replace('.append','')
        value=node_inputs[input_name]+' '+value
    matches=re.findall(r'%(.*?);(.*?)%',value)
    if matches:
        value=node_inputs[input_name]
        for search,replace in matches:
            value=re.compile(re.escape(search),re.IGNORECASE).sub(replace,value)
    for section in ('required','optional'):
        for name,info in (input_types.get(section) or {}).items():
            if name!=input_name:continue
            if info[0]=='INT':value=int(float(value))
            elif info[0]=='FLOAT':value=float(value)
            elif info[0] in ('BOOL','BOOLEAN'):
                if value.lower()=='true':value=True
                elif value.lower()=='false':value=False
                value=bool(value)
            elif type(info[0]) is list and value not in info[0]:
                raise KeyError(f'"{value}" not a valid value for input "{name}" in xyplot')
    return input_name,value


def relevant_prompt(prompt,caller_id):
    found={caller_id:None};pending=[caller_id]
    while pending:
        node=prompt[pending.pop()]
        for value in node['inputs'].values():
            if isinstance(value,list) and len(value)==2:
                if value[0] not in found:
                    found[value[0]]=None;pending.append(value[0])
    return {key:copy.deepcopy(prompt[key]) for key in reversed(found)}


def individual_mode(image_output,save_individuals):
    if save_individuals==True:
        return 'Hide/Save' if image_output in ('Hide','Hide/Save') else 'Save'
    return 'Preview' if image_output in ('Preview','Save') else 'Hide'


def compile_axes(prompt,caller_id,settings,input_types,*,node_input_types=None):
    """Convert axes in original order; retain later parse errors after prior cells."""
    caller_id=str(caller_id)
    x=settings.get('x_plot');y=settings.get('y_plot');z=settings.get('z_plot')
    if x is None and y is None:return None
    if z is None:z={'1':{'label':None}}
    columns=len(x) if x else 1;rows=len(y) if y else 1
    # The existing API permits at most 128 continuation nodes. Account the
    # pack's cell conversions, lists, plane renderers and final assembly first.
    cells=columns*rows*len(z)
    continuation_nodes=cells+len(z)*(list_nodes(columns*rows)+1)+list_nodes(len(z))+1
    if continuation_nodes>128:
        raise ValueError('plot exceeds the existing continuation-node ceiling')
    base=relevant_prompt(prompt,caller_id)
    original_mode=base[caller_id]['inputs']['image_output']
    base[caller_id]['inputs']['image_output']=individual_mode(original_mode,settings['save_individuals'])
    result=dict(variants=[],planes=[],failure=None,prompt=base,
                original_image_output=original_mode)
    touched={}

    def update(current,points):
        for node_id,values in points.items():
            if node_id=='label':continue
            if node_id not in current:
                raise KeyError(f'Node with ID: [{node_id}] not found in prompt for xyPlot')
            node_inputs=current[node_id]['inputs']
            for name,value in values.items():
                schema=(node_input_types(current[node_id]['class_type'],name.replace('.append',''),node_id)
                        if node_input_types is not None else
                        input_types(current[node_id]['class_type'],name.replace('.append','')))
                name,value=parse_value(name,value,node_inputs,schema)
                if (node_id==caller_id or name not in node_inputs
                        or isinstance(node_inputs[name],list) and len(node_inputs[name])==2):
                    raise PlotProfilePending('plot requires a caller, linked-input or topology mutation')
                node_inputs[name]=value;touched[node_id,name]=None

    def cell(current,plane):
        variant=dict(id='cell-'+str(len(result['variants'])),overrides=[
            dict(node_id=node_id,input_name=name,value=copy.deepcopy(current[node_id]['inputs'][name]))
            for node_id,name in touched])
        result['variants'].append(variant);plane['cells'].append(variant['id'])

    try:
        for points in z.values():
            z_prompt=copy.deepcopy(base);update(z_prompt,points)
            plane=dict(cells=[],x_labels=[],y_labels=[],z_label=points['label'],
                z_points=copy.deepcopy(z),has_x=x is not None,has_y=y is not None,
                columns=columns,rows=rows,spacing=settings['grid_spacing'],
                invert=settings['invert_bg'])
            if x:
                for x_points in x.values():
                    plane['x_labels'].append(x_points['label'])
                    x_prompt=copy.deepcopy(z_prompt);update(x_prompt,x_points)
                    if y:
                        for y_points in y.values():
                            plane['y_labels'].append(y_points['label'])
                            y_prompt=copy.deepcopy(x_prompt);update(y_prompt,y_points)
                            cell(y_prompt,plane)
                    else:cell(x_prompt,plane)
            elif y:
                for y_points in y.values():
                    plane['y_labels'].append(y_points['label'])
                    y_prompt=copy.deepcopy(z_prompt);update(y_prompt,y_points)
                    cell(y_prompt,plane)
            result['planes'].append(plane)
    except (KeyError,ValueError,TypeError,OverflowError) as error:
        # A later malformed axis must not erase already completed cell effects.
        if not result['variants']:raise
        result['failure']=dict(kind=type(error).__name__,args=list(error.args))
    return result


def row_major(values,columns,rows):
    return [values[column*rows+row] for row in range(rows) for column in range(columns)]


def background_dimensions(width,height,settings):
    border=int((width//8)*1.5) if settings['has_x'] or settings['has_y'] else 0
    spacing=settings['spacing']
    return (settings['columns']*(width+spacing)-spacing+border*settings['has_y'],
            settings['rows']*(height+spacing)-spacing+border*settings['has_x']
            +border*(settings['z_points']['1']['label'] is not None),
            border if settings['has_y'] else 0,border if settings['has_x'] else 0)
