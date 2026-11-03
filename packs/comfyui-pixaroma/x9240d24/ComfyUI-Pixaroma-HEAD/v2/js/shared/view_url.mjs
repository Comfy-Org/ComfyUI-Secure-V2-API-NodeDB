// The /view ROUTE for an image COMBO value (core LoadImage's `image` widget).
//
// A combo value can be "cat.png", "Studio1/cat.png" (an input SUBFOLDER) or carry a
// type annotation, "clipspace/clipspace-mask-1.png [input]" / "render.png [output]".
// ComfyUI's /view keeps only the BASENAME of `filename` and takes the folder from
// `subfolder`, so handing it the raw value 404s - or, worse, shows a SAME-NAMED file
// from the input root (image-pickers.md #4, LIVE_BUGS #15, 2026-10-15).
//
// The parsing is the same as js/load_image/api.mjs `splitTypeAnnotation` +
// `splitFilenameSubfolder`. Kept here rather than imported from there because the
// fullscreen editors (Crop, Composer) may depend only on js/framework and js/shared.
//
// Returns a ROUTE (no host, no cache-buster): hand it to pixApiUrl, with any `&t=`
// appended to the route BEFORE that call, never to its result (hosted-urls.md).
export function comboViewRoute(value) {
  const s = String(value ?? "");
  const m = s.match(/^(.*?)\s*\[(input|output|temp)\]\s*$/i);
  const name = (m ? m[1] : s).replace(/\\/g, "/");
  const type = m ? m[2].toLowerCase() : "input";
  const i = name.lastIndexOf("/");
  const subfolder = i < 0 ? "" : name.slice(0, i);
  const filename = i < 0 ? name : name.slice(i + 1);
  return `/view?filename=${encodeURIComponent(filename)}&type=${type}&subfolder=${encodeURIComponent(subfolder)}`;
}
