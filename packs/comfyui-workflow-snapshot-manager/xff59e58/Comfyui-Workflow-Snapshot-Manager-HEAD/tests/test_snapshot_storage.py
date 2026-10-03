import json
import tempfile
import unittest
from pathlib import Path

import snapshot_storage as storage


def make_record(snapshot_id, timestamp=1, **overrides):
    record = {
        "id": snapshot_id,
        "workflowKey": "workflow/example.json",
        "timestamp": timestamp,
        "label": "Auto",
        "source": "auto",
        "locked": False,
        "graphData": {"nodes": [{"id": 1, "type": "Test"}], "links": []},
    }
    record.update(overrides)
    return record


class SnapshotStorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_data_dir = storage._DATA_DIR
        self.old_profiles_dir = storage._PROFILES_DIR
        storage._DATA_DIR = self.tempdir.name
        storage._PROFILES_DIR = str(Path(self.tempdir.name) / "profiles")
        storage._cache.clear()
        storage._cache_warmed.clear()
        storage._profile_cache = None

    def tearDown(self):
        storage._cache.clear()
        storage._cache_warmed.clear()
        storage._profile_cache = None
        storage._DATA_DIR = self.old_data_dir
        storage._PROFILES_DIR = self.old_profiles_dir
        self.tempdir.cleanup()

    def test_put_lists_metadata_and_round_trips_graph(self):
        record = make_record("snap-1")
        storage.put(record)

        listed = storage.get_all_for_workflow(record["workflowKey"])
        self.assertEqual([entry["id"] for entry in listed], ["snap-1"])
        self.assertNotIn("graphData", listed[0])
        self.assertEqual(storage.get_full_record(record["workflowKey"], "snap-1"), record)

        snapshot_files = [path for path in Path(self.tempdir.name).rglob("*.json") if path.is_file()]
        self.assertEqual(len(snapshot_files), 1)
        json.loads(snapshot_files[0].read_text(encoding="utf-8"))

    def test_rejects_invalid_record_and_path_components(self):
        with self.assertRaises(ValueError):
            storage.put(make_record("../escape"))
        with self.assertRaises(ValueError):
            storage.put(make_record("snap-1", graphData={"links": []}))
        with self.assertRaises(ValueError):
            storage.put(make_record("snap-1", source="mystery"))
        with self.assertRaises(ValueError):
            storage.get_full_record("workflow", 123)

    def test_metadata_allowlist_cannot_replace_graph(self):
        record = make_record("snap-1")
        storage.put(record)

        with self.assertRaises(ValueError):
            storage.update_meta(
                record["workflowKey"],
                record["id"],
                {"graphData": {"nodes": []}},
            )

        full = storage.get_full_record(record["workflowKey"], record["id"])
        self.assertEqual(full["graphData"], record["graphData"])
        self.assertTrue(storage.update_meta(
            record["workflowKey"], record["id"], {"notes": "keeper", "locked": True}
        ))
        updated = storage.get_full_record(record["workflowKey"], record["id"])
        self.assertEqual(updated["notes"], "keeper")
        self.assertTrue(updated["locked"])

    def test_prune_preserves_locked_and_keeps_newest_unlocked(self):
        key = "workflow/example.json"
        storage.put(make_record("old", timestamp=1))
        storage.put(make_record("locked", timestamp=2, locked=True))
        storage.put(make_record("new", timestamp=3))

        self.assertEqual(storage.prune(key, 1, source="regular"), 1)
        remaining = {entry["id"] for entry in storage.get_all_for_workflow(key)}
        self.assertEqual(remaining, {"locked", "new"})

    def test_delete_all_keeps_locked_snapshots(self):
        key = "workflow/example.json"
        storage.put(make_record("unlocked", timestamp=1))
        storage.put(make_record("locked", timestamp=2, locked=True))

        self.assertEqual(storage.delete_all_for_workflow(key), {"lockedCount": 1})
        self.assertEqual(
            [entry["id"] for entry in storage.get_all_for_workflow(key)],
            ["locked"],
        )

    def test_profile_accepts_exact_snapshot_refs_and_rejects_bad_shape(self):
        profile = {
            "id": "profile-1",
            "name": "Editing",
            "timestamp": 10,
            "activeWorkflowKey": "workflow/example.json",
            "workflows": [{
                "workflowKey": "workflow/example.json",
                "displayName": "Example",
                "snapshotId": "snap-1",
            }],
        }
        storage.profile_put(profile)
        self.assertEqual(storage.profile_get("profile-1"), profile)

        with self.assertRaises(ValueError):
            storage.profile_put({"id": "bad", "name": "Bad", "timestamp": 1, "workflows": "nope"})


if __name__ == "__main__":
    unittest.main()
