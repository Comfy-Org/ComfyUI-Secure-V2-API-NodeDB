"""Verify actual service outputs including every PNG pixel using stdlib."""
from pathlib import Path, PurePosixPath
import binascii
import hashlib
import json
import struct
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / "sizefrompresets-service-test-r2-20261019"
load = lambda path: json.loads(path.read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def verify_png(path, expected_width, expected_height):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    idat = bytearray()
    header = None
    ended = False
    while pos < len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + size]
        crc = struct.unpack(">I", data[pos + 8 + size:pos + 12 + size])[0]
        assert binascii.crc32(kind + body) & 0xffffffff == crc
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        if kind == b"IDAT":
            idat.extend(body)
        pos += 12 + size
        if kind == b"IEND":
            ended = True
            break
    assert ended and pos == len(data)
    width, height, depth, color, compression, filtering, interlace = header
    assert (width, height) == (expected_width, expected_height)
    assert depth == 8 and color in (2, 6) and (compression, filtering, interlace) == (0, 0, 0)
    bpp = 3 if color == 2 else 4
    pixel = bytes((0x12, 0x34, 0x56)) + (b"\xff" if bpp == 4 else b"")
    expected = pixel * width
    raw = zlib.decompress(idat)
    stride = width * bpp
    assert len(raw) == height * (stride + 1)
    cache = {}
    for y in range(height):
        offset = y * (stride + 1)
        filter_kind = raw[offset]
        key = (filter_kind, y == 0)
        if key not in cache:
            assert 0 <= filter_kind <= 4
            encoded = bytearray(stride)
            for x, value in enumerate(expected):
                left = expected[x - bpp] if x >= bpp else 0
                above = expected[x] if y else 0
                upper_left = expected[x - bpp] if y and x >= bpp else 0
                if filter_kind == 0:
                    predict = 0
                elif filter_kind == 1:
                    predict = left
                elif filter_kind == 2:
                    predict = above
                elif filter_kind == 3:
                    predict = (left + above) // 2
                else:
                    p = left + above - upper_left
                    a, b, c = abs(p - left), abs(p - above), abs(p - upper_left)
                    predict = left if a <= b and a <= c else above if b <= c else upper_left
                encoded[x] = (value - predict) & 0xff
            cache[key] = bytes(encoded)
        assert raw[offset + 1:offset + 1 + stride] == cache[key], (path.name, y, "pixel mismatch")
    return {"path": path.name, "width": width, "height": height, "all_pixels": "RGB123456", "sha256": sha(path)}


