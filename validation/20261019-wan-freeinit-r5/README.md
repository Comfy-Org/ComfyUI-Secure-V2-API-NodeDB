# WAN FreeInit revision 5 validation

The only runtime change from revision 4 removes `freeinit_args` from the tuple
of refused sampler arguments. The existing 53 FreeInit checks are retained.
The normal node declaration and every other runtime byte remain unchanged;
unrun scheduler UI work is excluded. Counts remain 124 tested, 17 untested,
6 partial across 147 original nodes, with 146 declared node IDs.

The first actual normal-generation attempt failed because the real deferred
schema import needed accelerate. That failure remains recorded. The isolated
repair added the genuine cached accelerate 1.10.1 wheel, 96 files, with no
existing file changed/deleted. Actual import, installed RECORD and requirements
were checked. The unchanged second attempt passed all five canonical commands
and both replays. SDK/Core/backend and other pinned dependencies stayed fixed.

After that run only the conversion report's source-note paragraph changed.
The official final JSON/diff and bundle were regenerated and both replays
passed on all 785 source files with genuine POSIX0644 modes. The derived ZIP
is not committed. `CORPUS_INGEST.json` identifies exact source bytes and Git
modes; it does not supply an installation or readiness grant.

This is a bounded source revision with its stated prior behavioral evidence.
No new model, Guest, full-pack or deployment qualification is claimed. The
normal registry source cut and active runtime installation remain separate.
