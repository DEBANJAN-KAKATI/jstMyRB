import os
import sys
import json
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from agent.db import db
from agent.profile_manager import ProfileManager
from agent.gemini_thinker import GeminiThinker
from agent.github_tracker import GitHubTracker
from agent.linkedin_sync import LinkedInSync
from agent.tailor_agent import TailorAgent, CATEGORY_CONFIGS
from agent.renderer import ResumeRenderer
from agent.llm_router import router, load_settings as load_llm_settings, save_settings as save_llm_settings
from agent.jd_parser import jd_parser
from agent.ats_scorer import ats_scorer
from agent.bullet_critic import bullet_critic
from agent.tracker import tracker
from agent.cover_letter_agent import cover_letter_agent
from path_utils import get_base_dir, get_bundle_dir, get_writable_dir

app = FastAPI(title="JstMyRB", version="2.0")

STATIC_DIR = os.path.join(get_bundle_dir(), "static")
OUTPUT_DIR = get_writable_dir("output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SETTINGS_PATH = os.path.join(get_writable_dir("data"), "settings.json")

def load_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings: Dict[str, Any]):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")

_init_settings = load_settings()
_saved_key = _init_settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

pm = ProfileManager()
thinker = GeminiThinker(api_key=_saved_key)
gh_tracker = GitHubTracker(gemini_thinker=thinker)
li_sync = LinkedInSync()
tailor_agent = TailorAgent(profile_manager=pm, gemini_thinker=thinker)
renderer = ResumeRenderer()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Models
class ApiKeyRequest(BaseModel):
    api_key: str

class TailorRequest(BaseModel):
    category: str = "quant"
    company: Optional[str] = ""
    role: Optional[str] = ""
    custom_jd: Optional[str] = ""
    use_gemini: bool = False
    project_tiers: Optional[Dict[str, str]] = None
    experience_tiers: Optional[Dict[str, str]] = None
    active_project_ids: Optional[List[str]] = None
    active_experience_ids: Optional[List[str]] = None
    active_skills: Optional[List[Dict[str, str]]] = None
    font_size: Optional[str] = "9.5pt"
    line_height: Optional[str] = "1.15"

class UpdateSkillCategoryRequest(BaseModel):
    category: str
    skills: List[str]

class DeleteSkillCategoryRequest(BaseModel):
    category: str

class UpdateProjectRequest(BaseModel):
    id: str
    title: str
    context: Optional[str] = ""
    bullets: Optional[List[str]] = None
    points_tier: Optional[Dict[str, List[str]]] = None
    tags: Optional[List[str]] = None

class UpdateExperienceRequest(BaseModel):
    id: str
    role: str
    company: str
    duration: str
    location: str
    bullets: Optional[List[str]] = None
    points_tier: Optional[Dict[str, List[str]]] = None
    tags: Optional[List[str]] = None

class DeleteItemRequest(BaseModel):
    section: str
    id: str

class SkillAddRequest(BaseModel):
    category: str
    skill_text: str

class ProjectAddRequest(BaseModel):
    title: str
    context: Optional[str] = ""
    bullets: List[str]
    points_tier: Optional[Dict[str, List[str]]] = None
    tags: List[str] = []

class ExperienceAddRequest(BaseModel):
    role: str
    company: str
    duration: str
    location: str
    bullets: List[str]
    points_tier: Optional[Dict[str, List[str]]] = None
    tags: List[str] = []

class PorAddRequest(BaseModel):
    title: str
    details: str
    type: str = "POR"
    tags: List[str] = []

class AwardAddRequest(BaseModel):
    title: str
    details: str
    tags: List[str] = []

class GitHubImportRequest(BaseModel):
    repo_name: str

class LinkedInTextRequest(BaseModel):
    text: str

class RenderRequest(BaseModel):
    resume_data: Dict[str, Any]
    font_size: Optional[str] = "9.5pt"
    line_height: Optional[str] = "1.15"

class LLMSettingsRequest(BaseModel):
    llm_provider: Optional[str] = "auto"
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_endpoint: Optional[str] = None

class JDParseRequest(BaseModel):
    jd_text: str
    company: Optional[str] = ""
    role: Optional[str] = ""

