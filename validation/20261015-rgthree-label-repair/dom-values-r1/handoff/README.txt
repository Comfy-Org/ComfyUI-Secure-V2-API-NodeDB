Generic form-value bridge repair: source regression PASS; browser acceptance pending.

Only ui-renderer.mjs changes:62b5e5ec ->46882ce0. The complete production guest correctly serializes control.value; the old host copied it only as an attribute, which leaves textarea/select live values wrong. The successor restores their .value after sanitized children/options exist. Explicit empty strings, unmatched select values and native markup defaults remain correct. Scripts, unsafe URLs and inline handlers remain rejected.

The actual production guest/host dialog/renderer code was exercised against jsdom29.1.1 DOMParser, elements, events and closed shadow roots.26 checks passed, including2 expected failures of the old source, initial/repeated update hydration and bidirectional value-event transport. The bounded run exited0 without OOM in1.926seconds:1CPU,768MiB container,512MiB Node heap,90-second ceiling,offline,cached dependencies only.

Label63114, guest, host-entry, public declarations and registry package identity are unchanged. No frontend compiler rebuild is required by this one-module delta. Root owns publication; DANNY owns browser/deployment. Real Chromium rendering/keyboard/mouse/save-reload acceptance remains pending. Preserve all then-current selected frontend/login/pack loading assets; do not deploy a whole old dist merely to update this module.
