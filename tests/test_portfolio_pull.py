"""Run with: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.portfolio_pull import apply_pull, build_pull_preview, item_key, remove_entries, sanitize, slugify  # noqa: E402


def vault():
    return {
        "skills": {"programming": ["Python", "C++"]},
        "experiences": [{"id": "e1", "role": "Intern", "company": "Shell", "duration": "2026", "bullets": ["Old."], "updated_at": "2026-10-01T00:00:00Z"}],
        "projects": [
            {"id": "p1", "title": "Real", "bullets": ["One."], "points_tier": {"1": ["One."], "2": ["One.", "Two."], "3": ["One.", "Two.", "Three."]}, "selected_tier": "2", "updated_at": "2026-10-01T00:00:00Z", "bullets_source": "template"},
            {"title": "No Id Project", "bullets": ["x"]},
        ],
        "education": [],
        "patents_certifications": [],
        "pors_achievements": [],
        "awards_medals": [],
    }


def tiers(*b):
    return {"1": list(b[:1]), "2": list(b[:2]), "3": list(b)}


class PullPreviewTests(unittest.TestCase):
    def test_slug_matches_portfolio(self):
        self.assertEqual(slugify("JalProloy — Flood Early Warning!"), "jalproloy_flood_early_warning")
        self.assertEqual(item_key({"title": "No Id Project"}), "no_id_project")

    def test_statuses(self):
        inbox = {"items": [
            {"op": "add", "section": "projects", "id": "proj_dm_new", "data": {"title": "New", "points_tier": tiers("A.")}, "edited_at": "2026-10-30T00:00:00Z"},
            {"op": "edit", "section": "projects", "id": "p1", "data": {"title": "Real", "points_tier": tiers("Better.", "Two.")}, "base_updated_at": "2026-10-01T00:00:00Z", "edited_at": "2026-10-30T00:00:00Z"},
            {"op": "edit", "section": "experiences", "id": "e1", "data": {"role": "Intern", "company": "Shell", "duration": "2026", "bullets": ["Old."]}, "base_updated_at": "2026-10-01T00:00:00Z"},
            {"op": "delete", "section": "projects", "id": "no_id_project"},
            {"op": "add", "section": "skills", "id": "ai_ml", "data": {"category": "ai_ml", "skills": ["PyTorch"]}},
            {"op": "edit", "section": "settings", "id": "x", "data": {}},  # unknown section: ignored
        ]}
        rows = {r["key"]: r for r in build_pull_preview(inbox, vault())}
        self.assertEqual(rows["projects:proj_dm_new"]["status"], "new")
        self.assertEqual(rows["projects:p1"]["status"], "update")
        self.assertIn("points_tier", rows["projects:p1"]["changes"])
        self.assertEqual(rows["experiences:e1"]["status"], "unchanged")
        self.assertEqual(rows["projects:no_id_project"]["status"], "delete")
        self.assertEqual(rows["skills:ai_ml"]["status"], "new")
        self.assertNotIn("settings:x", rows)

    def test_conflict_when_vault_edited_after_base(self):
        profile = vault()
        profile["projects"][0]["updated_at"] = "2026-10-29T00:00:00Z"
        inbox = {"items": [{"op": "edit", "section": "projects", "id": "p1", "data": {"title": "Renamed"}, "base_updated_at": "2026-10-01T00:00:00Z", "edited_at": "2026-10-30T00:00:00Z"}]}
        [row] = build_pull_preview(inbox, profile)
        self.assertEqual(row["status"], "conflict")
        # Conflicts are skipped unless a choice is made.
        counts, resolved = apply_pull(profile, [row], {})
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(resolved, [])
        self.assertEqual(profile["projects"][0]["title"], "Real")
        # Keeping the vault version still clears the entry later.
        counts, resolved = apply_pull(profile, [row], {row["key"]: "vault"})
        self.assertEqual((counts["kept"], len(resolved)), (1, 1))
        self.assertEqual(profile["projects"][0]["title"], "Real")

    def test_sanitize_strips_unknown_fields_and_markup(self):
        data = sanitize("projects", {
            "title": "<script>x</script>Hi",
            "phone": "+91",
            "points_tier": {"1": ["<b>Fast</b> <img src=x onerror=1>app & more"]},
            "tags": ["ai_ml", {"bad": 1}],
        })
        self.assertNotIn("phone", data)
        self.assertEqual(data["title"], "xHi")
        self.assertEqual(data["points_tier"]["1"], ["<b>Fast</b> app &amp; more"])
        self.assertEqual(data["tags"], ["ai_ml"])
        self.assertEqual(sanitize("projects", {"title": "&lt;img src=x onerror=alert(1)&gt;Hi"})["title"], "Hi")


class PullApplyTests(unittest.TestCase):
    def test_apply_add_edit_delete_skills(self):
        profile = vault()
        inbox = {"items": [
            {"op": "add", "section": "projects", "id": "proj_dm_new", "data": {"title": "New", "points_tier": tiers("A.", "B.")}, "edited_at": "2026-10-30T00:00:00Z"},
            {"op": "edit", "section": "projects", "id": "p1", "data": {"points_tier": tiers("Better.", "Two.")}, "base_updated_at": "2026-10-01T00:00:00Z"},
            {"op": "delete", "section": "projects", "id": "no_id_project"},
            {"op": "add", "section": "skills", "id": "ai_ml", "data": {"category": "ai_ml", "skills": ["PyTorch"]}},
        ]}
        rows = build_pull_preview(inbox, profile)
        counts, resolved = apply_pull(profile, rows, {})
        self.assertEqual((counts["added"], counts["updated"], counts["deleted"]), (2, 1, 1))
        self.assertEqual(len(resolved), 4)
        titles = [p["title"] for p in profile["projects"]]
        self.assertEqual(titles, ["New", "Real"])
        new, real = profile["projects"]
        self.assertEqual(new["bullets"], ["A.", "B."])  # selected tier 2
        self.assertTrue(new["updated_at"])
        self.assertEqual(real["bullets"], ["Better.", "Two."])
        self.assertEqual(real["bullets_source"], "manual")  # edited, no longer template
        self.assertNotEqual(real["updated_at"], "2026-10-01T00:00:00Z")
        self.assertEqual(profile["skills"]["ai_ml"], ["PyTorch"])

    def test_unchecked_items_are_skipped(self):
        profile = vault()
        inbox = {"items": [{"op": "add", "section": "projects", "id": "proj_x", "data": {"title": "X", "points_tier": tiers("A.")}}]}
        rows = build_pull_preview(inbox, profile)
        counts, resolved = apply_pull(profile, rows, {"projects:proj_x": "skip"})
        self.assertEqual((counts["skipped"], resolved, len(profile["projects"])), (1, [], 2))


class InboxClearTests(unittest.TestCase):
    def test_remove_only_pulled_entries(self):
        inbox = {"version": 1, "items": [
            {"op": "edit", "section": "projects", "id": "p1", "edited_at": "2026-10-30T00:00:00Z"},
            {"op": "edit", "section": "projects", "id": "p2", "edited_at": "2026-10-31T09:00:00Z"},  # edited again after the pull
            {"op": "add", "section": "projects", "id": "p3", "edited_at": "2026-10-30T00:00:00Z"},  # never pulled
        ]}
        pulled = [
            {"section": "projects", "id": "p1", "edited_at": "2026-10-30T00:00:00Z"},
            {"section": "projects", "id": "p2", "edited_at": "2026-10-30T00:00:00Z"},
        ]
        updated, removed = remove_entries(inbox, pulled)
        self.assertEqual(removed, 1)
        self.assertEqual([i["id"] for i in updated["items"]], ["p2", "p3"])


if __name__ == "__main__":
    unittest.main()
