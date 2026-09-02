# Secure Nodes V2 conversion

- Upstream: `https://github.com/Derfuu/Derfuu_ComfyUI_ModdedNodes`
- Pinned commit: `d0905bed31249f2bd0814c67585cf4fe3c77c015`
- Release key: `xd0905be`

## Terminal census

Backend: **31 supported, 0 rejected, 0 pending**.

1. `DF_Float` — supported
2. `DF_Integer` — supported
3. `DF_Text` — supported
4. `DF_Text_Box` — supported
5. `DF_DynamicPrompts_Text_Box` — supported
6. `DF_String_Concatenate` — supported
7. `DF_String_Replace` — supported
8. `DF_Search_In_Text` — supported
9. `DF_To_text_(Debug)` — supported
10. `DF_Random` — supported
11. `DF_Int_to_Float` — supported
12. `DF_Ceil` — supported
13. `DF_Floor` — supported
14. `DF_Absolute_value` — supported
15. `DF_Get_latent_size` — supported
16. `DF_Get_image_size` — supported
17. `DF_Sum` — supported
18. `DF_Subtract` — supported
19. `DF_Multiply` — supported
20. `DF_Divide` — supported
21. `DF_Power` — supported
22. `DF_Square_root` — supported
23. `DF_Sinus` — supported
24. `DF_Cosines` — supported
25. `DF_Tangent` — supported
26. `DF_Logic_node` — supported
27. `DF_Latent_Scale_by_ratio` — supported
28. `DF_Latent_Scale_to_side` — supported
29. `DF_Image_scale_by_ratio` — supported
30. `DF_Image_scale_to_side` — supported
31. `DF_Conditioning_area_scale_by_ratio` — supported

Frontend: **1 supported, 0 rejected, 0 pending**.

1. `derfuu.Debug.ShowDataText` — supported through the typed definition and
   widget lifecycle facade in `scripts/debugNode.js`.

## Security and compatibility boundary

The 24 scalar, string, random, converter, math, trigonometry, and logic nodes
have no permissions. The two size probes use typed `ImageRef` and `LatentRef`
shape operations and likewise need no raw access. Only the debug materializer,
four scale nodes, and conditioning metadata transform declare `raw`; each
returns the corresponding typed ref. The resize implementation is pack-side,
bounded, and matches the pinned `common_upscale` algorithms, including center
crop, bislerp, and Lanczos.

The frontend imports only `/comfy/api/v2.js`, has no parent-window or ambient
DOM access, and creates its read-only textarea through a host-owned widget.
There is no filesystem, network, subprocess, package-install, model-load,
credential, host-mutation, vendor, dependency, hardware, or shared-API gap.

One V1 dispatch defect is repaired without changing its public schema:
`DF_Absolute_value` declared the input `negative_out` but its method accepted
`Get_negative`, so keyword execution failed. V2 honors the declared input and
the documented positive/negative behavior. An empty strict search pattern is
also treated as absent instead of entering V1's non-advancing loop.
