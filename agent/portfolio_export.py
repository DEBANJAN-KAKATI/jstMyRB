"""
Public-safe portfolio export + "Publish to Portfolio".

The export is built from an allow-list: only the fields named below ever leave
the vault. It never contains the phone number, tracker/CRM data, cover letters,
settings or API keys, vault versions, or items marked "visibility": "private".
Email and GPA are included only when switched on in settings.

Bullets written by the rule-based GitHub fallback or by tier padding (invented
metrics such as "99.9% uptime") are removed bullet by bullet, and whole items
flagged "bullets_source": "template" are left out until edited.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from path_utils import get_writable_dir

LAST_PUBLISH_PATH = os.path.join(get_writable_dir("data"), "portfolio_last_publish.json")
EXPORT_PATH_IN_REPO = "data/vault.public.json"
SCHEMA_VERSION = 1

# Must stay in sync with TEMPLATE_BULLETS in the portfolio's src/data/adapters/jstmyrb.js
TEMPLATE_PATTERNS = [
    r"^Engineered an enterprise-grade .+ system for ",
    r"reducing computational overhead by ~35% across stress tests",
    r"accelerating deployment cycle by 2\+ weeks",
    r"^Engineered production deployment pipeline with continuous benchmarking\.?$",
    r"^Deployed modular microservices with comprehensive automated testing\.?$",
    r"^Architected end-to-end system for .+, optimizing latency and throughput\.?$",
    r"^Led core initiatives at .+, boosting operational speed\.?$",
    r"^Engineered end-to-end data pipelines for executive analytics\.?$",
    r"^Automated reporting workflows saving 50%\+ engineering bandwidth\.?$",
    r"^Engineered an end-to-end \S+ solution for .+, ensuring modular architecture and high test coverage\.?$",
    r"^Implemented core algorithmic logic integrating \S+, optimizing throughput and runtime performance under production workloads\.?$",
]
_TEMPLATE_RX = [re.compile(p, re.IGNORECASE) for p in TEMPLATE_PATTERNS]
_TAG_RX = re.compile(r"<[^>]*>")

# Optional per-item fields the portfolio understands (section 11A step 2).
ITEM_COMMON = [
    "id", "tags", "visibility", "featured", "thumbnail", "images", "demo_url", "video_url", "model_url",
    "start_date", "end_date", "updated_at",
]
FIELDS = {
    "education": ["institution", "degree", "duration", "gpa", "location", *ITEM_COMMON],
    "experiences": ["role", "company", "duration", "location", "bullets", "points_tier", "selected_tier", *ITEM_COMMON],
    "projects": ["title", "context", "bullets", "points_tier", "selected_tier", "github_url", "repo_hint", *ITEM_COMMON],
    "patents_certifications": ["type", "title", "details", "url", "image", "date", *ITEM_COMMON],
    "pors_achievements": ["title", "details", "url", "image", "date", *ITEM_COMMON],
    "awards_medals": ["title", "details", "url", "image", "date", *ITEM_COMMON],
    "testimonials": ["id", "author", "headline", "relationship", "text", "date", "approved"],
}
SECTIONS = list(FIELDS.keys())


def is_template_bullet(html: str) -> bool:
    text = _TAG_RX.sub("", html or "").strip()
    return any(rx.search(text) for rx in _TEMPLATE_RX)


def _real(bullets: Any) -> List[str]:
    return [b for b in (bullets or []) if isinstance(b, str) and b.strip() and not is_template_bullet(b)]


def _without_template_bullets(item: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(item)
    if "bullets" in out:
        out["bullets"] = _real(out.get("bullets"))
    if isinstance(out.get("points_tier"), dict):
        out["points_tier"] = {k: _real(v) for k, v in out["points_tier"].items()}
    return out


def _has_bullets(item: Dict[str, Any]) -> bool:
    tiers = item.get("points_tier") or {}
    return bool(item.get("bullets")) or any(tiers.values())


def _pick(item: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: item[k] for k in keys if k in item and item[k] is not None}


def _infer_github_url(project: Dict[str, Any], github_profile: Optional[str]) -> Dict[str, Any]:
    """'Open Source System | GitHub: QR-Chat' -> https://github.com/<user>/QR-Chat"""
    if project.get("github_url") or not github_profile:
        return project
    m = re.search(r"GitHub:\s*([A-Za-z0-9._-]+)", project.get("context") or "")
    if not m:
        return project
    return {**project, "github_url": f"{github_profile.rstrip('/')}/{m.group(1)}"}


