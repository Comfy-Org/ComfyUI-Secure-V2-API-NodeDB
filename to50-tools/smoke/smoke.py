import sys, os, json, platform
sys.path[:0] = ["/core", "/overlay"]
out = {"python": platform.python_version()}
try:
    import torch; out["torch"] = torch.__version__
except Exception as e: out["torch"] = "ERR " + repr(e)
try:
    import comfy_api.latest as L; out["comfy_api"] = getattr(L, "__file__", "?")
except Exception as e: out["comfy_api"] = "ERR " + repr(e)
try:
    from comfy_secure_nodes import packmanifest, packpatch; out["overlay"] = [packmanifest.__file__, packpatch.__file__]
except Exception as e: out["overlay"] = "ERR " + repr(e)
out["bases"] = sorted(os.listdir("/bases"))[:10]
out["pack_ls"] = sorted(os.listdir("/pack"))[:5]
json.dump(out, open("/results/smoke.json", "w"), indent=1); print(json.dumps(out))
