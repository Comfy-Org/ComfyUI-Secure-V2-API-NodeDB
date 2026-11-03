"""Monitor Pixaroma - pure helpers for the system-stats route.

Everything in here is a plain function over plain data: no torch, no psutil, no
aiohttp at module scope, so the whole file can be unit-tested with the system
python (D:\\Claude Tests\\_monitor_test.py). The route in server_routes.py does
the I/O and calls in here for the parsing and the arithmetic.

The one genuinely fiddly part is nvidia-smi's output, which is why it has its own
function with its own tests: it prints "[N/A]" and "[Not Supported]" for a field
the card does not report (a laptop GPU with no power sensor, a passive card with
no fan), and those must come back as None. Zero would read as a real measurement
- a card sitting at "0 W" looks broken, and 0 degrees looks alarming.
"""

# The exact query the route runs. Kept here beside the parser so the two can
# never drift: the parser indexes these columns positionally.
NVIDIA_SMI_FIELDS = (
    "index",
    "name",
    "utilization.gpu",
    "memory.used",
    "memory.total",
    "temperature.gpu",
    "power.draw",
)

NVIDIA_SMI_ARGS = (
    "--query-gpu=" + ",".join(NVIDIA_SMI_FIELDS),
    "--format=csv,noheader,nounits",
)

# nvidia-smi reports memory in MiB with --nounits.
_MIB = 1024 * 1024


def _num(text):
    """A number, or None for a field the card does not report.

    nvidia-smi writes "[N/A]", "[Not Supported]" and occasionally "[Unknown
    Error]" in place of a value. Anything that is not a plain number is None.
    """
    s = (text or "").strip()
    if not s or s.startswith("["):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _int(text):
    v = _num(text)
    return None if v is None else int(v)


def parse_nvidia_smi(text):
    """Parse the CSV nvidia-smi prints for NVIDIA_SMI_ARGS.

    Returns a list of dicts, one per GPU, in the order nvidia-smi listed them:

        {index, name, util, memUsed, memTotal, temp, power}

    util is a percent, memUsed/memTotal are BYTES (nvidia-smi gives MiB), temp is
    Celsius and power is Watts. Any field the card does not report is None.

    A malformed line is skipped rather than raising: this feeds a status readout,
    and one odd row from a mixed-GPU box must not blank the whole panel.
    """
    out = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(NVIDIA_SMI_FIELDS):
            continue
        idx = _int(parts[0])
        if idx is None:
            continue
        mem_used = _num(parts[3])
        mem_total = _num(parts[4])
        out.append(
            {
                "index": idx,
                "name": parts[1] or "GPU",
                "util": _num(parts[2]),
                "memUsed": None if mem_used is None else int(mem_used * _MIB),
                "memTotal": None if mem_total is None else int(mem_total * _MIB),
                "temp": _num(parts[5]),
                "power": _num(parts[6]),
            }
        )
    return out


def pct(used, total):
    """used/total as a 0-100 percent, or None when it cannot be known.

    Guards the two cases that produce a nonsense bar: a total of zero (a device
    that reports no memory) and a negative free value (which some drivers hand
    back momentarily during a reallocation).
    """
    try:
        u = float(used)
        t = float(total)
    except (TypeError, ValueError):
        return None
    if not (t > 0):
        return None
    if u < 0:
        u = 0.0
    if u > t:
        u = t
    return (u / t) * 100.0


def parse_visible_devices(env_value):
    """CUDA_VISIBLE_DEVICES, parsed into a logical->physical index list.

    Returns None when the variable is unset or blank (no masking: logical and
    physical indices agree), a list of ints when it is a plain index list
    ("1" -> [1], "0,2" -> [0, 2]: torch's cuda:i is nvidia-smi's list[i]), and
    [] when it is set but not an index list (GPU-<uuid> / MIG names, or
    anything malformed) - meaning "masked, but we cannot know the mapping".

    Review finding (2026-08-24): torch renumbers the VISIBLE devices from 0
    while nvidia-smi always reports PHYSICAL indices, so on a box pinned with
    CUDA_VISIBLE_DEVICES=1 an identity match attaches the idle card's
    temperature and load to the busy card - confidently wrong data.
    """
    if env_value is None:
        return None
    s = str(env_value).strip()
    if not s:
        return None
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        try:
            i = int(tok)
        except (TypeError, ValueError):
            return []
        if i < 0:
            # CUDA treats a negative entry as "stop here"; anything after it is
            # invisible. Rather than model that, give up on index mapping.
            return []
        out.append(i)
    return out


def gpu_extras_for(devices, smi_rows, visible=None):
    """Attach the nvidia-smi extras to our device list, matched BY INDEX.

    `visible` is parse_visible_devices(CUDA_VISIBLE_DEVICES): torch's index i
    is nvidia-smi's physical index visible[i] when a mask is set, and the
    identity without one. An unknowable mapping (visible == [], the UUID case)
    matches ONLY the unambiguous one-card-one-row case; everything else gets no
    extras, because an honest dash beats another card's temperature.

    When no row matches, the device simply carries no extras and the face hides
    those readouts, which is the same thing that happens on an AMD card or a
    Mac.
    """
    by_index = {}
    for row in smi_rows or []:
        if isinstance(row, dict) and row.get("index") is not None:
            by_index.setdefault(int(row["index"]), row)
    devices = devices or []
    out = []
    for dev in devices:
        d = dict(dev)
        idx = d.get("index")
        phys = None
        if isinstance(idx, int):
            if visible is None:
                phys = idx
            elif visible and 0 <= idx < len(visible):
                phys = visible[idx]
        row = by_index.get(phys) if isinstance(phys, int) else None
        # The one-card fallback may only adopt an INDEX-BASED device. Without
        # the isinstance, a CPU/MPS device (index None - what torch reports in
        # CPU-fallback mode, while nvidia-smi still sees the physical card)
        # would wear the GPU's temperature and load - the exact wrong-data
        # failure this mapping exists to prevent (round-2 review, 2026-08-24).
        if (
            row is None
            and isinstance(idx, int)
            and visible == []
            and len(devices) == 1
            and len(by_index) == 1
        ):
            row = next(iter(by_index.values()))
        if row:
            d["util"] = row.get("util")
            d["temp"] = row.get("temp")
            d["power"] = row.get("power")
            # nvidia-smi sees the WHOLE card, including every other program on
            # the machine. torch's own free/total only covers this process, so
            # for "how full is my card" the driver's number is the honest one -
            # a browser or a game holding 3 GB is invisible to torch.
            if row.get("memUsed") is not None and row.get("memTotal"):
                d["cardUsed"] = row["memUsed"]
                d["cardTotal"] = row["memTotal"]
        out.append(d)
    return out
