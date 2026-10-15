"""Pinned immutable ReaderField projection; no filesystem or memmap constructor."""
from typing import NamedTuple, Any
import numpy.typing as npt
from .gguf_math.const import GGUFValueType
class ReaderField(NamedTuple):
    offset: int
    name: str
    parts: list[npt.NDArray[Any]] = []
    data: list[int] = [-1]
    types: list[GGUFValueType] = []
    def contents(self, index_or_slice=slice(None)):
        if self.types:
            to_string = lambda x: str(x.tobytes(), encoding='utf-8')
            main_type = self.types[0]
            if main_type == GGUFValueType.ARRAY:
                sub_type = self.types[-1]
                if sub_type == GGUFValueType.STRING:
                    indices = self.data[index_or_slice]
                    if isinstance(index_or_slice, int):
                        return to_string(self.parts[indices])
                    else:
                        return [to_string(self.parts[idx]) for idx in indices]
                elif isinstance(index_or_slice, int):
                    return self.parts[self.data[index_or_slice]].tolist()[0]
                else:
                    return [pv for idx in self.data[index_or_slice] for pv in
                        self.parts[idx].tolist()]
            if main_type == GGUFValueType.STRING:
                return to_string(self.parts[-1])
            else:
                return self.parts[-1].tolist()[0]
        return None
