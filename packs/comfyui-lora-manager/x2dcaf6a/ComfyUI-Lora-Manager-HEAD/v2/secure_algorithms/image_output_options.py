"""Options for verified public writer branches; other native branches held.

Current JPEG writer fixes subsampling=0; WebP omits method (Pillow default4).
The public exact-name writer is exclusive and cannot preserve native overwrite.
No option is silently dropped to claim a different native encoder behavior.
"""


def image_output_options(file_format, *, parameters=None, quality=100,
                         lossless_webp=True, jpeg_subsampling=0, webp_method=6,
                         save_with_metadata=True, add_counter_to_filename=True):
    if not add_counter_to_filename:
        raise NotImplementedError('Public exclusive image writer cannot preserve native no-counter overwrite')
    if file_format == 'jpeg' and jpeg_subsampling != 0:
        raise NotImplementedError('Public JPEG writer fixes subsampling at 0; native subsampling 1/2 remains pending')
    if file_format == 'webp' and webp_method != 4:
        raise NotImplementedError('Public WebP writer uses Pillow method 4; other native method choices remain pending')
    options = {'compress_level': 4, 'save_metadata': False,
               'a1111_parameters': parameters if save_with_metadata and parameters else None,
               'image_format': file_format, 'optimize': file_format == 'jpeg'}
    # The SDK validates quality/lossless globally. Omit them where the native
    # format never uses them, so its safe defaults do not alter that encoder.
    if file_format in ('jpeg','webp'):
        options['quality'] = quality
    if file_format == 'webp':
        options['lossless'] = lossless_webp
    return options
