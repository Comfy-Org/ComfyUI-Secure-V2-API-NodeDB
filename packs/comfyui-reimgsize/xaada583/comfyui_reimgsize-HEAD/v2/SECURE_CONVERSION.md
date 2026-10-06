# Reimgsize Secure Nodes V2 conversion

Source: https://github.com/MakkiShizu/comfyui_reimgsize
Pinned commit: `aada583b1f15f572c9737c88e61d528a15021fed` (`xaada583`).

Actual unmocked entrypoint census: **3 Python nodes supported**, 0 rejected,
0 pending; 0 frontend extensions, JS-only nodes or routes. IDs, class names,
display names, category, ordered schemas, optional defaultInput sockets,
and output names/order are preserved. MIT license and example workflows are
included unchanged.

## Architecture and behavior

Dimension and aspect-ratio math stays in this pack. The existing public
`ImageRef.describe()` provides bounded inert shape metadata; `ImageRef.resize()`
uses the host's canonical `comfy.utils.common_upscale`, just as upstream does.
No raw access, private constructors, ambient host imports, filesystem/network,
global mutation or new API is needed. Reimgsize and Cropimg declare only the
existing **inspect** capability for inert shape/channel metadata. Resizebyratio
has **zero permissions**. All use opaque SDK refs; inspect grants no raw buffers.

Reimgsize preserves total-pixel calculation, optional width/height precedence,
intermediate integer truncation and Python banker rounding to GCD multiples.
Cropimg preserves integer aspect crop followed by original-area scaling.
Resizebyratio preserves the independent floating-point ratio formula and may
return zero or large scalar dimensions, just as upstream; it does not allocate
an image. All five ordered interpolation choices and both crop modes remain.

## Bounds and legacy failures

Image inputs/outputs are bounded to batch 32, edge 8192, 4,194,304 total pixels,
and 1/3/4 channels. Parameter bounds follow the existing schemas (scalar size
permits the upstream direct range 1..8192; its widget minimum remains 32).
Noninteger/bool dimensions, nonfinite/out-of-range ratios, unknown methods and
malformed shape metadata fail closed. Computed output bounds are checked
**before broker dispatch**, so a legal UI parameter combination cannot cause
an unbounded batch allocation. These are explicit security constraints beyond
the legacy unbounded direct-call surface, not silent approximation.

Round-to-zero image sizes continue to fail rather than clamp to one; the
conversion raises a bounded validation error rather than reproducing a
vendor-specific interpolation exception message. Degenerate Cropimg integer
crop still raises ZeroDivisionError. Scalar ratio zero results stay intact.
The trusted resize broker separately rejects invalid size/method/crop values
before invoking its allocator; focused tests cover that actual implementation.

## Persistence disposition

**No durable state.** All output derives from explicit inputs. There are no
mutable caches, files, endpoints or user-authored preferences. Fresh copied
pack filesystems and separate confined guest processes for A/B/A tenants are
tested; no durable storage facade is necessary.

## Verification

The focused module is `tests/test_reimgsize_secure_conversion.py`. It covers
schema/census, exact pixels, shape/dtype/order, rounding/optional dimensions,
1,003 scalar-ratio differentials, malformed inputs and allocation bounds,
actual minimal-capability isolated guest dispatch, inspect/raw denial tests,
the public outer executor,
fresh-render statelessness, pinned declarations, pristine file identities,
manifest and byte-exact pristine-to-v2 patch reconstruction.

CPU behavior is exercised against the installed Torch/Pillow/core versions.
GPU placement/performance and Linux confinement are not exercised by the macOS
guest suite. Device behavior is delegated unchanged to the canonical broker;
no CPU conversion is introduced. Different numerical/vendor versions may
change interpolation pixels, equally affecting upstream and the canonical
operation. Frontend testing is not applicable (no frontend).
