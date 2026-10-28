"""
Import LinkedIn's official data export (Settings → Data privacy → Get a copy of
your data). LinkedIn's API doesn't expose your own positions/skills without
partner approval and scraping breaks their terms, so the zip is the source.

parse_linkedin_zip()  zip bytes -> raw rows per CSV
build_preview()       rows + vault -> items marked new / changed / duplicate
apply_items()         merges the accepted items into the vault
"""
import csv
import io
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

FILES = {
    "positions": "positions.csv",
    "skills": "skills.csv",
    "education": "education.csv",
    "certifications": "certifications.csv",
    "projects": "projects.csv",
    "honors": "honors.csv",
    "recommendations": "recommendations_received.csv",
}
# A column each file must have, used to find the header row (some exports start with notes).
HEADER_HINT = {
    "positions": "Company Name",
    "skills": "Name",
    "education": "School Name",
    "certifications": "Name",
    "projects": "Title",
    "honors": "Title",
    "recommendations": "Text",
}
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_CSV_BYTES = 5 * 1024 * 1024
LINKEDIN_SKILL_CATEGORY = "linkedin_imported"


class LinkedInImportError(Exception):
    pass


def _read_csv(text: str, hint: str) -> List[Dict[str, str]]:
    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, line in enumerate(lines) if hint in line), None)
    if start is None:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def parse_linkedin_zip(data: bytes) -> Dict[str, List[Dict[str, str]]]:
    if len(data) > MAX_ZIP_BYTES:
        raise LinkedInImportError("That file is larger than 50 MB; LinkedIn's basic export is much smaller.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise LinkedInImportError("That isn't a zip file. Upload the .zip LinkedIn emails you.") from e
    by_name = {}
    for info in zf.infolist():
        base = info.filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if base.endswith(".csv") and info.file_size <= MAX_CSV_BYTES:
            by_name.setdefault(base, info)
    rows = {}
    for key, fname in FILES.items():
        info = by_name.get(fname)
        if not info:
            rows[key] = []
            continue
        raw = zf.read(info)
        text = raw.decode("utf-8-sig", errors="replace")
        rows[key] = _read_csv(text, HEADER_HINT[key])
    if not any(rows.values()):
        raise LinkedInImportError("No LinkedIn CSVs found (expected Positions.csv, Skills.csv, …).")
    return rows


# ---------------------------------------------------------------- helpers

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:50]


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(value: str) -> str:
    """LinkedIn dates look like 'Jan 2024', '2024', '06/2024' or '2024-06-01'."""
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%b %Y", "%Y", "%m/%Y", "%Y-%m-%d", "%m/%d/%y", "%d %b %Y"):
        try:
            d = datetime.strptime(value, fmt)
            return str(d.year) if fmt == "%Y" else f"{_MONTHS[d.month - 1]} {d.year}"
        except ValueError:
            continue
    return value


def _duration(start: str, end: str) -> str:
    s, e = _fmt_date(start), _fmt_date(end)
    if s and e:
        return f"{s} – {e}"
    if s:
        return f"{s} – Present"
    return e


def _sentences(text: str, limit: int = 3) -> List[str]:
    """LinkedIn descriptions are free text: use lines/bullets, else sentences."""
    text = (text or "").strip()
    if not text:
        return []
    parts = [re.sub(r"^[\s•\-–*·]+", "", p).strip() for p in re.split(r"\n+", text)]
    parts = [p for p in parts if len(p) > 3]
    if len(parts) <= 1:
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 3]
    return parts[:limit]


def _tiers(bullets: List[str]) -> Dict[str, List[str]]:
    return {"1": bullets[:1], "2": bullets[:2], "3": bullets[:3]}


def _html_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _find(items: List[Dict[str, Any]], pred) -> Optional[Dict[str, Any]]:
    return next((i for i in items if isinstance(i, dict) and pred(i)), None)