def build_public_export(profile: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    settings = settings or {}
    show_email = bool(settings.get("portfolio_show_email", False))
    show_gpa = bool(settings.get("portfolio_show_gpa", True))
    p = profile.get("personal_info") or {}
    meta_in = profile.get("_meta") or {}

    def section(name: str, items: List[Any], clean: bool = False) -> List[Dict[str, Any]]:
        out = []
        for item in items or []:
            if not isinstance(item, dict) or item.get("visibility") == "private":
                continue
            if clean:
                if item.get("bullets_source") == "template":
                    continue
                item = _without_template_bullets(item)
            out.append(_pick(item, FIELDS[name]))
        return out

    projects = [
        _infer_github_url(pr, p.get("github"))
        for pr in (profile.get("projects") or [])
        if isinstance(pr, dict)
    ]
    projects = [pr for pr in section("projects", projects, clean=True) if _has_bullets(pr) or pr.get("github_url") or pr.get("repo_hint")]

    education = section("education", profile.get("education"))
    for e in education:
        e["gpa"] = e.get("gpa") if show_gpa and e.get("gpa") else None

    meta = {"source": "jstMyRB", "schema_version": SCHEMA_VERSION, "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    if meta_in.get("linkedin_imported_at"):
        meta["linkedin_imported_at"] = meta_in["linkedin_imported_at"]

    return {
        "meta": meta,
        "personal_info": {
            "name": p.get("name") or "",
            "email": p.get("email") if show_email else None,
            "linkedin": p.get("linkedin"),
            "github": p.get("github"),
            "location": p.get("location"),
        },
        "education": education,
        "coursework": profile.get("coursework") or {},
        "skills": profile.get("skills") or {},
        "experiences": section("experiences", profile.get("experiences"), clean=True),
        "projects": projects,
        "patents_certifications": section("patents_certifications", profile.get("patents_certifications")),
        "pors_achievements": section("pors_achievements", profile.get("pors_achievements")),
        "awards_medals": section("awards_medals", profile.get("awards_medals")),
        "testimonials": section("testimonials", [t for t in (profile.get("testimonials") or []) if isinstance(t, dict) and t.get("approved")]),
    }


def export_report(profile: Dict[str, Any]) -> Dict[str, int]:
    """What the allow-list removes, so nothing disappears silently."""
    template = private = 0
    for key in ("projects", "experiences"):
        for item in profile.get(key) or []:
            if not isinstance(item, dict):
                continue
            seen = set(item.get("bullets") or [])
            for tier in (item.get("points_tier") or {}).values():
                seen.update(tier or [])
            template += sum(1 for b in seen if isinstance(b, str) and is_template_bullet(b))
    for key in SECTIONS:
        private += sum(1 for i in profile.get(key) or [] if isinstance(i, dict) and i.get("visibility") == "private")
    return {"template_bullets_removed": template, "private_items_excluded": private}


def _key(item: Dict[str, Any]) -> str:
    return str(item.get("id") or item.get("title") or item.get("institution") or item.get("author") or "")


def _label(section: str, item: Dict[str, Any]) -> str:
    if section == "experiences":
        return f"{item.get('role', '')} @ {item.get('company', '')}"
    return str(item.get("title") or item.get("institution") or item.get("author") or item.get("id") or "")


def diff_exports(old: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Added / updated / removed items per section since the last publish."""
    added, updated, removed = [], [], []
    for section in SECTIONS:
        before = {_key(i): i for i in ((old or {}).get(section) or [])}
        after = {_key(i): i for i in (new.get(section) or [])}
        for k, item in after.items():
            if k not in before:
                added.append({"section": section, "title": _label(section, item)})
            elif json.dumps(before[k], sort_keys=True) != json.dumps(item, sort_keys=True):
                updated.append({"section": section, "title": _label(section, item)})
        for k, item in before.items():
            if k not in after:
                removed.append({"section": section, "title": _label(section, item)})
    for key in ("skills", "coursework", "personal_info"):
        if json.dumps((old or {}).get(key), sort_keys=True) != json.dumps(new.get(key), sort_keys=True) and old:
            updated.append({"section": key, "title": key.replace("_", " ").title()})
    return {"added": added, "updated": updated, "removed": removed}


def load_last_publish() -> Optional[Dict[str, Any]]:
    try:
        with open(LAST_PUBLISH_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_last_publish(export: Dict[str, Any]) -> None:
    with open(LAST_PUBLISH_PATH, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)


class PublishError(Exception):
    pass


def _github(method: str, url: str, token: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jstMyRB-portfolio-publish",
            **({"Content-Type": "application/json"} if data else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return json.loads(res.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 404 and method == "GET":
            return {}
        detail = e.read().decode("utf-8", "replace")[:300]
        hint = {401: "the token is invalid or expired", 403: "the token lacks Contents: write on this repo", 404: "repo or branch not found (or the token can't see it)"}.get(e.code, "")
        raise PublishError(f"GitHub HTTP {e.code}{': ' + hint if hint else ''}. {detail}") from e
    except urllib.error.URLError as e:
        raise PublishError(f"Couldn't reach GitHub: {e.reason}") from e


def publish_to_github(export: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, str]:
    """Commit data/vault.public.json to the portfolio repo via the GitHub Contents API."""
    repo = (settings.get("portfolio_repo") or "").strip()
    branch = (settings.get("portfolio_branch") or "main").strip()
    token = settings.get("portfolio_github_token") or ""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise PublishError("Set the portfolio repository as owner/name first.")
    if not token:
        raise PublishError("Add a fine-grained GitHub token (Contents: read & write on the portfolio repo only).")

    url = f"https://api.github.com/repos/{repo}/contents/{EXPORT_PATH_IN_REPO}"
    current = _github("GET", f"{url}?ref={branch}", token)
    content = json.dumps(export, indent=2, ensure_ascii=False) + "\n"
    stamp = export["meta"]["exported_at"][:16].replace("T", " ")
    body = {
        "message": f"Publish vault from jstMyRB ({stamp} UTC)",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
        **({"sha": current["sha"]} if current.get("sha") else {}),
    }
    result = _github("PUT", url, token, body)
    save_last_publish(export)
    commit = result.get("commit") or {}
    return {"commit_url": commit.get("html_url", ""), "sha": commit.get("sha", "")}
