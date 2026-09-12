from typing import Dict, Any, List, Optional
from datetime import datetime
from agent.db import db
from agent.jd_parser import jd_parser
from agent.ats_scorer import ats_scorer

KANBAN_STAGES = ["Wishlist", "Applied", "Online Assessment", "Interview", "Offer", "Rejected"]

class ApplicationTracker:
    def get_board(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns applications grouped into standard Kanban columns."""
        apps = db.get_applications()
        board = {stage: [] for stage in KANBAN_STAGES}
        for app in apps:
            stage = app.get("stage", "Applied")
            if stage not in board:
                board[stage] = []
            board[stage].append(app)
        return board

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        return db.get_application(app_id)

    def create_application_from_tailoring(
        self,
        company: str,
        role: str,
        jd_text: str = "",
        resume_data: Optional[Dict[str, Any]] = None,
        cover_letter: str = "",
        notes: str = "",
        stage: str = "Applied"
    ) -> str:
        """
        Creates or updates a job application linked directly to a tailored resume run.
        """
        # Parse JD if provided
        parsed_jd = {}
        ats_score_val = 0.0
        if jd_text:
            parsed_jd = jd_parser.parse_job_description(jd_text, company, role)
        
        if resume_data:
            score_res = ats_scorer.score_resume(resume_data, parsed_jd.get("target_keywords", []))
            ats_score_val = float(score_res.get("total_score", 0.0))

        app_payload = {
            "company": company,
            "role": role,
            "stage": stage,
            "jd_snapshot": jd_text,
            "jd_parsed": parsed_jd,
            "cover_letter_text": cover_letter,
            "ats_score": ats_score_val,
            "notes": notes,
            "resume_version_id": f"res_{company.lower().replace(' ', '_')}_{int(datetime.utcnow().timestamp())}"
        }
        return db.upsert_application(app_payload)

    def move_stage(self, app_id: str, new_stage: str) -> bool:
        if new_stage not in KANBAN_STAGES:
            return False
        app = db.get_application(app_id)
        if not app:
            return False
        app["stage"] = new_stage
        db.upsert_application(app)
        return True

    def update_notes(self, app_id: str, notes: str) -> bool:
        app = db.get_application(app_id)
        if not app:
            return False
        app["notes"] = notes
        db.upsert_application(app)
        return True

    def delete_application(self, app_id: str) -> bool:
        return db.delete_application(app_id)

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates funnel velocity and conversion metrics."""
        apps = db.get_applications()
        total = len(apps)
        stages_count = {}
        for a in apps:
            s = a.get("stage", "Applied")
            stages_count[s] = stages_count.get(s, 0) + 1

        interview_count = stages_count.get("Interview", 0) + stages_count.get("Offer", 0)
        offer_count = stages_count.get("Offer", 0)
        
        interview_rate = round((interview_count / total * 100), 1) if total > 0 else 0.0
        offer_rate = round((offer_count / total * 100), 1) if total > 0 else 0.0

        return {
            "total_applications": total,
            "by_stage": stages_count,
            "interview_rate": interview_rate,
            "offer_rate": offer_rate
        }

tracker = ApplicationTracker()
