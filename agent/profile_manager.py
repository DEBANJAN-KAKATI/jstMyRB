import os
import sys
import json
import shutil
from typing import Dict, Any, List, Optional
from path_utils import get_base_dir, get_bundle_dir, get_writable_dir

PERSISTENT_STORE_DIR = get_writable_dir("data")
PERSISTENT_STORE_PATH = os.path.join(PERSISTENT_STORE_DIR, "profile_store.json")
BUNDLED_STORE_PATH = os.path.join(get_bundle_dir(), "data", "profile_store.json")

from agent.db import db

class ProfileManager:
    def __init__(self, path: Optional[str] = None):
        self.path = path or PERSISTENT_STORE_PATH
        self._ensure_store_exists()
        loaded = db.load_profile()
        if loaded:
            self.data = loaded
        else:
            self.data = self._load()
            if self.data:
                db.save_profile(self.data, entity_type="initial", entity_id="migration")

    def _ensure_store_exists(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            if os.path.exists(BUNDLED_STORE_PATH):
                shutil.copy2(BUNDLED_STORE_PATH, self.path)
            else:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump({}, f)

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, entity_type: str = "general", entity_id: str = "update", diff: Optional[Dict[str, Any]] = None):
        db.save_profile(self.data, entity_type=entity_type, entity_id=entity_id, diff=diff)

    def get_all(self) -> Dict[str, Any]:
        return self.data

    def update_personal_info(self, info: Dict[str, str]):
        self.data["personal_info"].update(info)
        self.save()

    def add_skill(self, category: str, skill_text: str):
        if category not in self.data["skills"]:
            self.data["skills"][category] = []
        if skill_text not in self.data["skills"][category]:
            self.data["skills"][category].append(skill_text)
            self.save()

    def update_skill_category(self, category: str, skills_list: List[str]):
        if "skills" not in self.data:
            self.data["skills"] = {}
        target_key = category
        for k in self.data["skills"].keys():
            if k.lower() == category.lower() or k.replace('_', ' ').lower() == category.replace('_', ' ').lower():
                target_key = k
                break
        self.data["skills"][target_key] = skills_list
        self.save()

    def delete_skill_category(self, category: str):
        if "skills" in self.data:
            target_key = None
            for k in self.data["skills"].keys():
                if k.lower() == category.lower() or k.replace('_', ' ').lower() == category.replace('_', ' ').lower():
                    target_key = k
                    break
            if target_key and target_key in self.data["skills"]:
                del self.data["skills"][target_key]
                self.save()

    def add_coursework(self, category: str, course_name: str):
        if category not in self.data["coursework"]:
            self.data["coursework"][category] = []
        if course_name not in self.data["coursework"][category]:
            self.data["coursework"][category].append(course_name)
            self.save()

    def add_experience(self, exp: Dict[str, Any]):
        if "id" not in exp:
            exp["id"] = f"exp_{len(self.data['experiences']) + 1}"
        bullets = exp.get("bullets", [])
        if "points_tier" not in exp:
            exp["points_tier"] = {
                "1": bullets[:1] if bullets else ["Key leadership and delivery contribution."],
                "2": bullets[:2] if len(bullets) >= 2 else bullets,
                "3": bullets[:3] if len(bullets) >= 3 else bullets
            }
        exp["selected_tier"] = exp.get("selected_tier", "2")
        self.data["experiences"].insert(0, exp)
        self.save()

    def add_project(self, proj: Dict[str, Any]):
        if "id" not in proj:
            proj["id"] = f"proj_{len(self.data['projects']) + 1}"
        bullets = proj.get("bullets", [])
        if "points_tier" not in proj:
            exp_b = bullets
            proj["points_tier"] = {
                "1": exp_b[:1] if exp_b else ["Engineered full-scale production system."],
                "2": exp_b[:2] if len(exp_b) >= 2 else exp_b,
                "3": exp_b[:3] if len(exp_b) >= 3 else exp_b
            }
        proj["selected_tier"] = proj.get("selected_tier", "2")

        existing_idx = next((i for i, p in enumerate(self.data["projects"]) if p["title"].lower() == proj["title"].lower()), None)
        if existing_idx is not None:
            self.data["projects"][existing_idx] = proj
        else:
            self.data["projects"].insert(0, proj)
        self.save()

    def update_project(self, proj_id: str, updated_data: Dict[str, Any]) -> bool:
        for idx, p in enumerate(self.data.get("projects", [])):
            if p.get("id") == proj_id:
                p.update(updated_data)
                # re-sync bullets from selected tier
                tier = p.get("selected_tier", "2")
                if "points_tier" in p and tier in p["points_tier"]:
                    p["bullets"] = p["points_tier"][tier]
                self.save()
                return True
        return False

    def update_experience(self, exp_id: str, updated_data: Dict[str, Any]) -> bool:
        for idx, e in enumerate(self.data.get("experiences", [])):
            if e.get("id") == exp_id:
                e.update(updated_data)
                tier = e.get("selected_tier", "2")
                if "points_tier" in e and tier in e["points_tier"]:
                    e["bullets"] = e["points_tier"][tier]
                self.save()
                return True
        return False

    def update_item(self, section: str, item_id_or_idx: Any, updated_data: Dict[str, Any]) -> bool:
        sec = self.data.get(section)
        if sec is None:
            return False
        if isinstance(sec, list):
            for idx, item in enumerate(sec):
                if isinstance(item, dict) and (item.get("id") == item_id_or_idx or item.get("title") == item_id_or_idx or str(idx) == str(item_id_or_idx)):
                    item.update(updated_data)
                    self.save()
                    return True
        elif isinstance(sec, dict):
            sec[str(item_id_or_idx)] = updated_data
            self.save()
            return True
        return False

    def delete_item(self, section: str, item_id: str) -> bool:
        sec = self.data.get(section)
        if isinstance(sec, list):
            self.data[section] = [item for item in sec if not (isinstance(item, dict) and (item.get("id") == item_id or item.get("title") == item_id))]
            self.save()
            return True
        return False

    def add_por(self, item: Dict[str, Any]):
        if "pors_achievements" not in self.data:
            self.data["pors_achievements"] = []
        self.data["pors_achievements"].insert(0, item)
        self.save()

    def add_award_medal(self, item: Dict[str, Any]):
        if "awards_medals" not in self.data:
            self.data["awards_medals"] = []
        self.data["awards_medals"].insert(0, item)
        self.save()

    def add_patent_certification(self, item: Dict[str, Any]):
        if "patents_certifications" not in self.data:
            self.data["patents_certifications"] = []
        self.data["patents_certifications"].insert(0, item)
        self.save()

    def import_profile(self, new_data: Dict[str, Any]) -> bool:
        if isinstance(new_data, dict) and new_data:
            self.data = new_data
            self.save(entity_type="import", entity_id="vault_import")
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                print(f"Error saving imported profile to file: {e}")
            return True
        return False
