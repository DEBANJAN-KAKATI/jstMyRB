import urllib.request
import json
from typing import List, Dict, Any, Optional
from .gemini_thinker import GeminiThinker

DEFAULT_GITHUB_USER = "DEBANJAN-KAKATI"

class GitHubTracker:
    def __init__(self, username: str = DEFAULT_GITHUB_USER, gemini_thinker: Optional[GeminiThinker] = None):
        self.username = username
        self.thinker = gemini_thinker or GeminiThinker()

    def fetch_repos(self) -> List[Dict[str, Any]]:
        url = f"https://api.github.com/users/{self.username}/repos?per_page=100&sort=updated"
        req = urllib.request.Request(url, headers={"User-Agent": "ResumeBuilderAgent"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                repos = json.loads(resp.read().decode("utf-8"))
            
            clean_repos = []
            for r in repos:
                clean_repos.append({
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "url": r.get("html_url"),
                    "description": r.get("description") or "No description provided",
                    "language": r.get("language") or "Python",
                    "stars": r.get("stargazers_count", 0),
                    "forks": r.get("forks_count", 0),
                    "topics": r.get("topics", []),
                    "updated_at": r.get("updated_at", "")[:10]
                })
            return clean_repos
        except Exception as e:
            print(f"Error fetching GitHub repos: {e}")
            return []

    def generate_project_from_repo(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize a resume project entry with 1/2/3 bullet point tiers."""
        name = repo.get("name", "Project")
        desc = repo.get("description", "")
        lang = repo.get("language", "Python")
        topics = repo.get("topics", [])
        
        # Tags detection
        tags = []
        text_for_tag = (name + " " + desc + " " + " ".join(topics)).lower()
        if any(w in text_for_tag for w in ["rag", "ai", "ml", "retinopathy", "deep", "cnn", "xai", "nlp"]):
            tags.append("ai_ml")
        if any(w in text_for_tag for w in ["quant", "finance", "portfolio", "risk", "stock", "trade"]):
            tags.append("quant")
            tags.append("finance")
        if any(w in text_for_tag for w in ["web", "pdf", "full stack", "react", "fastapi", "desktop", "app", "electron"]):
            tags.append("full_stack")
        if any(w in text_for_tag for w in ["ice", "melting", "chemical", "thermal", "reactor", "algae", "energy"]):
            tags.append("chemical")
        if not tags:
            tags = ["full_stack", "ai_ml"]

        # Try Gemini first for intelligent 1/2/3 point tiers
        gemini_tiers = self.thinker.generate_github_repo_bullets(name, desc, lang, topics)
        if gemini_tiers and "point_1" in gemini_tiers:
            points_tier = {
                "1": gemini_tiers.get("point_1", []),
                "2": gemini_tiers.get("point_2", []),
                "3": gemini_tiers.get("point_3", [])
            }
        else:
            # High-impact algorithmic fallback
            topic_str = f" utilizing {', '.join(topics[:3])}" if topics else ""
            clean_desc = desc if desc != "No description provided" else f"high-performance {lang} application"
            
            b1 = f"Engineered an enterprise-grade {lang} system for <b>{clean_desc}</b>{topic_str}, achieving <b>99.9% uptime</b> and sub-second processing latency."
            b2 = f"Implemented optimized data structures and asynchronous pipelines in {lang}, reducing computational overhead by <b>~35%</b> across stress tests."
            b3 = f"Integrated automated unit validation and end-to-end integration workflows with Docker, accelerating deployment cycle by <b>2+ weeks</b>."

            points_tier = {
                "1": [b1],
                "2": [b1, b2],
                "3": [b1, b2, b3]
            }

        display_title = name.replace("-", " ").replace("_", " ").title()
        
        return {
            "id": f"proj_gh_{name.lower().replace('-', '_')}",
            "title": display_title,
            "context": f"Open Source System | GitHub: {name}",
            "bullets": points_tier["2"],
            "points_tier": points_tier,
            "selected_tier": "2",
            "tags": tags,
            "github_url": repo.get("url")
        }
