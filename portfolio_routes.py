"""
Portfolio sync endpoints (kept out of server.py so it only needs two lines):

  GET  /api/portfolio/export      public-safe vault (add ?download=1 for a file)
  GET  /api/portfolio/settings    repo / branch / privacy toggles (never returns the token)
  POST /api/portfolio/settings
  GET  /api/portfolio/preview     export + diff since the last publish
  POST /api/portfolio/publish     commit data/vault.public.json to the portfolio repo
                                  (and clear inbox entries already pulled)
  GET  /api/portfolio/pull/preview   Dev Mode edits waiting in the portfolio's vault inbox
  POST /api/portfolio/pull/apply     merge the chosen ones into the vault
  POST /api/linkedin/import_export   LinkedIn data-export zip (base64) -> merge preview
  POST /api/linkedin/apply           accept previewed items into the vault
"""
import base64
import binascii
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.portfolio_export import (
    PublishError,
    build_public_export,
    diff_exports,
    export_report,
    load_last_publish,
    publish_to_github,
)
from agent.portfolio_pull import apply_pull, build_pull_preview, clear_pulled_from_inbox, fetch_inbox, remember_pulled
from agent.linkedin_export import LinkedInImportError, apply_items, build_preview, parse_linkedin_zip

PREVIEW_TTL_SECONDS = 30 * 60


class PortfolioSettingsRequest(BaseModel):
    repo: Optional[str] = None
    branch: Optional[str] = None
    token: Optional[str] = None  # empty/None keeps the saved token
    clear_token: bool = False
    show_email: Optional[bool] = None
    show_gpa: Optional[bool] = None


class LinkedInUploadRequest(BaseModel):
    filename: str = "linkedin.zip"
    data_base64: str


class LinkedInApplyRequest(BaseModel):
    import_id: str
    keys: List[str]


class PullApplyRequest(BaseModel):
    pull_id: str
    choices: Dict[str, str] = {}  # key -> portfolio | vault | skip


def create_portfolio_router(pm, load_settings: Callable[[], Dict[str, Any]], save_settings: Callable[[Dict[str, Any]], None]) -> APIRouter:
    router = APIRouter()
    previews: Dict[str, Dict[str, Any]] = {}  # import_id / pull_id -> {items, created}

    def remember_preview(items: List[Dict[str, Any]]) -> str:
        now = time.time()
        for k in [k for k, v in previews.items() if now - v["created"] > PREVIEW_TTL_SECONDS]:
            previews.pop(k, None)
        key = uuid.uuid4().hex
        previews[key] = {"items": items, "created": now}
        return key

    def public_settings(st: Dict[str, Any]) -> Dict[str, Any]:
        last = load_last_publish()
        return {
            "repo": st.get("portfolio_repo", ""),
            "branch": st.get("portfolio_branch", "main"),
            "token_set": bool(st.get("portfolio_github_token")),
            "show_email": bool(st.get("portfolio_show_email", False)),
            "show_gpa": bool(st.get("portfolio_show_gpa", True)),
            "last_published_at": (last or {}).get("meta", {}).get("exported_at"),
        }

    @router.get("/api/portfolio/export")
    def portfolio_export(download: bool = False):
        export = build_public_export(pm.get_all(), load_settings())
        headers = {"Content-Disposition": "attachment; filename=vault.public.json"} if download else {}
        return JSONResponse(content=export, headers=headers)

    @router.get("/api/portfolio/settings")
    def get_portfolio_settings():
        return public_settings(load_settings())

    @router.post("/api/portfolio/settings")
    def update_portfolio_settings(req: PortfolioSettingsRequest):
        st = load_settings()
        if req.repo is not None:
            st["portfolio_repo"] = req.repo.strip()
        if req.branch is not None:
            st["portfolio_branch"] = req.branch.strip() or "main"
        if req.clear_token:
            st.pop("portfolio_github_token", None)
        elif req.token:
            st["portfolio_github_token"] = req.token.strip()
        if req.show_email is not None:
            st["portfolio_show_email"] = req.show_email
        if req.show_gpa is not None:
            st["portfolio_show_gpa"] = req.show_gpa
        save_settings(st)
        return public_settings(st)

    @router.get("/api/portfolio/preview")
    def preview_publish():
        profile = pm.get_all()
        export = build_public_export(profile, load_settings())
        last = load_last_publish()
        return {
            "export": export,
            "diff": diff_exports(last, export),
            "first_publish": last is None,
            "report": export_report(profile),
            "counts": {k: len(export[k]) for k in ("projects", "experiences", "education", "patents_certifications", "pors_achievements", "awards_medals", "testimonials")},
        }

    @router.post("/api/portfolio/publish")
    def publish():
        st = load_settings()
        export = build_public_export(pm.get_all(), st)
        try:
            result = publish_to_github(export, st)
        except PublishError as e:
            raise HTTPException(status_code=400, detail=str(e))
        # The vault now holds what was pulled, so those inbox entries can go.
        try:
            inbox = clear_pulled_from_inbox(st)
        except PublishError as e:
            inbox = {"cleared": 0, "error": f"Published, but the pulled inbox entries weren't cleared: {e}"}
        return {"status": "success", **result, "inbox": inbox, "settings": public_settings(load_settings())}

    @router.get("/api/portfolio/pull/preview")
    def pull_preview():
        try:
            inbox, _ = fetch_inbox(load_settings())
        except PublishError as e:
            raise HTTPException(status_code=400, detail=str(e))
        rows = build_pull_preview(inbox, pm.get_all())
        summary = {s: sum(1 for r in rows if r["status"] == s) for s in ("new", "update", "delete", "conflict", "unchanged")}
        return {"pull_id": remember_preview(rows), "items": rows, "summary": summary}

    @router.post("/api/portfolio/pull/apply")
    def pull_apply(req: PullApplyRequest):
        preview = previews.pop(req.pull_id, None)
        if not preview:
            raise HTTPException(status_code=410, detail="This preview expired. Open Pull from Portfolio again.")
        if any(c not in ("portfolio", "vault", "skip") for c in req.choices.values()):
            raise HTTPException(status_code=400, detail="Unknown choice.")
        counts, resolved = apply_pull(pm.data, preview["items"], req.choices)
        if counts["added"] or counts["updated"] or counts["deleted"]:
            pm.save(entity_type="portfolio_pull", entity_id="vault_inbox")
        remember_pulled(resolved)
        return {"status": "success", **counts, "to_clear": len(resolved)}

    @router.post("/api/linkedin/import_export")
    def linkedin_import(req: LinkedInUploadRequest):
        try:
            raw = base64.b64decode(req.data_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Upload could not be read.")
        try:
            rows = parse_linkedin_zip(raw)
        except LinkedInImportError as e:
            raise HTTPException(status_code=400, detail=str(e))
        items = build_preview(rows, pm.get_all())
        import_id = remember_preview(items)
        summary = {s: sum(1 for i in items if i["status"] == s) for s in ("new", "changed", "duplicate")}
        return {"import_id": import_id, "items": items, "summary": summary, "files": {k: len(v) for k, v in rows.items()}}

    @router.post("/api/linkedin/apply")
    def linkedin_apply(req: LinkedInApplyRequest):
        preview = previews.pop(req.import_id, None)
        if not preview:
            raise HTTPException(status_code=410, detail="This preview expired. Upload the export again.")
        _, counts = apply_items(pm.data, preview["items"], req.keys)
        if counts["added"] or counts["updated"]:
            pm.save(entity_type="linkedin_import", entity_id="linkedin_export")
        return {"status": "success", **counts}

    return router
