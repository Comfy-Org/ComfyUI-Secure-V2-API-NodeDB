// LoRA Manager rev 10: guest-shape tolerance shared by the self-registering frontends.
//
// definitionOff: the published comfy-api.d.ts types comfy.defs.extend as returning an Unsubscribe, but the live guest
// (host-stack r3 guest.mjs c6b97a15, lines 578-604) returns a Promise of the host's acknowledgements, and nothing can be
// unregistered there (forwarded to the r4a composer as R6-11). Calling that result threw TypeError in every dispose. Here a
// function result is the real Unsubscribe; anything else yields a no-op, and each caller's own disposed/stopped flag keeps its
// hooks inert after disposal, which is the observable behaviour of unregistering.
//
// canReplaceSerializedValue: on the live guest, widget beforeSerialize events reach the worker without setSerializedValue
// (platform gap G1; the #11 bridge excludes replacement values too). Callers skip the replacement, so the widget's own value
// is serialized, exactly as when no handler is registered.

/** @param {unknown} result what comfy.defs.extend returned */
export function definitionOff(result) {
  if (typeof result === 'function') return result;
  if (result && typeof (/** @type {any} */ (result)).then === 'function') {
    (/** @type {Promise<unknown>} */ (result)).then(undefined, error => {
      console.error('[LoRA Manager] a node definition hook was refused by the host:', error);
    });
  }
  return () => {};
}

/** @param {any} event a beforeSerialize event */
export function canReplaceSerializedValue(event) {
  return !!event && typeof event.setSerializedValue === 'function';
}
