"""Reviewed stdlib supervision and canonical source metadata helpers."""
import time
STARTED = time.monotonic()
DEADLINE = STARTED + 55
FINAL_DEADLINE = STARTED + 58
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import selectors
import signal
import stat
import subprocess
import sys
import zipfile
ROOT = Path(__file__).resolve().parent

def require(value, message):
    if not value:
        raise RuntimeError(message)

def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            tick()
            result.update(data)
    return result.hexdigest()

def rel(name):
    path = PurePosixPath(name)
    require(name and not path.is_absolute() and path.as_posix() == name
            and ".." not in path.parts and "\\" not in name and "\0" not in name,
            "Unsafe relative source name")
    return path

def file_at(root, name):
    path = root.joinpath(*rel(name).parts)
    require(path.is_file() and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve()), "Unsafe source file: " + name)
    return path

def inventory(root):
    found = {}
    for path in sorted(root.rglob("*")):
        tick()
        require(not path.is_symlink(), "Unexpected staged symlink")
        if path.is_dir():
            continue
        require(path.is_file() and path.stat().st_size <= 16 * 1024**2, "Unsafe staged file")
        found[path.relative_to(root).as_posix()] = {
            "sha256": sha(path), "git_mode": "100755" if path.stat().st_mode & 0o111 else "100644"}
    return found

def packet(expected):
    table = ROOT / "INPUT_SHA256SUMS"
    require(sha(table) == expected, "Wrong packet input table")
    pins = {}
    for line in table.read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(name not in pins and re.fullmatch("[0-9a-f]{64}", digest), "Bad/duplicate source pin")
        require(sha(file_at(ROOT, name)) == digest, "Packet source changed: " + name)
        pins[name] = digest
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()}
    require(actual == set(pins) | {"INPUT_SHA256SUMS", "HANDOFF.json"}, "Unexpected packet file set")
    return pins

def git(backend, *arguments):
    tick()
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    out = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(backend), *arguments],
                         env=env, capture_output=True, timeout=max(0.001, DEADLINE - time.monotonic()))
    require(out.returncode == 0 and len(out.stdout) <= 2 * 1024**2 and len(out.stderr) <= 16384,
            "Read-only source Git lookup failed")
    return out.stdout

def verify_backend(args, spec):
    binding = spec["actual_mac_binding"]
    backend = args.backend_root.resolve(strict=True)
    require(args.backend_root.is_absolute() and re.fullmatch("[0-9a-f]{40}", args.backend_commit), "Explicit actual backend root/full commit required")
    require(args.backend_commit == binding["overlay_commit"]
            and str(backend) == binding["backend_source_root"], "Actual backend selection changed; review first")
    source_receipt = ROOT / "inputs/mac-readback/OVERLAY-SOURCE-INVENTORY.json"
    require(sha(source_receipt) == binding["source_inventory_sha256"], "Selected converter source receipt changed")
    receipt = json.loads(source_receipt.read_bytes())
    require(receipt["overlay_head"] == args.backend_commit and receipt["backend_source_root"] == str(backend)
            and receipt["actual_sdk_profile_sha256"] == binding["profile_sha256"]
            and receipt["actual_sdk_result_sha256"] == binding["sdk_result_sha256"], "Converter source/SDK receipt association differs")
    top = Path(git(backend, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    prefix = backend.relative_to(top).as_posix()
    package = "comfy_secure_nodes" if prefix == "." else prefix + "/comfy_secure_nodes"
    rows = git(top, "ls-tree", "-rz", args.backend_commit, "--", package)
    verified = {}
    for entry in rows.split(b"\0"):
        if not entry:
            continue
        meta, raw = entry.split(b"\t", 1)
        mode, kind, expected_oid = meta.decode().split()
        name = raw.decode()
        require(kind == "blob" and mode in ("100644", "100755"), "Unsupported backend source object")
        path = file_at(top, name)
        data = path.read_bytes()
        actual_oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(actual_oid == expected_oid, "Actual backend differs from pinned source: " + name)
        local = path.relative_to(backend).as_posix()
        verified[local] = {"git_blob": expected_oid, "sha256": hashlib.sha256(data).hexdigest()}
    expected = {name.removeprefix("backend/"): {"git_blob": row["git_blob"], "sha256": row["sha256"]}
                for name, row in receipt["files"].items()}
    require(verified == expected, "Actual backend differs from MIKE's pinned complete package inventory")
    for name, expected_sha in binding["tool_sha256"].items():
        require(verified[name]["sha256"] == expected_sha, "Selected canonical tool hash changed")
    required = {"comfy_secure_nodes/" + name for name in ("__init__.py", "packmanifest.py", "packruntime.py", "packpatch.py")}
    require(required <= set(verified), "Actual canonical backend tooling absent")
    for path in (backend / "comfy_secure_nodes").rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc" or path.is_dir():
            continue
        if path.suffix in (".py", ".so", ".dylib"):
            require(path.relative_to(backend).as_posix() in verified, "Unpinned importable backend source")
    return backend, verified

def child_limits():
    signal.pthread_sigmask(signal.SIG_SETMASK, set())
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))

