"""Native per-frame filename value; directory/counter ownership stays external."""
from __future__ import annotations


def image_output_filename(filename, batch_index, counter, file_format,
                          add_counter_to_filename=True):
    base_filename = filename.replace('%batch_num%', str(batch_index))
    if add_counter_to_filename:
        current_counter = counter + batch_index
        base_filename += f'_{current_counter:05}_'
    if file_format == 'png':
        return base_filename + '.png'
    if file_format == 'jpeg':
        return base_filename + '.jpg'
    if file_format == 'webp':
        return base_filename + '.webp'
    raise ValueError(f'Unsupported file format: {file_format}')
