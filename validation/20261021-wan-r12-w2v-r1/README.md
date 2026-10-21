# WAN r12 wav2vec exists-first validation (publication r12)

H1 (`v2/secure_download_wav2vec_runtime.py` 54eaa42e -> 54f18030, diff cfd3818a): DownloadAndLoadWav2VecModel asks assets.exists for
its pinned weight first and requests models.download only when it is absent, as the original's os.path.exists check does.

One selected attempt (m_500f9302b4) of packet wan-r12-w2v-r1 (28c64aed, CONFIG 3367d8d6) ran two sequential bounded Linux
containers on WSL CPU (image e48accf7, one thread, uid/gid 1000, no capabilities, no network, read-only root, memory = swap = 6
GiB). The converted side counted assets.exists calls and refused the download verb with the live text (harness seams); the
original side counted snapshot_download calls.

COMPARISON 795cd51d (exact): loader 34/34, absent 18/18, control 14/14 and embeds 23/23. INTAKE_REVIEW.json (29 checks)
recomputed every comparison file byte-equal. HASH_BINDING.json binds the evidence to the H1 bytes, which equal the staged file.

Live: DownloadAndLoadWav2VecModel works on live only once the operator stages the pinned weights; absent weights still ask for models.download, which live refuses.
