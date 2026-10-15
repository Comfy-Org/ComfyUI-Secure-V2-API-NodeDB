"""Locate the unchanged bundled font, including UTF8-only pack transport."""
def font_source(path):
    # Full source distributions use the exact original filename and loader.
    if path.exists():return str(path.resolve())
    # Source-only transport carries the byte-identical bundled resource as data.
    import base64,hashlib,io
    from ._font_bytes import FONT_BASE64,FONT_SHA256
    data=base64.b64decode(FONT_BASE64,validate=True)
    if hashlib.sha256(data).hexdigest()!=FONT_SHA256:raise ValueError('Bundled Aux font digest mismatch')
    return io.BytesIO(data)
