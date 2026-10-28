"""
Portfolio sync endpoints (kept out of server.py so it only needs two lines):

  GET  /api/portfolio/export      public-safe vault (add ?download=1 for a file)
  GET  /api/portfolio/settings    repo / branch / privacy toggles (never returns the token)
  POST /api/portfolio/settings
  GET  /api/portfolio/preview     export + diff since the last publish
  POST /api/portfolio/publish     commit data/vault.public.json to the portfolio repo
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


def create_portfolio_router(pm, load_settings: Callable[[], Dict[str, Any]], save_settings: Callable[[Dict[str, Any]], None]) -> APIRouter:
    router = APIRouter()
    previews: Dict[str, Dict[str, Any]] = {}  # import_id -> {items, created}

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
        return {"status": "success", **result, "settings": public_settings(load_settings())}

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
        now = time.time()
        for k in [k for k, v in previews.items() if now - v["created"] > PREVIEW_TTL_SECONDS]:
            previews.pop(k, None)
        import_id = uuid.uuid4().hex
        previews[import_id] = {"items": items, "created": now}
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
