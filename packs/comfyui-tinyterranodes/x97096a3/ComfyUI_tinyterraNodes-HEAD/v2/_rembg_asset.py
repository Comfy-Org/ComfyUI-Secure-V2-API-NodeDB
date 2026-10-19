"""Genuine U2Net/rembg in the guest, using only an admitted managed asset."""
import asyncio
import contextlib
import hashlib
import importlib.metadata
import os
from pathlib import Path
import sys
import tempfile

from comfy_api.latest import sdk


MODEL_FOLDER = 'background_removal'
MODEL_NAME = 'u2net.onnx'
MODEL_BYTES = 175997641
MODEL_SHA256 = '8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491'
MODEL_MD5 = '60024c5c889badc19c04ad937298a77b'
RANGE_BYTES = 4 * 1024 * 1024
_SESSION_LOCK = asyncio.Lock()


@contextlib.contextmanager
def _private_vendor_cache(cache):
    # These are vendor-supported inputs. HOME and the vendor implementation stay
    # untouched. The guest's externally enforced network denial is mandatory.
    values = {'U2NET_HOME': str(cache), 'OMP_NUM_THREADS': '1', 'MODEL_CHECKSUM_DISABLED': None}
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


async def _copy_model(assets, destination):
    asset = await assets.resolve(MODEL_FOLDER, MODEL_NAME)
    if await assets.size(asset) != MODEL_BYTES or await assets.digest(asset) != MODEL_SHA256:
        raise ValueError('The admitted U2Net asset does not match the selected model')
    digest = hashlib.sha256()
    vendor_digest = hashlib.md5()
    offset = 0
    created = None
    try:
        with destination.open('xb') as output:
            created_stat = os.fstat(output.fileno())
            created = (created_stat.st_dev, created_stat.st_ino)
            while offset < MODEL_BYTES:
                length = min(RANGE_BYTES, MODEL_BYTES - offset)
                data = await assets.read_range(asset, offset=offset, length=length)
                if type(data) is not bytes or len(data) != length:
                    raise ValueError('The U2Net asset range is incomplete')
                digest.update(data)
                vendor_digest.update(data)
                output.write(data)
                offset += length
                await asyncio.sleep(0)
            if digest.hexdigest() != MODEL_SHA256 or vendor_digest.hexdigest() != MODEL_MD5:
                raise ValueError('The U2Net asset changed or failed its checksum')
            os.fchmod(output.fileno(),0o400)
    except BaseException:
        if created is not None:
            try:
                current = destination.lstat()
            except FileNotFoundError:
                pass
            else:
                if (current.st_dev,current.st_ino) == created:
                    destination.unlink()
        raise


async def remove(image):
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError('The selected rembg qualification target requires Python 3.13')
    for name, version in [('rembg', '2.0.67'), ('onnxruntime', '1.22.1'), ('numpy', '2.2.6')]:
        if importlib.metadata.version(name) != version:
            raise RuntimeError(f'The selected rembg target requires {name}=={version}')
    async with _SESSION_LOCK:
        with tempfile.TemporaryDirectory(prefix='tinyterra-u2net-') as directory:
            cache = Path(directory)
            await _copy_model(sdk.ctx().assets, cache / MODEL_NAME)
            # Lazy optional-backend import happens only after the complete asset
            # checks. A cache hit uses the unmodified vendor's checksum path.
            from rembg import new_session, remove as vendor_remove

            with _private_vendor_cache(cache):
                session = new_session('u2net', providers=['CPUExecutionProvider'])
                if session.inner_session.get_providers() != ['CPUExecutionProvider']:
                    raise RuntimeError('The selected CPU U2Net provider is unavailable')
                try:
                    return vendor_remove(image, session=session)
                finally:
                    del session
