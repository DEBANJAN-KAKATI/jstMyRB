"""
"Pull from Portfolio": bring Dev Mode edits back into the vault.

The portfolio's Dev Mode never edits the published vault export. It appends
operations to data/vault.inbox.json in the portfolio repo:

    {"version": 1, "items": [{"op": "add"|"edit"|"delete", "section": "projects",
      "id": "...", "data": {...}, "base_updated_at": "...", "edited_at": "..."}]}

Here they are previewed against the vault (new / update / delete / conflict),
applied with the owner's choice for each conflict, and remembered so the next
"Publish to Portfolio" removes exactly those entries from the inbox. An entry
edited again on the portfolio after the pull has a newer edited_at and stays.
"""
import base64
import html
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from path_utils import get_writable_dir
from agent.portfolio_export import FIELDS, PublishError, _github

INBOX_PATH_IN_REPO = "data/vault.inbox.json"
PULLED_PATH = os.path.join(get_writable_dir("data"), "portfolio_pulled.json")

LIST_SECTIONS = ["projects", "experiences", "education", "patents_certifications", "pors_achievements", "awards_medals"]
SECTIONS = [*LIST_SECTIONS, "skills"]
# Fields that are compared / shown in the preview (bookkeeping fields are ignored).
IGNORED = {"id", "updated_at", "selected_tier"}
_TAG_RX = re.compile(r"<[^>]*>")
_ALLOWED_TAG_RX = re.compile(r"</?(b|strong)>", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def slugify(text: Any) -> str:
    """Same as slugify() in the portfolio's src/data/adapters/jstmyrb.js."""
    s = unicodedata.normalize("NFKD", str(text or "").lower())
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60]


def item_key(item: Dict[str, Any]) -> str:
    """How the portfolio identifies a vault item: its id, else a slug of its title."""
    return str(item.get("id") or slugify(item.get("title") or item.get("institution")))


def _clean_html(value: str) -> str:
    """Bullets may keep <b>/<strong>; every other tag is dropped and text is escaped."""
    parts, last = [], 0
    for m in _ALLOWED_TAG_RX.finditer(value):
        parts.append(html.escape(html.unescape(_TAG_RX.sub("", value[last:m.start()])), quote=False))
        parts.append(m.group(0).lower().replace("strong", "b"))
        last = m.end()
    parts.append(html.escape(html.unescape(_TAG_RX.sub("", value[last:])), quote=False))
    return "".join(parts)


def _clean_text(value: Any) -> Any:
    if isinstance(value, str):
        # Unescape first so "&lt;img …&gt;" can't turn back into markup afterwards.
        return _TAG_RX.sub("", html.unescape(value)).replace("<", "").replace(">", "").strip()
    return value