class ATSScoreRequest(BaseModel):
    resume_data: Dict[str, Any]
    jd_keywords: Optional[List[str]] = None

class BulletCritiqueRequest(BaseModel):
    bullet_text: str

class BulletImproveRequest(BaseModel):
    bullet_text: str
    role_context: Optional[str] = ""

class TrackerAppRequest(BaseModel):
    company: str
    role: str
    stage: Optional[str] = "Applied"
    jd_snapshot: Optional[str] = ""
    cover_letter: Optional[str] = ""
    notes: Optional[str] = ""
    resume_data: Optional[Dict[str, Any]] = None

class TrackerMoveRequest(BaseModel):
    id: str
    stage: str

class TrackerNotesRequest(BaseModel):
    id: str
    notes: str

class CoverLetterRequest(BaseModel):
    company: str
    role: str
    jd_text: Optional[str] = ""
    use_llm: Optional[bool] = True

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>JstMyRB</h1>"

@app.post("/api/settings/api_key")
def set_api_key(req: ApiKeyRequest):
    key = req.api_key.strip()
    thinker.set_api_key(key)
    gh_tracker.thinker = thinker
    tailor_agent.thinker = thinker
    cur = load_settings()
    cur["gemini_api_key"] = key
    save_settings(cur)
    return {"status": "success", "has_key": bool(key)}

@app.get("/api/settings/status")
def get_status():
    return {
        "has_gemini_key": bool(thinker.api_key),
        "total_projects": len(pm.get_all().get("projects", [])),
        "total_experiences": len(pm.get_all().get("experiences", []))
    }

@app.get("/api/profile")
def get_profile():
    return pm.get_all()

@app.get("/api/profile/export")
def export_profile():
    return JSONResponse(
        content=pm.get_all(),
        headers={"Content-Disposition": "attachment; filename=jstmyrb_career_vault.json"}
    )

@app.post("/api/profile/import")
def import_profile(data: Dict[str, Any]):
    ok = pm.import_profile(data)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid profile format")
    return {"status": "success", "profile": pm.get_all()}

@app.get("/api/categories")
def get_categories():
    return [
        {"key": k, "title": v["title"], "keywords": v["keywords"]}
        for k, v in CATEGORY_CONFIGS.items()
    ]

@app.post("/api/resume/tailor")
def tailor_resume(req: TailorRequest):
    data = tailor_agent.tailor_resume(
        category=req.category,
        company=req.company or "",
        role=req.role or "",
        custom_jd=req.custom_jd or "",
        project_tiers=req.project_tiers,
        experience_tiers=req.experience_tiers,
        active_project_ids=req.active_project_ids,
        active_experience_ids=req.active_experience_ids,
        active_skills=req.active_skills,
        use_gemini=req.use_gemini
    )
    html = renderer.render_html(
        data,
        font_size=req.font_size or "9.5pt",
        line_height=req.line_height or "1.15"
    )
    tex = renderer.render_latex(data, font_size=req.font_size or "10pt")
    return {
        "status": "success",
        "data": data,
        "category": data.get("category", req.category),
        "reasoning": data.get("reasoning", ""),
        "html": html,
        "tex": tex
    }

@app.post("/api/profile/update_skill_category")
def update_skill_category(req: UpdateSkillCategoryRequest):
    pm.update_skill_category(req.category, req.skills)
    return {"status": "success", "skills": pm.get_all()["skills"]}

@app.post("/api/profile/delete_skill_category")
def delete_skill_category(req: DeleteSkillCategoryRequest):
    pm.delete_skill_category(req.category)
    return {"status": "success", "skills": pm.get_all()["skills"]}

@app.post("/api/profile/update_project")
def update_project(req: UpdateProjectRequest):
    update_dict = {
        "title": req.title,
        "context": req.context or ""
    }
    if req.bullets is not None:
        update_dict["bullets"] = req.bullets
    if req.points_tier is not None:
        update_dict["points_tier"] = req.points_tier
    if req.tags is not None:
        update_dict["tags"] = req.tags

    ok = pm.update_project(req.id, update_dict)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "success", "projects": pm.get_all()["projects"]}

