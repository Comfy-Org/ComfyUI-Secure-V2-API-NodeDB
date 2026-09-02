# Audio General third-party notices

The external, content-addressed dependency profile is
`0efe9730e960e77448c0bf7500a8fc24a98f572e5ddde629fc43cd21f92957de`.
Its Python 3.13 / `macosx-11.0-arm64` target selects lock
`40bc18f0bf4c986fc1c9b6abec7c2506c054fc236f04591e6666d35f24112e3c`
with 26 exact wheels.

Twenty-five wheels embed their own license/notice payloads. The conversion
test binds the exact filenames to the content-addressed wheelhouse, including
the third-party files in llvmlite and numba, the Apache NOTICE in requests,
and all bundled LGPL/component/source-compliance material in soundfile and
soxr. Those files remain in the installed external dependency layer.

`primePy==1.3` is the sole exception: its wheel has an MIT classifier but no
license file. The exact upstream MIT text is retained here as
`primePy-1.3-LICENSE.txt`. Upstream published no Git tag. The pinned primary
source is commit `ee9cc1666bdd6e1e2984ad10d307213e481c937b` in
<https://github.com/janaindrajit/primePy>; it is the 2018-05-29 merge that
introduced the MIT license before the 1.3 PyPI upload later that day. The
retained license bytes have SHA-256
`1a06a1576544095ade4508462bc6c795c874a499e2abe12d21557e85a3741d9e`.