def sanitize(section: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only fields the vault knows for this section; strip markup."""
    if section == "skills":
        skills = data.get("skills") if isinstance(data.get("skills"), list) else []
        return {"category": _clean_text(data.get("category") or ""), "skills": [_clean_text(s) for s in skills if isinstance(s, str) and s.strip()]}
    out: Dict[str, Any] = {}
    for k in FIELDS.get(section, []):
        if k == "id" or k not in data:
            continue
        v = data[k]
        if k == "bullets" and isinstance(v, list):
            v = [_clean_html(b) for b in v if isinstance(b, str)]
        elif k == "points_tier" and isinstance(v, dict):
            v = {t: [_clean_html(b) for b in (v.get(t) or []) if isinstance(b, str)] for t in ("1", "2", "3")}
        elif k == "details" and isinstance(v, str):
            v = _clean_html(v)
        elif isinstance(v, list):
            v = [_clean_text(x) for x in v if isinstance(x, (str, int, float))]
        elif isinstance(v, (str, int, float, bool)) or v is None:
            v = _clean_text(v)
        else:
            continue
        out[k] = v
    return out


def _label(section: str, item: Dict[str, Any], fallback: str) -> str:
    if section == "skills":
        return str(item.get("category") or fallback)
    if section == "experiences":
        return f"{item.get('role', '')} @ {item.get('company', '')}".strip(" @") or fallback
    return str(item.get("title") or item.get("institution") or fallback)


def _short(v: Any) -> str:
    if isinstance(v, dict):
        v = v.get("3") or v.get("2") or v.get("1") or []
    if isinstance(v, list):
        v = "; ".join(_TAG_RX.sub("", str(x)) for x in v)
    s = _TAG_RX.sub("", str(v if v is not None else ""))
    return s if len(s) <= 140 else s[:137] + "…"


def _find(profile: Dict[str, Any], section: str, entry_id: str) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    if section == "skills":
        skills = profile.get("skills") or {}
        for k, v in skills.items():
            if k == entry_id or k.lower() == entry_id.lower():
                return None, {"category": k, "skills": list(v or [])}
        return None, None
    for i, item in enumerate(profile.get(section) or []):
        if isinstance(item, dict) and item_key(item) == entry_id:
            return i, item
    return None, None


def _newer(a: Optional[str], b: Optional[str]) -> bool:
    """Is timestamp a later than b? Missing values never count as newer."""
    if not a or not b:
        return False
    try:
        pa = datetime.fromisoformat(a.replace("Z", "+00:00"))
        pb = datetime.fromisoformat(b.replace("Z", "+00:00"))
        if pa.tzinfo is None:
            pa = pa.replace(tzinfo=timezone.utc)
        if pb.tzinfo is None:
            pb = pb.replace(tzinfo=timezone.utc)
        return pa > pb
    except ValueError:
        return a > b


def build_pull_preview(inbox: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One row per inbox entry: what pulling it would do to the vault."""
    rows = []
    for entry in (inbox or {}).get("items") or []:
        if not isinstance(entry, dict):
            continue
        section, op, entry_id = entry.get("section"), entry.get("op"), str(entry.get("id") or "")
        if section not in SECTIONS or op not in ("add", "edit", "delete") or not entry_id:
            continue
        data = sanitize(section, entry.get("data") or {}) if op != "delete" else {}
        _, current = _find(profile, section, entry_id)
        row = {
            "key": f"{section}:{entry_id}",
            "section": section,
            "op": op,
            "id": entry_id,
            "label": _label(section, data or current or {}, entry_id),
            "edited_at": entry.get("edited_at"),
            "data": data,
            "changes": {},
        }
        if op == "delete":
            row["status"] = "delete" if current else "unchanged"
        elif current is None:
            row["status"] = "new"
        else:
            changes = {
                k: [_short(current.get(k)), _short(v)]
                for k, v in data.items()
                if k not in IGNORED and json.dumps(current.get(k), sort_keys=True) != json.dumps(v, sort_keys=True)
            }
            row["changes"] = changes
            row["status"] = "update" if changes else "unchanged"
        # Edited in the vault after the portfolio edit was based on it?
        vault_at = (current or {}).get("updated_at")
        base = entry.get("base_updated_at")
        if current is not None and row["status"] in ("update", "delete") and (_newer(vault_at, base) or (not base and _newer(vault_at, entry.get("edited_at")))):
            row["status"] = "conflict"
            row["vault_updated_at"] = vault_at
        rows.append(row)
    return rows


def _apply_one(profile: Dict[str, Any], row: Dict[str, Any], stamp: str) -> bool:
    section, entry_id, data = row["section"], row["id"], row["data"]
    if section == "skills":
        skills = profile.setdefault("skills", {})
        _, current = _find(profile, "skills", entry_id)
        key = (current or {}).get("category") or data.get("category") or entry_id
        if row["op"] == "delete":
            return skills.pop(key, None) is not None
        skills[key] = data.get("skills") or []
        return True

    items = profile.setdefault(section, [])
    idx, current = _find(profile, section, entry_id)
    if row["op"] == "delete":
        if idx is None:
            return False
        items.pop(idx)
        return True
    if current is None:
        item = {"id": entry_id, **data, "updated_at": stamp, "bullets_source": "portfolio"} if "points_tier" in data or "bullets" in data else {"id": entry_id, **data, "updated_at": stamp}
        if "points_tier" in item:
            item.setdefault("selected_tier", "2")
            item["bullets"] = item["points_tier"].get(item["selected_tier"]) or item.get("bullets") or []
        items.insert(0, item)
        return True
    current.update(data)
    current["id"] = current.get("id") or entry_id
    current["updated_at"] = stamp
    if ("bullets" in data or "points_tier" in data) and current.get("bullets_source") == "template":
        current["bullets_source"] = "manual"
    tier = str(current.get("selected_tier") or "2")
    if isinstance(current.get("points_tier"), dict) and current["points_tier"].get(tier):
        current["bullets"] = current["points_tier"][tier]
    return True


def apply_pull(profile: Dict[str, Any], rows: List[Dict[str, Any]], choices: Dict[str, str]) -> Tuple[Dict[str, int], List[Dict[str, str]]]:
    """
    choices: key -> "portfolio" (take the portfolio's version), "vault" (keep the
    vault's; the entry is still cleared on publish) or "skip" (leave it in the inbox).
    Rows not mentioned default to "portfolio", except conflicts, which default to "skip".
    Returns counts and the entries to clear from the inbox on the next publish.
    """
    stamp = now_iso()
    counts = {"added": 0, "updated": 0, "deleted": 0, "kept": 0, "skipped": 0}
    resolved = []
    for row in rows:
        choice = choices.get(row["key"], "skip" if row["status"] == "conflict" else "portfolio")
        if choice == "skip":
            counts["skipped"] += 1
            continue
        if choice == "vault" or row["status"] == "unchanged":
            counts["kept"] += 1
        elif _apply_one(profile, row, stamp):
            counts[{"add": "added", "edit": "updated", "delete": "deleted"}[row["op"]] if row["status"] != "new" else "added"] += 1
        resolved.append({"section": row["section"], "id": row["id"], "edited_at": row.get("edited_at")})
    return counts, resolved


# ------------------------------------------------------------------ GitHub + bookkeeping

def _repo_settings(settings: Dict[str, Any]) -> Tuple[str, str, str]:
    repo = (settings.get("portfolio_repo") or "").strip()
    branch = (settings.get("portfolio_branch") or "main").strip()
    token = settings.get("portfolio_github_token") or ""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise PublishError("Set the portfolio repository as owner/name first.")
    if not token:
        raise PublishError("Add a fine-grained GitHub token (Contents: read & write on the portfolio repo only).")
    return repo, branch, token


def fetch_inbox(settings: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """The portfolio's data/vault.inbox.json and its blob sha (empty inbox if the file doesn't exist)."""
    repo, branch, token = _repo_settings(settings)
    url = f"https://api.github.com/repos/{repo}/contents/{INBOX_PATH_IN_REPO}?ref={branch}"
    res = _github("GET", url, token)
    if not res.get("content"):
        return {"version": 1, "items": []}, res.get("sha")
    try:
        inbox = json.loads(base64.b64decode(res["content"]).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise PublishError("The portfolio's vault inbox isn't valid JSON.") from e
    return inbox, res.get("sha")


def load_pulled() -> List[Dict[str, str]]:
    try:
        with open(PULLED_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("entries", [])
    except (OSError, ValueError):
        return []


def remember_pulled(entries: List[Dict[str, str]]) -> None:
    current = {(e["section"], e["id"]): e for e in load_pulled()}
    for e in entries:
        current[(e["section"], e["id"])] = e
    with open(PULLED_PATH, "w", encoding="utf-8") as f:
        json.dump({"entries": list(current.values())}, f, indent=2)


def forget_pulled() -> None:
    try:
        os.remove(PULLED_PATH)
    except OSError:
        pass


def remove_entries(inbox: Dict[str, Any], pulled: List[Dict[str, str]]) -> Tuple[Dict[str, Any], int]:
    """Drop pulled entries. One edited again on the portfolio since (newer edited_at) stays."""
    done = {(p["section"], p["id"]): p.get("edited_at") for p in pulled}
    keep = []
    for entry in inbox.get("items") or []:
        k = (entry.get("section"), str(entry.get("id")))
        if k in done and not _newer(entry.get("edited_at"), done[k]):
            continue
        keep.append(entry)
    removed = len(inbox.get("items") or []) - len(keep)
    return {**inbox, "version": inbox.get("version", 1), "items": keep}, removed


def clear_pulled_from_inbox(settings: Dict[str, Any]) -> Dict[str, Any]:
    """After a publish: commit the inbox without the entries already pulled into the vault."""
    pulled = load_pulled()
    if not pulled:
        return {"cleared": 0}
    repo, branch, token = _repo_settings(settings)
    inbox, sha = fetch_inbox(settings)
    updated, removed = remove_entries(inbox, pulled)
    if removed:
        content = json.dumps(updated, indent=2, ensure_ascii=False) + "\n"
        _github("PUT", f"https://api.github.com/repos/{repo}/contents/{INBOX_PATH_IN_REPO}", token, {
            "message": f"Clear {removed} vault inbox entr{'y' if removed == 1 else 'ies'} pulled into jstMyRB",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
            **({"sha": sha} if sha else {}),
        })
    forget_pulled()
    return {"cleared": removed}
