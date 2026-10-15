"""Read bounded broker-delivered Iridas cube data; no physical path authority."""
import numpy as np
from colour.io.luts.iridas_cube import LUT3D, LUT3x1D

MAX_LUT_BYTES = 8 * 1024 * 1024

def read_lut_bytes(payload, name, clip=True):
    if not isinstance(payload, bytes) or len(payload) > MAX_LUT_BYTES:
        raise ValueError("LUT exceeds bounded byte limit")
    text = payload.decode("utf-8")
    domain_min, domain_max = np.array([0,0,0]), np.array([1,1,1])
    dimensions, size = 3, 2
    data = []
    comments = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            comments.append(line[1:].strip())
            continue
        tokens = line.split()
        if tokens[0] == "TITLE":
            continue  # Upstream replaces the title with the logical filename.
        if tokens[0] == "DOMAIN_MIN":
            domain_min = np.asarray(tokens[1:], dtype=float)
        elif tokens[0] == "DOMAIN_MAX":
            domain_max = np.asarray(tokens[1:], dtype=float)
        elif tokens[0] in ("LUT_1D_SIZE", "LUT_3D_SIZE"):
            dimensions = 2 if tokens[0] == "LUT_1D_SIZE" else 3
            size = int(tokens[1])
            maximum = 65536 if dimensions == 2 else 65
            if not 2 <= size <= maximum:
                raise ValueError("LUT dimension exceeds bounded limit")
        else:
            if len(tokens) != 3 or len(data) >= 65**3:
                raise ValueError("LUT rows exceed bounded layout")
            data.append(tokens)
    if domain_min.shape != (3,) or domain_max.shape != (3,):
        raise ValueError("LUT domain must have three channels")
    table = np.asarray(data, dtype=float)
    if table.ndim != 2 or table.shape[1] != 3 or not np.isfinite(table).all():
        raise ValueError("LUT table must contain finite RGB triples")
    domain = np.vstack([domain_min, domain_max])
    if not np.isfinite(domain).all() or not (domain_max > domain_min).all():
        raise ValueError("LUT domain must be finite and increasing")
    if dimensions == 2:
        if len(table) != size:
            raise ValueError("LUT table does not match declared dimension")
        lut = LUT3x1D(table, name, domain, comments=comments)
    else:
        table = np.reshape(table, (size,size,size,3), order="F")
        lut = LUT3D(table, name, domain, comments=comments)
    if clip:
        if lut.domain[0].max() == lut.domain[0].min() and lut.domain[1].max() == lut.domain[1].min():
            lut.table = np.clip(lut.table, lut.domain[0,0], lut.domain[1,0])
        else:
            for dim in range(3):
                if dimensions == 2:
                    lut.table[:,dim] = np.clip(lut.table[:,dim],lut.domain[0,dim],lut.domain[1,dim])
                else:
                    lut.table[:,:,:,dim] = np.clip(lut.table[:,:,:,dim],lut.domain[0,dim],lut.domain[1,dim])
    return lut

