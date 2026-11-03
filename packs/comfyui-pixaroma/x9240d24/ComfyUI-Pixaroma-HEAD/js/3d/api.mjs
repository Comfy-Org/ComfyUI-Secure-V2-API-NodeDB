// Pixaroma 3D — API helpers
//
// NOTE: do NOT wrap these routes in pixApiUrl(). `api.fetchApi` already calls
// `api.apiURL()` on the route it is given, and apiURL is NOT idempotent when
// ComfyUI is served under a sub-path:
//
//   apiURL(e) = e.startsWith("/api") ? api_base + e : api_base + "/api" + e
//
// With api_base "" (localhost) a double wrap is a silent no-op, which is why it
// tests clean. With api_base "/comfy" (a reverse proxy serving ComfyUI at
// https://host/comfy/) the second pass no longer sees a leading "/api" and
// prefixes again:  /comfy/api/comfy/api/pixaroma/api/3d/save  -> 404.
// pixApiUrl is for URLs we hand to fetch/import/img.src OURSELVES, not for
// routes passed to fetchApi.
import { api } from "../../../scripts/api.js";

export class ThreeDAPI {
  static async saveRender(projectId, dataURL) {
    const res = await api.fetchApi("/pixaroma/api/3d/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, image_merged: dataURL }),
    });
    return res.json();
  }

  static async uploadBgImage(projectId, dataURL) {
    const res = await api.fetchApi("/pixaroma/api/3d/bg_upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, image: dataURL }),
    });
    return res.json();
  }

  // Upload a user-supplied 3D model file (GLB / GLTF / OBJ) as a
  // base64 data URL. Backend hashes contents, stores under
  // input/pixaroma/<project>/models/, and returns { status, path }
  // where `path` is the `pixaroma/...` subfolder-relative URL suitable
  // for /view?type=input&subfolder=...&filename=...
  static async uploadModel(projectId, filename, dataURL) {
    const res = await api.fetchApi("/pixaroma/api/3d/model_upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        filename,
        data: dataURL,
      }),
    });
    // The backend route is registered at server start; if ComfyUI was
    // running when this plugin was updated the route may not exist yet
    // (HTTP 405 "Method Not Allowed") and the response body will be a
    // non-JSON error page. Surface a friendly message in that case
    // instead of letting res.json() throw "Unexpected non-whitespace
    // character after JSON" deep in the import pipeline.
    if (!res.ok) {
      if (res.status === 405 || res.status === 404) {
        return {
          status: "error",
          msg: "Backend route not registered — restart ComfyUI to load the new model-upload endpoint.",
        };
      }
      return { status: "error", msg: `HTTP ${res.status}` };
    }
    try {
      return await res.json();
    } catch {
      return { status: "error", msg: "Invalid JSON response from server" };
    }
  }
}