def original(target):
    rows = {}
    for line in (ROOT / "inputs/ORIGINAL_GIT_TREE.tsv").read_text().splitlines():
        meta, name = line.split("\t", 1)
        mode, kind, oid = meta.split()
        rel(name)
        require(kind == "blob" and mode in ("100644", "100755"), "Unsupported pristine Git mode")
        rows[name] = (mode, oid)
    require(len(rows) == 43, "Wrong original source count")
    target.mkdir(parents=True)
    with zipfile.ZipFile(ROOT / "inputs/ORIGINAL.zip") as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        require(len(members) == len(rows) and {item.filename for item in members} == set(rows), "Original archive file set differs")
        for item in members:
            tick()
            require(not stat.S_ISLNK(item.external_attr >> 16) and item.file_size <= 16 * 1024**2, "Unsafe original member")
            data = archive.read(item)
            mode, oid = rows[item.filename]
            require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == oid, "Pristine Git blob differs")
            path = target.joinpath(*rel(item.filename).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
            path.chmod(0o755 if mode == "100755" else 0o644)

def tick():
    require(time.monotonic() < DEADLINE, "55-second work watchdog expired; cleanup reserved through58s")

def safe(root, name):
    parsed = PurePosixPath(name)
    require(name and not parsed.is_absolute() and ".." not in parsed.parts
            and parsed.as_posix() == name and "\\" not in name, "Unsafe relative input")
    path = root.joinpath(*parsed.parts)
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "Unsafe selected file: " + name)
    return path

def verify_runtime(actual, science):
    require(sys.platform == "darwin" and sys.version_info[:3] == (3, 13, 14), "Selected native Darwin Python3.13.14 required")
    require(actual["owner"] == "MERVYN" and actual["core_head"] == "44564d0279c275eef52b11750a9d76349f4e7a88", "Actual selected runtime differs")
    python = Path(actual["python"])
    require(sha(python.resolve()) == actual["python_sha256"] == sha(Path(sys.executable).resolve()), "Selected Python bytes changed")
    site, core = Path(actual["common_site_packages"]), Path(actual["core_source"])
    require(len(actual["sdk_files"]) == 141 and len(actual["core_files"]) == 1384, "Wrong actual runtime pin counts")
    for root, rows in ((site, actual["sdk_files"]), (core, actual["core_files"]), (site, science["site_file_pins"])):
        for name, digest in rows.items():
            require(sha(safe(root, name)) == digest, "Actual runtime/dependency pin changed: " + name)
    return python, site, core

def stop(number, frame):
    raise RuntimeError("Supervisor watchdog/termination signal " + str(number))

def retire_owned_group(child):
    """Unsandboxed controller: bounded leader reap AND owned-group absence."""
    end = min(FINAL_DEADLINE, time.monotonic() + 3)
    cleanup = {"owned_pgid": child.pid, "leader_reaped": False,
               "group_absence_confirmed": False, "errors": []}
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # Already absent; still reap/check below.
    except OSError as error:
        cleanup["errors"].append("signal: " + repr(error))
    while time.monotonic() < end:
        if not cleanup["leader_reaped"]:
            try:
                cleanup["leader_returncode"] = child.wait(timeout=min(0.05, max(0.001, end - time.monotonic())))
                cleanup["leader_reaped"] = True
            except subprocess.TimeoutExpired:
                pass  # Poll again only inside the bounded retirement window.
            except OSError as error:
                cleanup["errors"].append("reap: " + repr(error))
                break
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            cleanup["group_absence_confirmed"] = True
        except OSError as error:
            cleanup["errors"].append("group probe: " + repr(error))
            break
        else:
            cleanup["group_absence_confirmed"] = False
        if cleanup["leader_reaped"] and cleanup["group_absence_confirmed"]:
            break
        time.sleep(min(0.02, max(0, end - time.monotonic())))
    if not cleanup["leader_reaped"]:
        cleanup["errors"].append("leader reap unconfirmed within cleanup deadline")
    if not cleanup["group_absence_confirmed"]:
        cleanup["errors"].append("owned process group absence unconfirmed within cleanup deadline")
    cleanup["confirmed"] = (cleanup["leader_reaped"] and cleanup["group_absence_confirmed"]
                            and not cleanup["errors"])
    return cleanup

def run(command, scratch, name, report):
    tick()
    tmp = scratch / "temporary"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp), "TMPDIR": str(tmp), "XDG_CACHE_HOME": str(tmp / "cache"),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "OMP_NUM_THREADS": "1",
           "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
           "BLIS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": "",
           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    child = None
    row = {"name": name, "argv": [str(a) for a in command], "exit_code": None}
    capture = bytearray()
    try:
        # Keep a pending watchdog/termination signal from interrupting between
        # successful process creation and recording the owned child. Restore
        # the mask inside this try so any pending signal reaches cleanup.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM})
        try:
            child = subprocess.Popen([str(a) for a in command], cwd=scratch, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=child_limits)
            row["pid"] = child.pid
            report["commands"].append(row)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while selector.get_map():
                tick()
                for key, _ in selector.select(timeout=.1):
                    data = os.read(key.fileobj.fileno(), 4096)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    room = 16384 - len(capture)
                    capture.extend(data[:room])
                    require(len(data) <= room, "Tool capture exceeds16KiB")
        row["exit_code"] = child.wait(timeout=max(.001, DEADLINE - time.monotonic()))
        require(row["exit_code"] == 0, "Actual canonical command failed: " + name)
    finally:
        # Reserve the work deadline's final3s for outside-sandbox cleanup.
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            row["cleanup"] = retire_owned_group(child) if child is not None else {"confirmed": True, "not_started": True}
        except BaseException as error:
            row["cleanup"] = {"confirmed": False, "errors": [repr(error)]}
        (scratch / (name + ".log")).write_bytes(capture)
        if time.monotonic() < DEADLINE:
            signal.setitimer(signal.ITIMER_REAL, max(.001, DEADLINE - time.monotonic()))
        require(row["cleanup"]["confirmed"], "Owned group cleanup failed: " + name)