@app.post("/api/profile/update_experience")
def update_experience(req: UpdateExperienceRequest):
    update_dict = {
        "role": req.role,
        "company": req.company,
        "duration": req.duration,
        "location": req.location
    }
    if req.bullets is not None:
        update_dict["bullets"] = req.bullets
    if req.points_tier is not None:
        update_dict["points_tier"] = req.points_tier
    if req.tags is not None:
        update_dict["tags"] = req.tags

    ok = pm.update_experience(req.id, update_dict)
    if not ok:
        raise HTTPException(status_code=404, detail="Experience not found")
    return {"status": "success", "experiences": pm.get_all()["experiences"]}

@app.post("/api/profile/delete_item")
def delete_item(req: DeleteItemRequest):
    ok = pm.delete_item(req.section, req.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "data": pm.get_all().get(req.section, [])}

@app.post("/api/resume/render")
def render_custom(req: RenderRequest):
    html = renderer.render_html(
        req.resume_data,
        font_size=req.font_size or "9.5pt",
        line_height=req.line_height or "1.15"
    )
    tex = renderer.render_latex(req.resume_data, font_size=req.font_size or "10pt")
    return {"html": html, "tex": tex}

@app.get("/api/role_recommendations")
def get_role_recommendations(role: str = ""):
    return tailor_agent.get_role_recommendations(role)

@app.get("/api/github/repos")
def fetch_github_repos():
    repos = gh_tracker.fetch_repos()
    current_titles = [p["title"].lower() for p in pm.get_all().get("projects", [])]
    for r in repos:
        name_clean = r["name"].replace("-", " ").replace("_", " ").lower()
        r["already_imported"] = any(name_clean in ct for ct in current_titles)
    return {"repos": repos}

@app.post("/api/github/import")
def import_github_repo(req: GitHubImportRequest):
    repos = gh_tracker.fetch_repos()
    matched = [r for r in repos if r["name"].lower() == req.repo_name.lower()]
    if not matched:
        raise HTTPException(status_code=404, detail=f"Repository {req.repo_name} not found")
    proj = gh_tracker.generate_project_from_repo(matched[0])
    pm.add_project(proj)
    return {"status": "success", "imported_project": proj}

@app.post("/api/linkedin/sync_text")
def sync_linkedin_text(req: LinkedInTextRequest):
    parsed = li_sync.parse_text_content(req.text)
    return {"status": "success", "extracted": parsed}

@app.post("/api/profile/add_skill")
def add_skill(req: SkillAddRequest):
    pm.add_skill(req.category, req.skill_text)
    return {"status": "success", "skills": pm.get_all()["skills"]}

@app.post("/api/profile/add_project")
def add_project(req: ProjectAddRequest):
    proj = {
        "title": req.title,
        "context": req.context or "",
        "bullets": req.bullets,
        "points_tier": req.points_tier or {
            "1": req.bullets[:1],
            "2": req.bullets[:2],
            "3": req.bullets[:3]
        },
        "selected_tier": "2",
        "tags": req.tags
    }
    pm.add_project(proj)
    return {"status": "success", "projects": pm.get_all()["projects"]}

@app.post("/api/profile/add_experience")
def add_experience(req: ExperienceAddRequest):
    exp = {
        "role": req.role,
        "company": req.company,
        "duration": req.duration,
        "location": req.location,
        "bullets": req.bullets,
        "points_tier": req.points_tier or {
            "1": req.bullets[:1],
            "2": req.bullets[:2],
            "3": req.bullets[:3]
        },
        "selected_tier": "2",
        "tags": req.tags
    }
    pm.add_experience(exp)
    return {"status": "success", "experiences": pm.get_all()["experiences"]}

@app.post("/api/profile/add_por")
def add_por(req: PorAddRequest):
    item = {
        "title": req.title,
        "details": req.details,
        "type": req.type,
        "tags": req.tags
    }
    pm.add_por(item)
    return {"status": "success", "pors_achievements": pm.get_all()["pors_achievements"]}

@app.post("/api/profile/add_award")
def add_award(req: AwardAddRequest):
    item = {
        "title": req.title,
        "details": req.details,
        "tags": req.tags
    }
    pm.add_award_medal(item)
    return {"status": "success", "awards_medals": pm.get_all().get("awards_medals", [])}

