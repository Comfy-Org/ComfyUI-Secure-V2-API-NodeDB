# Secure conversion evidence

- Upstream: `https://github.com/1038lab/ComfyUI-Mosaic`
- Commit: `54e799b354a465ca9f7ade0421f069b6ff4a6804`
- Backend census: 2 supported, 0 rejected, 0 pending
- Frontend census: 0 supported, 0 rejected, 0 pending
- Routes: 0
- Authority: bounded pack-owned raw IMAGE/MASK computation only

The copied algorithm module remains pack-owned and is exercised differentially
against the pristine implementation. The V2 wrappers add finite resource bounds,
typed schemas, and raw-compute permission without introducing host authority.
