"""Data-only exact comparison, including independent wrong-result controls."""
import argparse
import copy
import json
from pathlib import Path


def compare(original, converted, fixture):
    names = {row["id"] for row in fixture["cases"]}
    checks = {"original_completed": original.get("status") == "ORIGINAL_DONE",
              "genuine_SDK_completed": converted.get("status") == "CONVERTED_REAL_SDK_DONE",
              "one_registered_node_each": original.get("registered_count") == converted.get("registered_count") == 1,
              "same_explicit_schema": original.get("schema") == converted.get("schema"),
              "real_extension": converted.get("extension_same_registered_class") is True,
              "all148_case_ids": len(names) == 148 and set(original.get("cases", {})) == set(converted.get("cases", {})) == names}
    for case in fixture["cases"]:
        name = case["id"]
        a, b = original.get("cases", {}).get(name), converted.get("cases", {}).get(name)
        checks[name + ":exact_record"] = a is not None and a == b
        checks[name + ":correct_original_branch"] = bool(a) and a.get("outcome") == ("error" if case["expected_original_error"] else "returned")
        if case["expected_original_error"]:
            checks[name + ":native_overflow"] = bool(a) and a.get("error", {}).get("type") == "OverflowError"
        else:
            checks[name + ":two_integer_outputs"] = bool(a) and a.get("result", {}).get("type") == "tuple" and len(a["result"]["items"]) == 2 and all(v.get("type") == "int" for v in a["result"]["items"])
    return checks


def main():
    parser = argparse.ArgumentParser()
    for name in ("original", "converted", "cases", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    original, converted, fixture = [json.loads(p.read_bytes()) for p in (args.original, args.converted, args.cases)]
    checks = compare(original, converted, fixture)
    controls = []
    for name in ("swap_order", "wrong_rounding", "wrong_scale", "wrong_scalar_type", "wrong_default", "wrong_error"):
        bad = copy.deepcopy(converted)
        if name == "wrong_default":
            target = next(v for v in bad["schema"]["inputs"] if v["id"] == "factor_32px")
            target["attrs"]["default"] = {"type": "bool", "value": False}
        elif name == "wrong_error":
            bad["cases"]["overflow_positive_f0"]["error"]["message"] += " wrong"
        else:
            case_id = {"swap_order": "d07_s0_f0_l0", "wrong_rounding": "d03_s0_f1_l0",
                       "wrong_scale": "d17_s0_f0_l1", "wrong_scalar_type": "d00_s0_f0_l0"}[name]
            result = bad["cases"][case_id]["result"]
            if name == "swap_order":
                result["items"].reverse()
            elif name == "wrong_scalar_type":
                result["items"][0] = {"type": "float", "hex": "0x0.0p+0"}
            else:
                result["items"][0]["decimal"] = str(int(result["items"][0]["decimal"]) + 1)
        controls.append({"name": name, "returned_data_only": True,
                         "detected": not all(compare(original, bad, fixture).values())})
    passed = all(checks.values()) and len(controls) == 6 and all(v["detected"] for v in controls)
    result = {"status": "PASS_SWAP_ORIGINAL_DEFAULT_SDK_ONLY" if passed else "FAILED_COMPARISON",
              "checks": checks, "failed_checks": [k for k, v in checks.items() if not v],
              "algorithm_cases": 148, "positive_cases": 144, "original_error_parity_cases": 4,
              "schema_cases": 1, "controls": controls, "whole_pack_service_or_Guest_acceptance": False}
    body = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    assert len(body) < 1024**2
    args.output.write_bytes(body)
    print(json.dumps({"status": result["status"], "checks": len(checks), "failed_checks": result["failed_checks"],
                      "detected_controls": sum(v["detected"] for v in controls)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
