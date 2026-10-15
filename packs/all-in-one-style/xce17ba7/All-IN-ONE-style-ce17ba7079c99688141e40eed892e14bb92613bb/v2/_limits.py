"""Pre-operation exact projected text/replacement/log workload bounds."""
MAX_TEXT_BYTES = 65536
MAX_WORK_BYTES = 16777216
MAX_SELECTION_BYTES = 256

class ProfileError(ValueError):
    pass

def before(values, source):
    positive, negative = values['text_positive'], values['text_negative']
    if type(positive) is not str or type(negative) is not str or type(values['log_prompt']) is not bool:
        raise ProfileError('style plain STRING/BOOLEAN profile')
    pb, nb = len(positive.encode('utf-8')), len(negative.encode('utf-8'))
    if pb + nb > MAX_TEXT_BYTES:
        raise ProfileError('style input text budget')
    work = pb + nb
    selection_bytes = 0
    fields = [(k,v) for k,v in values.items() if k not in ('text_positive','text_negative','log_prompt')]
    if len(fields) > len(source.NODES['ComfyUI Styler']):
        raise ProfileError('style selection item budget')
    for menu, selection in fields:
        if type(menu) is not str or type(selection) is not str:
            raise ProfileError('style plain selection profile')
        if menu not in source.NODES['ComfyUI Styler']:
            raise ProfileError('style unknown menu profile')
        encoded_menu, encoded_selection = len(menu.encode()), len(selection.encode())
        if encoded_selection > MAX_SELECTION_BYTES:
            raise ProfileError('style selection text budget')
        selection_bytes += encoded_menu + encoded_selection
        # Invalid names intentionally retain the native KeyError before work.
        template = source.styler_data[menu][selection]
        count = template.prompt.count('{prompt}')
        next_pb = len(template.prompt.encode()) - count * 8 + count * pb
        prefix = len(template.negative_prompt.encode())
        next_nb = prefix + nb + (2 if prefix and nb else 0)
        if next_pb + next_nb > MAX_TEXT_BYTES:
            raise ProfileError('style projected output text budget')
        work += len(template.prompt.encode()) + pb + next_pb + prefix + nb + next_nb
        if work > MAX_WORK_BYTES:
            raise ProfileError('style cumulative work budget')
        pb, nb = next_pb, next_nb
    if values['log_prompt']:
        work += 2 * (len(positive.encode()) + len(negative.encode()) + pb + nb + selection_bytes) + 4096
    if work > MAX_WORK_BYTES:
        raise ProfileError('style print work budget')
    return pb, nb
