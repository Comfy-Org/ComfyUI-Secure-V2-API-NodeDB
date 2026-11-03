"""The marker a V2 ClownsharKSampler_Beta output latent carries in place of the original's state_info.

The original attaches the loop's whole state to both output latents (beta/samplers.py:1009-1010). A V2 latent carries
{"node": "ClownsharKSampler_Beta", "denoised": <the loop's final denoised estimate>} under CHAIN_KEY: the one entry a
converted consumer reads in standard mode (LatentUpscaleWithVAE, helper_sigma_preview_image_preproc.py:658-666).
Core's nodes copy or drop it exactly as they copy or drop the original's state_info entry
(tests/test_chain_key_core.py). Kept in its own module so that the image-side nodes need not import the sampler.
"""
CHAIN_KEY = "res4lyf_v2_chain"

__all__ = ["CHAIN_KEY"]
