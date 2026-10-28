"""Run with: python -m unittest discover -s tests"""
import io
import json
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.portfolio_export import build_public_export, diff_exports, export_report, is_template_bullet  # noqa: E402
from agent.linkedin_export import LinkedInImportError, apply_items, build_preview, parse_linkedin_zip  # noqa: E402

TEMPLATE = "Engineered an enterprise-grade Python system for <b>X</b>, achieving <b>99.9% uptime</b> and sub-second processing latency."
PADDING = "Engineered production deployment pipeline with continuous benchmarking."


def vault():
    return {
        "personal_info": {"name": "Test", "email": "me@x.com", "phone": "+91 99999", "github": "https://github.com/u", "linkedin": "https://linkedin.com/in/u"},
        "education": [{"institution": "BITS", "degree": "B.E.", "duration": "2023 – 2027", "gpa": "9.1"}],
        "skills": {"programming": ["Python (NumPy, Pandas)", "C++"]},
        "coursework": {},
        "experiences": [
            {"id": "e1", "role": "Intern", "company": "Shell", "duration": "May 2026 – Jul 2026", "bullets": ["Real work."], "secret_notes": "x"},
            {"id": "e2", "role": "Ghost", "company": "Hidden", "bullets": ["x"], "visibility": "private"},
        ],
        "projects": [
            {"id": "p1", "title": "Real", "context": "GitHub: real-repo", "bullets": ["Good.", PADDING], "points_tier": {"1": ["Good."], "3": ["Good.", PADDING]}},
            {"id": "p2", "title": "Auto", "context": "Open Source System | GitHub: auto", "bullets": [TEMPLATE], "points_tier": {"1": [TEMPLATE]}},
            {"id": "p3", "title": "Flagged", "bullets": ["fine"], "bullets_source": "template"},
            {"id": "p4", "title": "Nothing", "bullets": [PADDING]},
        ],
        "patents_certifications": [], "pors_achievements": [], "awards_medals": [],
        "testimonials": [{"id": "t1", "author": "A", "text": "great", "approved": True}, {"id": "t2", "author": "B", "text": "meh", "approved": False}],
        "tracker": [{"company": "secret"}],
        "cover_letters": ["secret letter"],
    }


class ExportTests(unittest.TestCase):
    def test_privacy_allow_list(self):
        out = build_public_export(vault(), {})
        s = json.dumps(out)
        for leaked in ("99999", "me@x.com", "secret", "Hidden", "secret_notes"):
            self.assertNotIn(leaked, s)
        self.assertEqual(set(out.keys()), {"meta", "personal_info", "education", "coursework", "skills", "experiences", "projects",
                                           "patents_certifications", "pors_achievements", "awards_medals", "testimonials"})
        self.assertEqual([t["id"] for t in out["testimonials"]], ["t1"])
        self.assertEqual(out["education"][0]["gpa"], "9.1")

    def test_toggles(self):
        out = build_public_export(vault(), {"portfolio_show_email": True, "portfolio_show_gpa": False})
        self.assertEqual(out["personal_info"]["email"], "me@x.com")
        self.assertIsNone(out["education"][0]["gpa"])

    def test_template_bullets(self):
        self.assertTrue(is_template_bullet(TEMPLATE))
        self.assertTrue(is_template_bullet(PADDING))
        self.assertFalse(is_template_bullet("Built rate-limit governors guaranteeing 99.9% query uptime."))
        out = build_public_export(vault(), {})
        by_id = {p["id"]: p for p in out["projects"]}
        self.assertEqual(by_id["p1"]["points_tier"]["3"], ["Good."])
        self.assertEqual(by_id["p1"]["github_url"], "https://github.com/u/real-repo")
        # template-only project survives (GitHub will describe it) with no bullets
        self.assertEqual(by_id["p2"]["bullets"], [])
        self.assertEqual(by_id["p2"]["github_url"], "https://github.com/u/auto")
        self.assertNotIn("p3", by_id)  # flagged whole item
        self.assertNotIn("p4", by_id)  # nothing real and no repo
        # p1 padding + p2 template + p4 padding
        self.assertEqual(export_report(vault())["template_bullets_removed"], 3)

    def test_diff(self):
        a = build_public_export(vault(), {})
        b = json.loads(json.dumps(a))
        b["projects"][0]["title"] = "Renamed"
        b["projects"].append({"id": "p9", "title": "New one"})
        b["experiences"] = []
        d = diff_exports(a, b)
        self.assertEqual([x["title"] for x in d["added"]], ["New one"])
        self.assertEqual([x["title"] for x in d["updated"]], ["Renamed"])
        self.assertEqual([x["title"] for x in d["removed"]], ["Intern @ Shell"])
        self.assertTrue(all(x["section"] for x in d["added"] + d["updated"] + d["removed"]))


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


