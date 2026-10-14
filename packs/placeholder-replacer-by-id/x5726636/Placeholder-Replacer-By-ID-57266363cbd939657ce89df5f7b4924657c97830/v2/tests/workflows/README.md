# Prepared workflows and actual TEST execution

These 17 JSON files are the original prepared API graphs. Their independent
64x64, batch-one image fixture uses color 2241348 (0x223344). Before execution,
the manager changed that fixture to 1024, as required by the TEST runner, and
combined the 14 positive graphs with unique node IDs. These original files are
retained for provenance; their hashes in `../EXPECTED_RESULTS.json` refer to
these bytes, not to the adjusted or combined submitted graphs.

The five exact submitted requests, including all adjusted fixtures and the
TEST-only producer and observer, are stored at repository-root path
`validation/20261014-placeholder/REQUEST-*.json`. Use those requests to reproduce
the completed run. `EXPECTED_RESULTS.json` binds every prepared case to its
verified job and adjusted fixture hash; `SERVICE_STATE.json` stores the results.

The typed producer sends one INT_LIST value as plain data. The production node
returns three strings to an observer that checks exact types and values against
the native reference. Only after those assertions pass does a real ImageRef
reach PreviewImage. A preview alone is not evidence of correct string outputs.
Unsigned 64-bit values are encoded in JSON strings to avoid JavaScript rounding.

The submitted helpers check schemas with the installed finalized GET_SCHEMA
and compare the actual production class. The original parser is unchanged.
The actual target runtime is Python 3.13. Three verified negative cases cover
an intentionally wrong debug expectation and two native parser errors; each
produced zero preview artifacts. A final valid job verified recovery. The five
jobs cover 17 distinct behavior cases and one recovery, with 15 total previews.
