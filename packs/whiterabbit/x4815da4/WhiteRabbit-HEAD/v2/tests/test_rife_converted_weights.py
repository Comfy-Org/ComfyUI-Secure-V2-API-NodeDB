"""WhiteRabbit repair (NED r2): the RIFE menus' pickle entries load their registered SafeTensors conversions (gate).

    DEPS=<torchlanc 1.1.1 unpacked> run_in_gate.sh <root holding WhiteRabbit-HEAD/, or that folder> <v2/tests> \
        <results> test_rife_converted_weights.py

In the gate host, with the v2 package imported the way packdb imports it (its __init__.py, the classes by name):
1. Declarations: every weight a RIFE row declares is SafeTensors (no pickle can be requested), in the
   frame_interpolation folder, with a sha256 pin.
2. Menu binding: each RIFE row's ckpt_name menu (from secure-nodes.json) is exactly the explicit name -> declaration
   map, and each name binds to one of the row's own declarations.
3. Manifest: each RIFE row's required_weights equal the real encoder's (packmanifest.encode_required_weights).
4. Load path, with a stand-in ctx (no network, no weights in the gate): selecting a menu name requests exactly its
   declaration (repo, file, folder, revision, sha256), resolves that catalogue name in its folder, and loads the state
   dict strictly into the architecture the menu name selects (rife47 and rife49, both the legacy 4.7 architecture:
   stand-in tensors with LegacyRife47's own names; the conversions keep the pickles' names). A name that is not
   declared is refused.
Writes /results/rife_converted_weights.json; exits 1 on any failed check.
"""

import asyncio
import importlib.util
import json
import sys
import traceback
from pathlib import Path

sys.path[:0] = ["/core", "/overlay"]
sys.path.append("/deps")

checks = []


def record(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": None if ok else str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {str(detail)[:400]}"), flush=True)


def pack_head(root: Path = Path("/pack")) -> Path:
    if (root / "v2").is_dir():
        return root
    heads = [d for d in sorted(root.iterdir()) if d.is_dir() and (d / "v2").is_dir()]
    if len(heads) != 1:
        raise SystemExit(f"/pack must hold exactly one pack folder: {heads}")
    return heads[0]


def load_package(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(name, folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Stop(Exception):
    """Ends a stand-in load after the request and the asset have been recorded."""


def run_load(nodes, sdk, name):
    """_loaded_rife(name) with a stand-in ctx; returns (requests, resolved, outcome)."""
    requests, resolved = [], []

    class Models:
        async def download_huggingface_weights(self, **kwargs):
            requests.append(dict(kwargs))
            return sdk.HuggingFaceWeight(on_demand=True, **kwargs).catalogue_name

    class Assets:
        async def resolve(self, folder, logical):
            resolved.append((folder, logical))
            return ("asset", folder, logical)

        async def load_state_dict(self, asset):
            # rife47 and rife49 are both the legacy 4.7 architecture; their conversions keep its tensor names.
            if asset[2].endswith(("/rife47.safetensors", "/rife49.safetensors")):
                return {key: value.clone() for key, value in nodes.LegacyRife47().state_dict().items()}
            raise Stop(asset)

    class Ctx:
        models = Models()
        assets = Assets()

    previous = sdk.ctx
    sdk.ctx = lambda: Ctx()
    try:
        nodes._RIFE_CACHE.pop(name, None)
        loaded = asyncio.run(nodes._loaded_rife(name))
        outcome = ("loaded", getattr(loaded.spec, "filename", None), getattr(loaded.spec, "architecture", None),
                   type(getattr(loaded, "inference_model", None)).__name__)
    except Stop:
        outcome = ("requested",)
    except Exception as error:  # noqa: BLE001
        outcome = ("error", f"{type(error).__name__}: {error}")
    finally:
        sdk.ctx = previous
    return requests, resolved, outcome


def main() -> int:
    facts = {}
    try:
        from comfy_api.latest import sdk
        from comfy_secure_nodes.packmanifest import encode_required_weights

        v2 = pack_head() / "v2"
        package = load_package("whiterabbit_v2_rife", v2)
        nodes = sys.modules["whiterabbit_v2_rife._secure_nodes"]
        manifest = json.loads((v2 / "secure-nodes.json").read_text())
        rows = {k: v for k, v in manifest["nodes"].items() if v.get("required_weights")}
        facts["rife_rows"] = sorted(rows)
        record("the manifest has RIFE rows with required weights", len(rows) == 4, sorted(rows))
        binding = dict(nodes._RIFE_BY_NAME)
        for node_id, row in sorted(rows.items()):
            cls = getattr(nodes, row["class"])
            declared = tuple(cls.SDK_REQUIRED_WEIGHTS)
            record(f"{node_id}: every declared weight is SafeTensors, in frame_interpolation, sha256-pinned",
                   declared and all(w.filename.endswith(".safetensors") and w.folder == "frame_interpolation"
                                    and w.sha256 for w in declared),
                   [(w.repo_id, w.filename, w.folder) for w in declared])
            menu = next(i["attrs"]["options"] for i in row["schema"]["inputs"] if i["attrs"]["id"] == "ckpt_name")
            record(f"{node_id}: the menu is exactly the explicit name -> declaration map, each bound to a declaration "
                   "of this row", list(menu) == list(binding) and all(binding[n] in declared for n in menu),
                   {"menu": menu, "binding": list(binding)})
            record(f"{node_id}: required_weights equal the real encoder's",
                   row["required_weights"] == encode_required_weights(cls),
                   {"manifest": row["required_weights"], "encoder": encode_required_weights(cls)})
        for name, weight in binding.items():
            requests, resolved, outcome = run_load(nodes, sdk, name)
            facts[f"load {name}"] = {"requests": requests, "resolved": resolved, "outcome": outcome}
            want = {"repo_id": weight.repo_id, "filename": weight.filename, "folder": weight.folder,
                    "revision": weight.revision, "sha256": weight.sha256}
            record(f"load {name}: requests exactly its declaration and resolves it in its folder",
                   requests == [want] and resolved == [(weight.folder, weight.catalogue_name)],
                   {"requests": requests, "resolved": resolved, "want": want})
            if name in ("rife47.pth", "rife49.pth"):
                record(f"load {name}: the state dict loads strictly into the architecture the name selects "
                       "(legacy 4.7)", outcome[0] == "loaded" and outcome[1] == name and outcome[2] == "legacy47",
                       outcome)
            else:
                record(f"load {name}: the stand-in stops after the asset (no tensors needed)",
                       outcome == ("requested",), outcome)
        requests, _resolved, outcome = run_load(nodes, sdk, "rife46.pth")
        record("a name that is not declared is refused before any request",
               outcome[0] == "error" and "unsupported RIFE checkpoint" in outcome[1] and not requests,
               (outcome, requests))
    except Exception:  # noqa: BLE001
        record("session", False, traceback.format_exc()[-3000:])
    failed = [c["check"] for c in checks if not c["ok"]]
    Path("/results").mkdir(parents=True, exist_ok=True)
    Path("/results/rife_converted_weights.json").write_text(
        json.dumps({"checks": checks, "failed": failed, "facts": facts}, indent=1, default=str) + "\n")
    print(json.dumps({"failed": failed}, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