LINKEDIN = {
    "Basic_LinkedInDataExport/Positions.csv": "Company Name,Title,Description,Location,Started On,Finished On\n"
    "Shell Technology Centre,Intern,\"Built a platform.\nAutomated reports.\",Bengaluru,May 2026,Jul 2026\n"
    "Acme Corp,Analyst,Did analysis.,Remote,Jan 2024,\n",
    "Skills.csv": "﻿Name\nPython\nKubernetes\n",
    "Education.csv": "School Name,Start Date,End Date,Notes,Degree Name,Activities\nBITS,2023,2028,,B.E.,\n",
    "Recommendations_Received.csv": "First Name,Last Name,Company,Job Title,Text,Creation Date,Status\nJane,Doe,Shell,Manager,Great <b>work</b>.,06/12/26,VISIBLE\n",
    "Honors.csv": "Title,Description,Issued On\nGold Medal,Ranked first,Mar 2022\n",
}


class LinkedInTests(unittest.TestCase):
    def test_parse_and_preview(self):
        rows = parse_linkedin_zip(make_zip(LINKEDIN))
        self.assertEqual(len(rows["positions"]), 2)
        self.assertEqual(rows["skills"][0]["Name"], "Python")
        items = build_preview(rows, vault())
        by_label = {i["label"]: i for i in items}
        intern = by_label["Intern @ Shell Technology Centre"]  # matched: company contains "Shell"
        self.assertEqual(intern["status"], "changed")
        self.assertEqual(intern["changes"]["location"], ["", "Bengaluru"])
        self.assertEqual(by_label["Analyst @ Acme Corp"]["status"], "new")
        self.assertEqual(by_label["Analyst @ Acme Corp"]["incoming"]["duration"], "Jan 2024 – Present")
        self.assertEqual(by_label["Python"]["status"], "duplicate")  # inside "Python (NumPy, Pandas)"
        self.assertEqual(by_label["Kubernetes"]["status"], "new")
        self.assertEqual(by_label["BITS"]["status"], "changed")
        self.assertEqual(by_label["Gold Medal"]["status"], "new")
        rec = by_label["Recommendation from Jane Doe"]
        self.assertTrue(rec["incoming"]["approved"])

    def test_apply_only_accepted(self):
        v = vault()
        items = build_preview(parse_linkedin_zip(make_zip(LINKEDIN)), v)
        keys = [i["key"] for i in items if i["label"] in ("Analyst @ Acme Corp", "Kubernetes", "BITS", "Python")]
        _, counts = apply_items(v, items, keys)
        self.assertEqual(counts, {"added": 2, "updated": 1})  # Python is a duplicate: ignored
        self.assertIn("Kubernetes", v["skills"]["linkedin_imported"])
        self.assertEqual(v["education"][0]["duration"], "2023 – 2028")
        self.assertEqual(len(v["experiences"]), 3)
        self.assertIn("linkedin_imported_at", v["_meta"])
        # descriptions are escaped before they become bullets (only <b> is markup in the vault)
        self.assertNotIn("<", json.dumps([e["bullets"] for e in v["experiences"]][2]))

    def test_bad_upload(self):
        with self.assertRaises(LinkedInImportError):
            parse_linkedin_zip(b"not a zip")
        with self.assertRaises(LinkedInImportError):
            parse_linkedin_zip(make_zip({"Connections.csv": "x"}))


if __name__ == "__main__":
    unittest.main()
