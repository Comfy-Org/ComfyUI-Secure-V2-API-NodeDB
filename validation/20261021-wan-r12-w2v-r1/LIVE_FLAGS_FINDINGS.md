# WAN live-readiness audit: two flags checked (read-only, 2026-10-21)

These checks are static and read-only. They use r10 (corpus main `06b47fbe`, PR #62; no WAN code change since r9), the deployed
SDK `_sdk.py` `0d6ec97e`, and the live overlay copy (`execution.py` `33bd75f9`, `transport/host.py` `4480ba6d`,
`consent.py` `149b9e76`; the danny-overlay-successor-r48 deployment that LIVE_FACTS names).
Live environment fact, taken from LIVE_FACTS (not re-read here): `COMFY_SECURE_ALLOW_CAPABILITIES` is unset in every live
process.

## 1. DownloadAndLoadWav2VecModel: REAL

- Converted node `v2/secure_fantasytalking_nodes.py`:
  - :32-33 declares `models.download` and `SDK_REQUIRED_WEIGHTS = required_weights()`;
  - both weights are `on_demand=True` (`v2/secure_download_wav2vec_runtime.py:37-39`; `secure-nodes.json` agrees);
  - :45 `execute` calls `load_downloaded_wav2vec(...)` with the default `allow_download=True` (runtime :81-82).
- Runtime `private_bundle` (:48-49) calls `context.models.download_huggingface_weights(**weight)` *before* it resolves the
  installed asset (:52).
- On live:
  - Dispatch passes, because all its weights are on_demand: `execution.py:142-144` (`required = ... if not item.on_demand`;
    `if not required: return`).
  - `models.download` is in `CONSENT_REQUIRED` (`consent.py:28`). `app_allows` (:129-141) reads the unset
    `COMFY_SECURE_ALLOW_CAPABILITIES`, so `filter_capabilities` (:143) refuses it, and `_capabilities_for`
    (`execution.py:96-130`) grants a set without it.
  - In the guest, the download call reaches `host.py:2321` `_h_models_download_huggingface_weights`, and `self._require("models.download")` at :2324 raises
    (`host.py:414-417`): `WireError: capability 'models.download' not granted to node DownloadAndLoadWav2VecModel`. This
    happens on every run, even when the weight is installed.
- In-process tests passed because the in-process provider grants by declaration. Per its docstring (`_sdk.py:4053-4067`), it
  "reuses a valid installed file without a network request".
- Original (`fantasytalking/nodes.py:52-66`): `if not os.path.exists(model_path): snapshot_download(...)`. The original
  downloads only when the model is absent.
- r11 fix (this folder): exists-first. `if allow_download and not await context.assets.exists(folder, logical):` then
  download.
  - On live, `assets.exists` needs only `assets` (`host.py:1393-1396`). It is routed at `host.py:243` and sent by
    `guest/__init__.py:238`.
  - With the weight staged by the operator, the node then works on live without `models.download`. If the weight is absent,
    the node still asks for the download and is refused, as today.

### `assets.exists` is a declared public verb (MERVYN m_c53a20b61c, item 1)

- Published SDK stub: the live engine's `comfy_api/latest/_sdk_public.pyi` is `ca99b8e1...`, the same bytes as the native-core
  copy the tests use. `class AssetsDomain(Protocol)` is at :524, and :526 declares
  `async def exists(self, folder: str, name: str) -> bool: ...`. `assets: AssetsDomain` is at :877.
- The pack's own shipped stub, `v2/comfy-api.pyi` (`7a445480...`), has `class AssetsDomain` at :854 with the same signature at
  :858.
- Deployed runtime `_sdk.py` `0d6ec97e`: the Protocol is at :1957-1959, and `_InProcessAssets.exists` at :2484-2497 is an
  `os.path.isfile` check under the folder roots.
- Live: the host routes `"assets.exists"` to `_h_assets_exists` (`host.py:243`), and the handler requires only `assets`
  (:1393-1396). The guest proxy sends it at `guest/__init__.py:238`.
- r11 calls it with exactly that signature: `context.assets.exists(weight['folder'], logical)`. This is not the #4 ValueRef
  pattern.

## 2. WanVideoUniAnimateDWPoseDetector: REAL

- Converted node `v2/secure_unianimate_node.py`:
  - :11-12 builds `WEIGHTS` without `on_demand` (default False, `_sdk.py:1836`);
  - :59-60 declares `models.download` and `SDK_REQUIRED_WEIGHTS=WEIGHTS`;
  - `secure-nodes.json` has 2 entries without `on_demand`.
- Live (`execution.py:430-431`): `_provision_required_weights` runs before execute. `required` is non-empty, and
  `models.download` is not in the caps, so `PermissionError("node WanVideoUniAnimateDWPoseDetector requires Hugging Face
  model weights, but the models.download capability is not granted")` is raised (`execution.py:145-148`).
  - This happens before any installed-file reuse, which lives inside the provider (:149-163). So staged weights do not help.
- The node's own execute (:81-95) never downloads. `load_unianimate_jit` (:17-41) only resolves, sizes, digests and reads the
  two pinned assets. The block is the dispatch gate alone.
- Original (`unianimate/nodes.py:733-747`): exists-first, then `snapshot_download`.
- Fix options:
  - (a) platform: in `_provision_required_weights`, do not require `models.download` for a weight already installed under
    its catalogue name with its pinned sha256. This also unblocks Lynx (2 nodes, 6 entries) and the 21 Aux nodes (38 entries,
    none on_demand).
  - (b) pack: declare both `on_demand=True` and add the same exists-first step in execute. This changes
    `SDK_REQUIRED_WEIGHTS`, so `secure-nodes.json` must be regenerated with the official generator. It is a manifest change,
    unlike r11.
  - Either way the weights must be staged in the live store: `HF_HUB_OFFLINE=1` is set, and downloads are withheld.
