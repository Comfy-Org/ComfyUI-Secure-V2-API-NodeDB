"""Bounded test-only VP8 fixture, independent of the pack decoder profile."""
import av
import numpy as np
from pathlib import Path
target = Path(__file__).parent / "browser-preview.webm"
assert not target.exists()
with av.open(str(target), mode="w", format="webm") as container:
    stream = container.add_stream("libvpx", rate=4)
    stream.width, stream.height, stream.pix_fmt = 16, 8, "yuv420p"
    for index in range(4):
        array = np.full((8, 16, 3), index * 30, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
print(target)
