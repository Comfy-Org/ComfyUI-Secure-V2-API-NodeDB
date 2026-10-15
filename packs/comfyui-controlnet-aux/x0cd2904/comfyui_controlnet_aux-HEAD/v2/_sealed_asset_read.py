"""Whole sealed asset bytes through the bounded published range API.

The guest broker caps assets.read_bytes at COMFY_SECURE_ASSET_READ_MAX (64 MiB by
default; in-process has no cap), so the two routes diverge for larger checkpoints.
Families whose ORIGINAL loader needs the complete raw archive (restricted torch.load
of nested containers, TorchScript, ONNX) read it with assets.read_range, which both
routes bound to [1, 16 MiB] per call. The selected size and sha256 are verified over
exactly the bytes returned; nothing is cached or written.
"""
import hashlib

CHUNK = 16 * 1024 * 1024


async def read_sealed_asset(assets, ref, size, sha256):
    if type(size) is not int or size <= 0 or type(sha256) is not str or len(sha256) != 64:
        raise RuntimeError('sealed asset size/digest is unselected')
    if await assets.size(ref) != size:
        raise RuntimeError('sealed asset size differs')
    chunks = []; done = 0; h = hashlib.sha256()
    while done < size:
        chunk = await assets.read_range(ref, done, min(CHUNK, size - done))
        if type(chunk) is not bytes or not chunk or len(chunk) > size - done:
            raise RuntimeError('sealed asset range read differs')
        chunks.append(chunk); h.update(chunk); done += len(chunk)
    if done != size or h.hexdigest() != sha256:
        raise RuntimeError('sealed asset bytes differ')
    return b''.join(chunks)
