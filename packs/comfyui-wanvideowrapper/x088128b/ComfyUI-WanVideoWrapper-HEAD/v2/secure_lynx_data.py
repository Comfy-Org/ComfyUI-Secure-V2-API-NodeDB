"""Pack-owned Lynx data branch. Native WanVAE image encoding remains closed.

Values stay shallow and opaque; this helper never resolves refs or model objects.
Existing Wan text/container/parser limits bound newly created data. These are
supported-workload limits, not a runtime profile or physical memory guarantee.
"""
MAX_TEXT_BYTES = 65536
MAX_CONTAINER_ITEMS = 4096
MAX_BLOCK_ENTRIES = 10001

def _preflight(embeds, ip, text):
    # Only closed finite JSON container shapes may supply native dict pairs.
    # Do not inspect ignored VAE/text metadata or dereference opaque values.
    if not isinstance(embeds, (dict, list, tuple, str, type(None), bool, int, float)):
        raise TypeError('Wan Lynx embeds require a bounded mapping or pair sequence')
    if isinstance(embeds, (dict, list, tuple)) and len(embeds) > MAX_CONTAINER_ITEMS:
        raise OverflowError('Wan Lynx input container exceeds 4096 entries')
    if isinstance(embeds, (list, tuple)):
        for pair in embeds:
            if not isinstance(pair, (list, tuple, str)):
                raise TypeError('Wan Lynx mapping pairs require finite sequences')
            if len(pair) > MAX_CONTAINER_ITEMS:
                raise OverflowError('Wan Lynx mapping pair exceeds 4096 entries')
    if isinstance(ip, (dict, list, tuple)) and len(ip) > MAX_CONTAINER_ITEMS:
        raise OverflowError('Wan Lynx IP container exceeds 4096 entries')
    strings = [text]
    if isinstance(embeds, str):
        strings.append(embeds)
    if isinstance(embeds, dict):
        strings.extend(embeds.keys())
    for value in strings:
        if isinstance(value, str) and len(value.encode('utf-8', errors='surrogatepass')) > MAX_TEXT_BYTES:
            raise OverflowError('Wan Lynx text exceeds 64 KiB')

def attach_lynx_data(embeds, ip_scale, ref_scale, start_percent, end_percent, lynx_cfg_scale, vae=None, lynx_ip_embeds=None, ref_image=None, ref_text_embed=None, ref_blocks_to_use=''):
    if ref_image is not None and ref_text_embed is None:
        raise ValueError('If ref_image is provided, ref_text_embed must also be provided.')
    if ref_image is not None:
        raise RuntimeError('Wan Lynx ref_image requires the source-owned WanVAE encode/device path; this staged data branch is not admitted for images')
    _preflight(embeds, lynx_ip_embeds, ref_blocks_to_use)
    if ref_blocks_to_use.strip() == '':
        ref_blocks_to_use = None
    else:
        expanded_entries = 0
        blocks = []
        for item in ref_blocks_to_use.split(','):
            item = item.strip()
            if '-' in item and (not item.startswith('-')):
                try:
                    start, end = item.split('-', 1)
                    start, end = (int(start.strip()), int(end.strip()))
                    projected = max(0, end - start + 1)
                    if expanded_entries + projected > MAX_BLOCK_ENTRIES:
                        raise OverflowError('Wan Lynx block expansion exceeds 10001 entries')
                    expanded_entries += projected
                    blocks.extend(list(range(start, end + 1)))
                except ValueError:
                    print(f'Invalid range format: {item}')
            elif item.isdigit():
                if expanded_entries + 1 > MAX_BLOCK_ENTRIES:
                    raise OverflowError('Wan Lynx block expansion exceeds 10001 entries')
                expanded_entries += 1
                blocks.append(int(item))
            else:
                print(f'Invalid block specification: {item}')
        ref_blocks_to_use = sorted(list(set(blocks)))
        if len(ref_blocks_to_use) > MAX_CONTAINER_ITEMS:
            raise OverflowError('Wan Lynx published block list exceeds 4096 entries')
        print('Using ref blocks:', ref_blocks_to_use)
    new_entry = {'ip_x': lynx_ip_embeds['ip_x'] if lynx_ip_embeds is not None else None, 'ip_x_uncond': lynx_ip_embeds['ip_x_uncond'] if lynx_ip_embeds is not None else None, 'ref_latent': ref_latent if ref_image is not None else None, 'ref_latent_uncond': ref_latent_uncond if ref_image is not None else None, 'ref_text_embed': ref_text_embed if ref_text_embed is not None else None, 'ip_scale': ip_scale, 'ref_scale': ref_scale, 'cfg_scale': lynx_cfg_scale, 'start_percent': start_percent, 'end_percent': end_percent, 'ref_blocks_to_use': ref_blocks_to_use}
    updated = dict(embeds)
    updated['lynx_embeds'] = new_entry
    if len(updated) > MAX_CONTAINER_ITEMS:
        raise OverflowError('Wan Lynx published mapping exceeds 4096 entries')
    return (updated,)