@app.get("/output/{filename}")
def download_output(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

# ==================== V2 API ENDPOINTS ====================

@app.get("/api/settings/llm")
def get_llm_settings():
    st = load_llm_settings()
    usage = db.get_api_usage_summary()
    return {
        "llm_provider": st.get("llm_provider", "auto"),
        "has_gemini": bool(router.get_api_key("gemini")),
        "has_openai": bool(router.get_api_key("openai")),
        "has_anthropic": bool(router.get_api_key("anthropic")),
        "ollama_endpoint": st.get("ollama_endpoint", "http://localhost:11434/api/generate"),
        "usage_summary": usage
    }

@app.post("/api/settings/llm")
def update_llm_settings(req: LLMSettingsRequest):
    st = load_llm_settings()
    if req.llm_provider:
        st["llm_provider"] = req.llm_provider
    if req.gemini_api_key is not None:
        st["gemini_api_key"] = req.gemini_api_key.strip()
        thinker.set_api_key(req.gemini_api_key.strip())
        tailor_agent.thinker = thinker
    if req.openai_api_key is not None:
        st["openai_api_key"] = req.openai_api_key.strip()
    if req.anthropic_api_key is not None:
        st["anthropic_api_key"] = req.anthropic_api_key.strip()
    if req.ollama_endpoint is not None:
        st["ollama_endpoint"] = req.ollama_endpoint.strip()
    save_llm_settings(st)
    return {"status": "success", "settings": get_llm_settings()}

@app.post("/api/jd/parse")
def parse_job_description(req: JDParseRequest):
    parsed = jd_parser.parse_job_description(req.jd_text, req.company or "", req.role or "")
    profile = pm.get_all()
    gap = jd_parser.compute_gap_analysis(parsed, profile)
    return {
        "status": "success",
        "parsed": parsed,
        "gap_analysis": gap
    }

@app.post("/api/ats/score")
def get_ats_score(req: ATSScoreRequest):
    result = ats_scorer.score_resume(req.resume_data, req.jd_keywords)
    return {"status": "success", "score": result}

@app.post("/api/bullet/critique")
def critique_bullet(req: BulletCritiqueRequest):
    result = bullet_critic.critique_bullet(req.bullet_text)
    return {"status": "success", "result": result}

@app.post("/api/bullet/improve")
def improve_bullet(req: BulletImproveRequest):
    improved = bullet_critic.ai_improve_bullet(req.bullet_text, req.role_context or "")
    return {"status": "success", "improved_bullet": improved or req.bullet_text}

@app.get("/api/tracker/board")
def get_tracker_board():
    return {
        "status": "success",
        "board": tracker.get_board(),
        "metrics": tracker.get_metrics()
    }

@app.post("/api/tracker/application")
def create_or_update_tracker_app(req: TrackerAppRequest):
    app_id = tracker.create_application_from_tailoring(
        company=req.company,
        role=req.role,
        jd_text=req.jd_snapshot or "",
        resume_data=req.resume_data,
        cover_letter=req.cover_letter or "",
        notes=req.notes or "",
        stage=req.stage or "Applied"
    )
    return {"status": "success", "app_id": app_id, "board": tracker.get_board()}

@app.post("/api/tracker/move")
def move_tracker_stage(req: TrackerMoveRequest):
    ok = tracker.move_stage(req.id, req.stage)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid application ID or stage")
    return {"status": "success", "board": tracker.get_board()}

@app.post("/api/tracker/notes")
def update_tracker_notes(req: TrackerNotesRequest):
    ok = tracker.update_notes(req.id, req.notes)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"status": "success"}

@app.delete("/api/tracker/application/{app_id}")
def delete_tracker_app(app_id: str):
    ok = tracker.delete_application(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"status": "success", "board": tracker.get_board()}

@app.post("/api/cover_letter/generate")
def generate_cover_letter_endpoint(req: CoverLetterRequest):
    result = cover_letter_agent.generate_cover_letter(
        company=req.company,
        role=req.role,
        jd_text=req.jd_text or "",
        use_llm=req.use_llm if req.use_llm is not None else True
    )
    return {"status": "success", "result": result}

@app.get("/api/profile/versions")
def get_profile_versions():
    return {"status": "success", "versions": db.get_version_history(limit=30)}

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
