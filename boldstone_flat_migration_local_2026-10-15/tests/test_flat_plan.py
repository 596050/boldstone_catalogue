from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("flat_check", BASE / "tools" / "check_flat_plan.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def make_snapshot(plan, source_ids, files):
    original = {r["id"]: r for r in plan["folders"]}
    by_path = {m.path_key(r["source_relative"]): r for r in plan["folders"]}
    wanted = set(source_ids)
    for fid in list(source_ids):
        path = original[fid]["source_relative"]
        parts = path.split("/")
        for end in range(1, len(parts)):
            wanted.add(by_path[m.path_key("/".join(parts[:end]))]["id"])
    folders = []
    for fid in sorted(wanted):
        row = original[fid]; path = row["source_relative"]
        parent_path = path.rsplit("/", 1)[0] if "/" in path else ""
        pid = by_path[m.path_key(parent_path)]["id"] if parent_path else "id:test-root"
        folders.append(dict(id=fid, parent_id=pid, relative_path=path, name=path.split("/")[-1]))
    outfiles = []
    for fid, pid, name in files:
        outfiles.append(dict(id=fid, parent_id=pid, name=name,
                             relative_path=original[pid]["source_relative"] + "/" + name,
                             rev="test-rev", size=3, content_hash="a" * 64, media_kind="image"))
    return dict(schema="boldstone-flat-snapshot-v1", account_id="test-account", root_id="id:test-root",
                observed_at_utc="2026-10-15T00:00:00Z", complete=True, has_more=False,
                folders=folders, files=outfiles)


class FlatPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.plan = m.load_plan(BASE)

    def test_source_checksums(self):
        self.assertEqual(m.package_validation(BASE)["original_checksum_entries_verified"], 14)

    def test_exact_counts(self):
        p=self.plan
        self.assertEqual((len(p["rows"]),len(p["folders"]),len(p["targets"])), (425,422,347))

    def test_three_family_ids_intentionally_have_direct_file_rules(self):
        overlaps=set(self.plan["family_controls"]) & set(self.plan["direct_routes"])
        self.assertEqual(len(overlaps),3)
        self.assertEqual({self.plan["direct_routes"][x]["action"] for x in overlaps},{"ROOT-FILE HOLDING PROPOSAL"})

    def test_exact_63_family_specs(self):
        self.assertEqual(len(list((BASE/"rules"/"families").glob("*.json"))),63)

    def test_exact_74_review_leaves(self):
        self.assertEqual(sum(t["review"]=="True" for t in self.plan["targets"]),74)

    def test_all_targets_two_components(self):
        for t in self.plan["targets"]: m.validate_relative(t["target_relative"],2)

    def test_no_daggers_in_actual_names(self):
        self.assertTrue(all("†" not in t["target_name"] for t in self.plan["targets"]))

    def test_decision_template_not_preapproved(self):
        rows=m.load_csv(BASE/"decisions"/"Folder_Decisions_TEMPLATE.csv")
        self.assertEqual(len(rows),347)
        self.assertEqual({x["decision"] for x in rows},{"PENDING"})

    def test_snapshot_must_be_complete(self):
        s=make_snapshot(self.plan,["id:cnqzTNngPVsAAAAAAAyh8g"],[]);s["has_more"]=True
        with self.assertRaises(ValueError): m.check_snapshot(s)

    def test_ancestry_validation(self):
        pid="id:cnqzTNngPVsAAAAAAAyh8g"
        s=make_snapshot(self.plan,[pid],[("id:test",pid,"x.jpg")]);s["files"][0]["parent_id"]="id:unknown"
        with self.assertRaises(ValueError):m.check_snapshot(s)

    def test_ids_not_case_folded(self):
        a="id:cnqzTNngPVsAAAAAAAyh8g"
        self.assertIn(a,self.plan["direct_routes"])
        self.assertNotIn(a.lower(),self.plan["direct_routes"])

    def test_reject_traversal_and_nested_leaf(self):
        for bad in ["A/../B","A/B/C","/A/B","A/B†","A/B\\C","A/B:","A/B "]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):m.validate_relative(bad,2)

    def test_duplicate_snapshot_ids_rejected(self):
        pid="id:cnqzTNngPVsAAAAAAAyh8g"
        s=make_snapshot(self.plan,[pid],[("id:same",pid,"x.jpg"),("id:same",pid,"y.jpg")])
        with self.assertRaises(ValueError):m.check_snapshot(s)

    def test_case_insensitive_collision_rejected_in_snapshot(self):
        pid="id:cnqzTNngPVsAAAAAAAyh8g"
        s=make_snapshot(self.plan,[pid],[("id:a",pid,"X.jpg"),("id:b",pid,"x.jpg")])
        with self.assertRaises(ValueError):m.check_snapshot(s)

    def test_nested_fingerprint_uses_own_route(self):
        parent="id:cnqzTNngPVsAAAAAAAyhHw";child="id:cnqzTNngPVsAAAAAAAyhOw"
        s=make_snapshot(self.plan,[parent,child],[("id:p",parent,"p.jpg"),("id:c",child,"c.jpg")])
        r=m.route_preview(self.plan,s)
        self.assertEqual(r[0]["proposed_relative"],"Fingerprint/Fingerprint Verdigris/p.jpg")
        self.assertEqual(r[1]["proposed_relative"],"Fingerprint/Fingerprint 1 Verdigris/c.jpg")

    def test_wrapper_direct_file_is_held(self):
        pid="id:cnqzTNngPVsAAAAAAAs74Q"
        r=m.route_preview(self.plan,make_snapshot(self.plan,[pid],[("id:t",pid,"x.jpg")]))[0]
        self.assertIn("UNEXPECTED_DIRECT_FILE_IN_WRAPPER",r["holds"])
        self.assertEqual(r["proposed_relative"],"")

    def test_video_needs_external_approval(self):
        pid="id:cnqzTNngPVsAAAAAAA5RBg"
        r=m.route_preview(self.plan,make_snapshot(self.plan,[pid],[("id:t",pid,"x.mp4")]))[0]
        self.assertIn("EXTERNAL_ROUTE_REQUIRES_APPROVAL",r["holds"])

    def test_unmapped_new_child_does_not_inherit_family_rule(self):
        pid="id:cnqzTNngPVsAAAAAAAydIw"
        s=make_snapshot(self.plan,[pid],[])
        s["folders"].append(dict(id="id:newchild",parent_id=pid,name="New",relative_path="Collection Together/New"))
        s["files"].append(dict(id="id:t",parent_id="id:newchild",name="x.jpg",relative_path="Collection Together/New/x.jpg"))
        self.assertEqual(m.route_preview(self.plan,s)[0]["preview_status"],"UNALLOCATED_IMMEDIATE_PARENT")

    def test_family_root_direct_file_rule(self):
        pid="id:cnqzTNngPVsAAAAAAAydIw"
        r=m.route_preview(self.plan,make_snapshot(self.plan,[pid],[("id:t",pid,"x.jpg")]))[0]
        self.assertEqual(r["proposed_relative"],"Collection Together/Mixed Sculptures Unclassified/x.jpg")

    def test_provisional_cannot_use_source_label_approval(self):
        pid="id:cnqzTNngPVsAAAAAAAyhOw"
        s=make_snapshot(self.plan,[pid],[("id:t",pid,"x.jpg")])
        r=m.route_preview(self.plan,s,{"Fingerprint/Fingerprint 1 Verdigris":"APPROVE_SOURCE_LABEL_ROUTING"})[0]
        self.assertIn("PROVISIONAL_STORAGE_DECISION_REQUIRED",r["holds"])

    def test_provisional_storage_not_a_live_execution_approval(self):
        pid="id:cnqzTNngPVsAAAAAAAyhOw"
        s=make_snapshot(self.plan,[pid],[("id:t",pid,"x.jpg")])
        r=m.route_preview(self.plan,s,{"Fingerprint/Fingerprint 1 Verdigris":"APPROVE_PROVISIONAL_STORAGE"})[0]
        self.assertNotIn("PROVISIONAL_STORAGE_DECISION_REQUIRED",r["holds"])
        self.assertFalse(r["executable"])

    def test_nonimage_held_not_discarded(self):
        pid="id:cnqzTNngPVsAAAAAAAyh8g"
        s=make_snapshot(self.plan,[pid],[("id:t",pid,"x.txt")]);s["files"][0]["media_kind"]="other"
        r=m.route_preview(self.plan,s)[0]
        self.assertIn("NON_IMAGE_OR_UNVERIFIED_TYPE",r["holds"])

    def test_missing_content_hash_held(self):
        pid="id:cnqzTNngPVsAAAAAAAyh8g"
        s=make_snapshot(self.plan,[pid],[("id:t",pid,"x.jpg")]);s["files"][0]["content_hash"]=""
        self.assertIn("CONTENT_METADATA_INCOMPLETE",m.route_preview(self.plan,s)[0]["holds"])

    def test_pooling_collision_preserves_two_rows(self):
        a="id:cnqzTNngPVsAAAAAAAylkg";b="id:cnqzTNngPVsAAAAAAAylkw"
        s=make_snapshot(self.plan,[a,b],[("id:a",a,"same.jpg"),("id:b",b,"same.jpg")])
        r=m.route_preview(self.plan,s)
        self.assertEqual(len(r),2)
        self.assertTrue(all("MULTIPLE_FILES_REQUEST_SAME_DESTINATION" in x["holds"] for x in r))
        self.assertTrue(all(not x["executable"] for x in r))

    def test_same_id_at_target_not_a_move(self):
        pid="id:cnqzTNngPVsAAAAAAAyh8g"
        r=m.route_preview(self.plan,make_snapshot(self.plan,[pid],[("id:t",pid,"x.jpg")]))[0]
        self.assertEqual(r["preview_status"],"ALREADY_AT_PROPOSED_TARGET")

    def test_historical_hold_scope_preserved_for_new_move(self):
        pid="id:cnqzTNngPVsAAAAAAAylkg"
        s=make_snapshot(self.plan,[pid],[("id:held",pid,"x.jpg")])
        r=m.route_preview(self.plan,s,held_ids={"id:held"})[0]
        self.assertIn("HISTORICAL_HOLD_SCOPE_REQUIRES_REVIEW",r["holds"])

    def test_schema_compiles_and_events_are_immutable(self):
        db=sqlite3.connect(":memory:")
        db.executescript((BASE/"spec"/"STATE_SCHEMA.sql").read_text())
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",("r","a","root","{}","digest","now",None,"OPEN"))
        db.execute("INSERT INTO events(event_id,run_id,recorded_utc,event_type,payload_json) VALUES ('e','r','now','TEST','{}')")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("DELETE FROM events")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE events SET event_type='CHANGED'")
        db.close()

    def test_config_defaults_disable_mutations(self):
        c=json.loads((BASE/"spec"/"CONFIG.example.json").read_text())
        self.assertEqual(c["mode"],"READ_ONLY")
        self.assertFalse(c["allow_file_deletion"])
        self.assertFalse(c["allow_image_conversion"])
        self.assertFalse(c["allow_ownership_transfer"])
        self.assertIsNone(c["account_id"])


if __name__ == "__main__":unittest.main()
