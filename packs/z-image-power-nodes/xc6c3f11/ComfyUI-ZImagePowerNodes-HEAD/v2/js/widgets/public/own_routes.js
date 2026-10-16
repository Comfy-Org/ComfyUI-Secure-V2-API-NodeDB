/**
 * The pack's own backend routes, addressed RELATIVE to the pack's routes:
 * comfy.backend.fetch('zi_power/styles/by_version?v=1.0'). The host adds the
 * pack's namespace, so the pack never spells a base, a leading '/' or another
 * pack's route.
 *
 * The manifest keeps the original declarations ('/zi_power/styles/by_version',
 * '/zi_power/palettes/by_version'). Route v3 serves them at
 * /ext/<namespace>/zi_power/<route>, so the relative paths are
 * 'zi_power/<route>'. The node schemas give the widgets the original endpoint
 * strings ('/zi_power/styles/by_version?v=1.0'); those map to the two relative
 * routes, and any other endpoint is refused without a request.
 */
const OWN_ROUTES = new Set(['zi_power/styles/by_version','zi_power/palettes/by_version']);

/** The relative route (with its query) for an endpoint, or null if it is not one of this pack's routes. */
export function ownRoutePath(endpoint) {
    if (typeof endpoint !== 'string' || !endpoint.trim()) return null;
    let url;
    try { url = new URL(endpoint,'https://pack.invalid/'); }
    catch { return null; }
    if (url.origin !== 'https://pack.invalid' || url.hash) return null;
    const route = url.pathname.slice(1);
    return OWN_ROUTES.has(route) ? route + url.search : null;
}

/** Fetches one of this pack's routes through the host by relative path. */
export function fetchOwnRoute(comfy,endpoint,init) {
    const path = ownRoutePath(endpoint);
    if (!path) return Promise.reject(new Error(`not one of this pack's routes: ${String(endpoint)}`));
    return comfy.backend.fetch(path,init);
}
