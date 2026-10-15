"""Bounded native OpenCV transport; PyAV only reads encoded metadata tags.

The temporary filename is guest-owned disposable transport, never a recovered
host path. Native codec parser peak memory remains a runtime-profile boundary.
"""
from io import BytesIO
import json
import os
from pathlib import Path
import posixpath
import tempfile
import av
import cv2
import numpy as np
from PIL import Image
from .limits import container_work, json_work, logical_label, text
from .video_algorithms import VideoAlgorithms

ENCODED_MAX = 524288
DECODE_FRAMES_MAX = 64
DECODE_PIXELS_MAX = 1048576
OUTPUT_BYTES_MAX = 8388608
WORK_BYTES_MAX = 16777216


def tags_from_bytes(blob, label):
    selected = None
    if posixpath.splitext(label)[1].lower() in (".webp", ".png", ".gif"):
        try:
            image = Image.open(BytesIO(blob))
        except OSError:
            image = None
        if image is not None:
            with image:
                container_work(image.info)
                if "prompt" in image.info:
                    selected = image.info["prompt"]
                elif "workflow" in image.info:
                    selected = json.dumps({"workflow_only": image.info["workflow"]})
                elif isinstance(image.info.get("exif"), bytes):
                    exif = image.info["exif"].decode("utf-8", errors="ignore")
                    if "prompt:" in exif:
                        selected = exif.split("prompt:")[1].split("\x00")[0]
    if selected is None:
        try:
            with av.open(BytesIO(blob), "r") as container:
                sources = [dict(container.metadata)] + [
                    dict(stream.metadata) for stream in container.streams if stream.type == "video"]
        except (av.error.FFmpegError, ValueError):
            sources = []
        container_work(sources)
        if sum(len(tags) for tags in sources) > 1024:
            raise ValueError("video tag count workload exceeded")
        for tags in sources:
            if any(not isinstance(k, str) or not isinstance(v, str) for k, v in tags.items()):
                raise ValueError("video tag text profile required")
            for key in ("comment", "prompt", "workflow", "description", "user_data"):
                for tag, value in tags.items():
                    if tag.lower() == key:
                        clean = value.strip()
                        if clean.startswith("{") or "Prompt:" in clean:
                            selected = clean
                            break
                if selected is not None:
                    break
            if selected is not None:
                break
    if selected is not None:
        text(selected)
        if selected.strip().startswith("{"):
            json_work(selected)
        elif selected.strip().startswith("Prompt:"):
            json_work(selected.strip()[7:])
    return selected


class BoundedCapture:
    def __init__(self, path):
        self.native = cv2.VideoCapture(path)
        self.frames = 0
        if not self.native.isOpened():
            return
        self.width = int(self.native.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.native.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not (0 < self.width <= 2048 and 0 < self.height <= 2048):
            self.release()
            raise ValueError("video decode dimension workload exceeded")
        if self.width * self.height > DECODE_PIXELS_MAX:
            self.release()
            raise ValueError("video decode pixel workload exceeded")

    def isOpened(self):
        return self.native.isOpened()

    def get(self, key):
        return self.native.get(key)

    def read(self):
        # Attempt budget includes the next native read, including EOF probing.
        if self.frames >= DECODE_FRAMES_MAX or (self.frames + 1) * self.width * self.height > DECODE_PIXELS_MAX:
            raise ValueError("cumulative video decode workload exceeded")
        ret, frame = self.native.read()
        if ret:
            self.frames += 1
            if frame.dtype != np.uint8 or frame.shape != (self.height, self.width, 3):
                raise ValueError("native decoded video frame profile mismatch")
        return ret, frame

    def release(self):
        self.native.release()


class ManagedVideoAlgorithms(VideoAlgorithms):
    def open_capture(self, path):
        self.capture = BoundedCapture(path)
        return self.capture

    def reserve_selected(self, width, height):
        count = self.selected_count + 1
        output = count * width * height * 16
        work = len(self.source_bytes) + count * width * height * 28 + self.capture.width * self.capture.height * 64
        if output > OUTPUT_BYTES_MAX or work > WORK_BYTES_MAX:
            raise ValueError("projected video output/allocation workload exceeded")

    def resize_frame(self, frame, size, *, interpolation):
        self.reserve_selected(*size)
        return cv2.resize(frame, size, interpolation=interpolation)

    def selected_frame(self, frame):
        # Called before native RGB conversion and float32 temporaries.
        height, width = frame.shape[:2]
        self.reserve_selected(width, height)
        count = self.selected_count + 1
        self.selected_count = count
        return frame

    def extract_raw_video_metadata(self, path):
        return self.metadata_raw


def analyze_video(blob, label, force_rate=0, max_frames=0, resize_long_edge=0, emoji_in_readable_text=True):
    logical_label(label)
    if not isinstance(blob, bytes) or len(blob) > ENCODED_MAX:
        raise ValueError("encoded video workload exceeded")
    for value, maximum in ((force_rate, 60), (max_frames, 10000), (resize_long_edge, 4096)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError("declared video option required")
    helper = ManagedVideoAlgorithms()
    helper.input_label, helper.source_bytes = label, blob
    helper.capture, helper.selected_count = None, 0
    helper.metadata_raw = tags_from_bytes(blob, label)
    path = None
    try:
        descriptor, name = tempfile.mkstemp(prefix="amy-srm-video-", suffix=".bin")
        path = Path(name)
        # Host-selected guest TMPDIR/cwd is tested in required-guest gates.
        if path.parent.resolve() != Path(tempfile.gettempdir()).resolve():
            os.close(descriptor)
            raise ValueError("guest-owned temporary directory mismatch")
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(blob)
        helper.decode_path = str(path)
        result = helper.load_video_analyze(label, force_rate, max_frames,
            resize_long_edge, emoji_in_readable_text)
        for value in result["result"]:
            if isinstance(value, str):
                text(value)
        container_work(result["ui"])
        return result
    finally:
        if helper.capture is not None:
            helper.capture.release()
        if path is not None:
            path.unlink()