def _company_match(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    return bool(na and nb) and (na == nb or na in nb or nb in na)


# ---------------------------------------------------------------- preview

def build_preview(rows: Dict[str, List[Dict[str, str]]], vault: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Every importable item, each with:
      key, section, status ('new' | 'changed' | 'duplicate'), label, detail,
      incoming (vault-shaped data), existing_id, changes ({field: [old, new]})
    """
    items: List[Dict[str, Any]] = []

    def add(section, status, label, detail, incoming, existing=None, changes=None):
        items.append({
            "key": f"{section}:{len(items)}",
            "section": section,
            "status": status,
            "label": label,
            "detail": detail,
            "incoming": incoming,
            "existing_id": (existing or {}).get("id") or (existing or {}).get("title") or (existing or {}).get("institution"),
            "changes": changes or {},
        })

    def compare(existing, incoming, fields) -> Dict[str, List[str]]:
        return {f: [existing.get(f) or "", incoming[f]] for f in fields if incoming.get(f) and (existing.get(f) or "") != incoming[f]}

    # Positions -> experiences (matched by company + role)
    for r in rows.get("positions", []):
        company, role = r.get("Company Name", ""), r.get("Title", "")
        if not company or not role:
            continue
        bullets = [_html_escape(b) for b in _sentences(r.get("Description", ""))]
        incoming = {
            "id": f"exp_li_{_slug(company)}_{_slug(role)}"[:60],
            "role": role,
            "company": company,
            "duration": _duration(r.get("Started On", ""), r.get("Finished On", "")),
            "location": r.get("Location", ""),
            "tags": [],
            "bullets": bullets[:2],
            "points_tier": _tiers(bullets),
            "selected_tier": "2",
        }
        existing = _find(vault.get("experiences", []), lambda e: _company_match(e.get("company", ""), company) and (_norm(e.get("role", "")) == _norm(role) or _norm(role) in _norm(e.get("role", ""))))
        if not existing:
            add("experiences", "new", f"{role} @ {company}", incoming["duration"], incoming)
        else:
            changes = compare(existing, incoming, ["duration", "location"])
            add("experiences", "changed" if changes else "duplicate", f"{role} @ {company}", incoming["duration"], incoming, existing, changes)

    # Skills -> a "linkedin_imported" category (skills already anywhere in the vault are duplicates)
    known = {_norm(s) for cat in (vault.get("skills") or {}).values() for s in cat}
    known_tokens = {_norm(tok) for cat in (vault.get("skills") or {}).values() for s in cat for tok in re.split(r"[,/()]", s) if tok.strip()}
    for r in rows.get("skills", []):
        name = r.get("Name", "")
        if not name:
            continue
        dup = _norm(name) in known or _norm(name) in known_tokens
        add("skills", "duplicate" if dup else "new", name, "Skill", {"category": LINKEDIN_SKILL_CATEGORY, "skill": name})

    # Education (matched by school)
    for r in rows.get("education", []):
        school = r.get("School Name", "")
        if not school:
            continue
        incoming = {
            "institution": school,
            "degree": r.get("Degree Name", "") or r.get("Notes", ""),
            "duration": _duration(r.get("Start Date", ""), r.get("End Date", "")),
            "gpa": "",
            "location": "",
        }
        existing = _find(vault.get("education", []), lambda e: _company_match(e.get("institution", ""), school))
        if not existing:
            add("education", "new", school, incoming["degree"], incoming)
        else:
            changes = compare(existing, incoming, ["degree", "duration"])
            add("education", "changed" if changes else "duplicate", school, incoming["degree"], incoming, existing, changes)

    # Certifications -> patents_certifications (matched by title)
    for r in rows.get("certifications", []):
        name = r.get("Name", "")
        if not name:
            continue
        authority = r.get("Authority", "")
        year = _fmt_date(r.get("Started On", ""))
        incoming = {"type": "Certification", "title": name, "details": " · ".join(x for x in [authority, year] if x), "url": r.get("Url") or None, "tags": []}
        existing = _find(vault.get("patents_certifications", []), lambda c: _norm(c.get("title", "")) == _norm(name))
        add("patents_certifications", "duplicate" if existing else "new", name, incoming["details"], incoming, existing)

    # Projects (matched by title)
    for r in rows.get("projects", []):
        title = r.get("Title", "")
        if not title:
            continue
        bullets = [_html_escape(b) for b in _sentences(r.get("Description", ""))]
        url = r.get("Url", "")
        incoming = {
            "id": f"proj_li_{_slug(title)}",
            "title": title,
            "context": "LinkedIn project",
            "tags": [],
            "bullets": bullets[:2],
            "points_tier": _tiers(bullets),
            "selected_tier": "2",
            **({"github_url": url} if "github.com/" in url else {}),
            **({"demo_url": url} if url and "github.com/" not in url else {}),
        }
        existing = _find(vault.get("projects", []), lambda p: _norm(p.get("title", "")) == _norm(title))
        add("projects", "duplicate" if existing else "new", title, _duration(r.get("Started On", ""), r.get("Finished On", "")), incoming, existing)

    # Honors -> awards_medals (matched by title)
    for r in rows.get("honors", []):
        title = r.get("Title", "")
        if not title:
            continue
        issued = _fmt_date(r.get("Issued On", ""))
        details = " · ".join(x for x in [_html_escape(r.get("Description", "")), issued] if x)
        existing = _find(vault.get("awards_medals", []), lambda a: _norm(a.get("title", "")) == _norm(title))
        add("awards_medals", "duplicate" if existing else "new", title, details, {"title": title, "details": details, "tags": []}, existing)

    # Recommendations -> testimonials. Accepting one approves it for the portfolio.
    for r in rows.get("recommendations", []):
        text = r.get("Text", "")
        if not text or (r.get("Status", "VISIBLE").upper() not in ("VISIBLE", "")):
            continue
        author = f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip() or "LinkedIn member"
        rid = f"rec_li_{_slug(author)}_{_slug(r.get('Creation Date', ''))}"[:60]
        incoming = {
            "id": rid,
            "author": author,
            "headline": " · ".join(x for x in [r.get("Job Title", ""), r.get("Company", "")] if x) or None,
            "relationship": None,
            "text": text,
            "date": r.get("Creation Date") or None,
            "approved": True,
        }
        existing = _find(vault.get("testimonials", []), lambda t: t.get("id") == rid)
        add("testimonials", "duplicate" if existing else "new", f"Recommendation from {author}", text[:120], incoming, existing)

    return items


# ---------------------------------------------------------------- apply

def apply_items(vault: Dict[str, Any], items: List[Dict[str, Any]], accepted_keys: List[str]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Merge accepted preview items into the vault (in place). Duplicates are never applied."""
    accepted = set(accepted_keys)
    counts = {"added": 0, "updated": 0}
    for it in items:
        if it["key"] not in accepted or it["status"] == "duplicate":
            continue
        section, data = it["section"], dict(it["incoming"])
        if section == "skills":
            cat = vault.setdefault("skills", {}).setdefault(data["category"], [])
            if data["skill"] not in cat:
                cat.append(data["skill"])
                counts["added"] += 1
            continue
        lst = vault.setdefault(section, [])
        if it["status"] == "new":
            lst.append(data)
            counts["added"] += 1
        elif it["status"] == "changed":
            target = _find(lst, lambda x: (x.get("id") or x.get("title") or x.get("institution")) == it["existing_id"])
            if target:
                for field, (_, new_value) in it["changes"].items():
                    target[field] = new_value
                counts["updated"] += 1
    if counts["added"] or counts["updated"]:
        vault.setdefault("_meta", {})["linkedin_imported_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return vault, counts