positive = load(HERE / "POSITIVE_STATE.json")
negative = load(HERE / "NEGATIVE_STATE.json")
assert positive["status"] == positive["result"]["status"] == "passed"
assert positive["result"]["sandbox"] == "gvisor" and positive["result"]["phase"] == "complete"
assert negative["status"] == negative["result"]["status"] == "failed"
assert negative["result"]["phase"] == "execute" and negative["result"]["sandbox"] == "gvisor"
error = negative["result"]["error"]
assert error["type"] == "AssertionError" and error["message"] == "Size TEST dimensions differ from actual original result"
assert any(frame["file"] == "v2/tests/size_test_oracles.py" and frame["function"] == "checked_image" for frame in error["frames"])
assert negative["result"]["outputs"] == []
fixtures = load(ROOT / "coordination/sizefrompresets-service-test-source-r1-20261019/PLAN.json")["positive_paths"]
assert len(fixtures) == 10
artifacts = {row["node_id"]: row for row in load(HERE / "ARTIFACTS.json")}
assert len(artifacts) == 10 and set(artifacts) == {row["preview"] for row in fixtures}
pngs = []
facts = []
output = {row["node_id"]: row for row in positive["result"]["outputs"]}
for fixture in fixtures:
    width, height = fixture["png_dimensions"]
    artifact = artifacts[fixture["preview"]]
    png = verify_png(HERE / artifact["path"], width, height)
    assert png["sha256"] == artifact["sha256"]
    png["node_id"] = fixture["node_id"]
    pngs.append(png)
    if fixture["latent"]:
        text = output[fixture["oracle"]]["value"]["text"]
        assert len(text) == 1
        observed = json.loads(text[0])
        assert observed["reported_dimensions"] == [width, height]
        assert observed["shape"] == [1, 4, height // 8, width // 8] and observed["batch"] == 1
        assert observed["dtype"] == "torch.float32" and observed["device"] == "cpu" and observed["nonzero"] == 0
        facts.append(dict(observed, node_id=fixture["node_id"]))
assert len(facts) == 5
request = load(HERE / "POSITIVE_REQUEST.json")
prior = load(BASE / "POSITIVE_REQUEST.json")
for now, before in zip(request["files"], prior["files"], strict=True):
    assert now["path"] == before["path"]
    if now["path"] == "v2/tests/size_test_oracles.py":
        assert now["content"] == before["content"].replace("await latent.value\n", "await latent.value()\n")
    else:
        assert now == before
assert request["files"] == load(HERE / "NEGATIVE_REQUEST.json")["files"]
normal_receipt = load(ROOT / "coordination/sizefrompresets-generation-result-intake-r1-20261019/VERIFIED_RESULT_RECEIPT.json")
normal_path = Path(normal_receipt["production_v2"]) / "secure-nodes.json"
assert sha(normal_path) == "397ea4fdd91b8f7783294196a9a83b9f9b7d916c1f2494c2fa48b09fc5ea01d8"
test_manifest = json.loads(next(row["content"] for row in request["files"] if row["path"] == "v2/secure-nodes.json"))
normal = load(normal_path)
assert all(test_manifest["nodes"][key] == value for key, value in normal["nodes"].items())
helpers = load(HERE / "HELPER_DEFINITIONS.json")
assert set(test_manifest["nodes"]) == set(normal["nodes"]) | set(helpers)
assert all(test_manifest["nodes"][key] == value for key, value in helpers.items())
actual_argv = load(HERE / "ACTUAL_WORKER_ARGV.json")
assert actual_argv["test_id"] == positive["id"] and len(actual_argv["workers"]) == 1
assert actual_argv["workers"][0]["cpu_cli_argument_present"]
# R3 completed before its ephemeral ZIP could be copied. The retained first
# attempt ZIP plus the exact one-call source correction document the boundary.
expected = load(BASE / "ASSEMBLY.json")["files"]
retained_files = {}
with zipfile.ZipFile(BASE / "ACTUAL_POSITIVE_EPHEMERAL.zip") as archive:
    for item in archive.infolist():
        if item.is_dir():
            continue
        parts = PurePosixPath(item.filename).parts
        assert parts[0] == "MoeSizeServiceR2-HEAD"
        name = str(PurePosixPath(*parts[1:]))
        data = archive.read(item)
        assert hashlib.sha256(data).hexdigest() == expected[name]
        retained_files[name] = hashlib.sha256(data).hexdigest()
assert retained_files["v2/presets/sd15.csv"] == expected["v2/presets/sd15.csv"]
assert retained_files["v2/presets/sdxl.csv"] == expected["v2/presets/sdxl.csv"]
receipt = {"status": "PASS_ACTUAL_SERVICE_GVISOR_TEN_OUTPUTS_AND_DELIBERATE_WRONG_WIDTH_CONTROL",
    "authorization": "m_53c64c8643", "session_id": load(HERE / "SESSION.json")["id"],
    "positive_test_id": positive["id"], "negative_test_id": negative["id"],
    "positive_state_sha256": sha(HERE / "POSITIVE_STATE.json"), "negative_state_sha256": sha(HERE / "NEGATIVE_STATE.json"),
    "normal_manifest_sha256": sha(normal_path), "normal_generation_intake_receipt_sha256": sha(ROOT / "coordination/sizefrompresets-generation-result-intake-r1-20261019/VERIFIED_RESULT_RECEIPT.json"),
    "production_definitions_unchanged": 10, "actual_encoder_additive_test_helpers": 2,
    "pngs_every_pixel_checked": pngs, "actual_latent_facts": facts,
    "wrong_answer_control_detected": {"type": error["type"], "message": error["message"], "outputs": 0},
    "preserved_prior_failure": {"test_id": "4c573ebbbcefbb899b1b2f02cf4db25a", "state_sha256": sha(BASE / "POSITIVE_STATE.json"), "reason": "TEST helper awaited a method object; corrected to await latent.value()."},
    "actual_service_requests": {"first_failed_positive": 1, "corrected_positive": 1, "wrong_width_negative": 1},
    "corrected_positive_duration_ms": positive["result"]["duration_ms"], "negative_duration_ms": negative["result"]["duration_ms"],
    "sandbox": "gvisor", "actual_worker_cpu_flag_recorded": True,
    "actual_policy": positive["result"]["policy"],
    "snapshot_scope": "Exact32-file seeded bytes and first-attempt actual ephemeral archive retained. Corrected request differs only in helper value() call. Corrected ephemeral archive retired before copy; no fresh corrected ZIP comparison claimed.",
    "canonical_production_source_changed": False, "models_requested": 0,
    "target_engine_or_managed_general_adoption": False,
    "limits": "This selected service CPU TEST fixture only; no nonCPU or batch>1 service coverage, general runtime/registry/adoption claim. Actual Mac broader in-process case evidence remains separate."}
(HERE / "VERIFIED_SERVICE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": receipt["status"], "receipt_sha256": sha(HERE / "VERIFIED_SERVICE_RECEIPT.json"), "pngs": len(pngs), "latent_fact_records": len(facts), "negative_control": "DETECTED"}))
