import { comfy } from '/comfy/api/v2.js';

// The original's display table is empty for every language — DISPLAY() falls
// straight through to the key — so translation here is an identity function
// today, and converting it is a matter of dropping the legacy `app` read.
//
// This file was previously punted whole for one function's gap. That took
// ue_properties.js, ue_properties_editor.js and floating_window.js down with
// it: they import names from here, which is a link error at load rather than a
// parse error. A gap in get_functional() is not a reason to break four files.

export var REPEATED_TYPE_OPTIONS;
export var GROUP_RESTRICTION_OPTIONS;
export var COLOR_RESTRICTION_OPTIONS;

var _FUNCTIONAL = null;
var _FUNCTIONAL_REGEX = null;

const toTitleCase = (phrase) =>
    phrase.toLowerCase().split(' ')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

export function i18n(v, extras) {
    return extras?.titlecase ? toTitleCase(v) : v;
}

export function language_changed() {
    _FUNCTIONAL = null;
    _FUNCTIONAL_REGEX = null;

    REPEATED_TYPE_OPTIONS = [
        i18n("Exact match of input names"),
        i18n("Match start of input names"),
        i18n("Match end of input names"),
        i18n("Inputs matches target node name"),
        i18n("Regex match of input names"),
    ];
    GROUP_RESTRICTION_OPTIONS = [
        i18n("No restrictions"),
        i18n("Send only within group"),
        i18n("Send only outside group"),
    ];
    COLOR_RESTRICTION_OPTIONS = [
        i18n("No restrictions"),
        i18n("Send only to same color"),
        i18n("Send only to different color"),
    ];
}
language_changed();

comfy.settings.onChange('Comfy.Locale', () => language_changed());

function get_functional() {
    const localized = (name) => {
        const def = comfy.defs.get('KSampler');
        const input = def?.inputs.find((i) => i.name === name);
        return input?.localizedName || name;
    };
    const seed = localized('seed');
    const positive = localized('positive');
    const negative = localized('negative');
    _FUNCTIONAL = {
        seed_input_regex : `seed|${seed}`,
        prompt_regex     : `(_|\\b)pos(itive|_|\\b)|${positive}`,
        negative_regex   : `(_|\\b)neg(ative|_|\\b)|${negative}`,
        seed, positive, negative,
    };
}

function get_functional_regex() {
    if (!_FUNCTIONAL) get_functional();
    _FUNCTIONAL_REGEX = {
        prompt_regex   : new RegExp(_FUNCTIONAL.prompt_regex),
        negative_regex : new RegExp(_FUNCTIONAL.negative_regex),
    };
}

export function i18n_functional(v) {
    if (!_FUNCTIONAL) get_functional();
    return _FUNCTIONAL?.[v] || v;
}

export function i18n_functional_regex(v) {
    if (!_FUNCTIONAL_REGEX) get_functional_regex();
    return _FUNCTIONAL_REGEX[v];
}

export function i18ify_settings(settings) {
    settings.forEach((s) => {
        if (s.name)    s.name    = i18n(s.name);
        if (s.tooltip) s.tooltip = i18n(s.tooltip);
        if (s.options) s.options.forEach((o) => { o.text = i18n(o.text) });
    });
    return settings;
}
