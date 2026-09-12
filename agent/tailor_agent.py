import re
from typing import Dict, Any, List, Optional
from .profile_manager import ProfileManager
from .gemini_thinker import GeminiThinker
from .embeddings_engine import semantic_engine

CATEGORY_CONFIGS = {
    "quant": {
        "title": "Quantitative Researcher & Financial Risk",
        "keywords": ["quant", "risk", "econometrics", "garch", "cvar", "portfolio", "stochastic", "time-series", "valuation", "math", "trading", "finance"],
        "coursework_keys": ["quantitative", "finance"],
        "skill_categories": ["programming", "quant_methods", "data_systems"],
        "primary_tags": ["quant", "finance"],
        "preferred_projects": ["proj_systemic_risk", "proj_bitslens", "proj_paints_valuation", "proj_powergrid_corp", "proj_ice_melting"],
        "preferred_experiences": ["exp_intellipaat", "exp_pieds"],
        "preferred_pors": ["SAE Formula Bharat — Chassis Development Engineer"],
        "preferred_patents": ["Ice Melting Rate Prediction Model"]
    },
    "ai_ml": {
        "title": "Artificial Intelligence & Machine Learning Engineer",
        "keywords": ["ai", "ml", "deep learning", "nlp", "rag", "transformer", "computer vision", "cnn", "gnn", "grad-cam", "pytorch", "tensorflow", "langgraph"],
        "coursework_keys": ["computing_ai", "quantitative"],
        "skill_categories": ["programming", "ai_ml", "frameworks_web", "data_systems"],
        "primary_tags": ["ai_ml"],
        "preferred_projects": ["proj_advanced_rag", "proj_xai_retinopathy", "proj_freewind_aqi", "proj_bitslens", "proj_ice_melting"],
        "preferred_experiences": ["exp_intellipaat", "exp_shell"],
        "preferred_pors": ["Smart India Hackathon (SIH) — National Top 1% Finalist"],
        "preferred_patents": ["Ice Melting Rate Prediction Model", "Advanced Data Science & Artificial Intelligence"]
    },
    "sde": {
        "title": "Software Development Engineer (SDE) & Systems",
        "keywords": ["sde", "software", "algorithms", "full stack", "react", "fastapi", "docker", "web", "api", "node.js", "electron", "microservices", "sql", "git"],
        "coursework_keys": ["computing_ai", "quantitative"],
        "skill_categories": ["programming", "frameworks_web", "data_systems"],
        "primary_tags": ["full_stack", "sde"],
        "preferred_projects": ["proj_shell_hte", "proj_advanced_rag", "proj_jstpdf", "proj_bitslens"],
        "preferred_experiences": ["exp_shell", "exp_intellipaat"],
        "preferred_pors": ["Smart India Hackathon (SIH) — National Top 1% Finalist"],
        "preferred_patents": ["Advanced Data Science & Artificial Intelligence"]
    },
    "full_stack": {
        "title": "Full Stack Developer & Systems Engineer",
        "keywords": ["full stack", "react", "fastapi", "docker", "web", "api", "node.js", "electron", "frontend", "backend", "microservices", "sql"],
        "coursework_keys": ["computing_ai", "quantitative"],
        "skill_categories": ["programming", "frameworks_web", "data_systems"],
        "primary_tags": ["full_stack"],
        "preferred_projects": ["proj_shell_hte", "proj_advanced_rag", "proj_jstpdf", "proj_bitslens", "proj_kalpana_dashboard"],
        "preferred_experiences": ["exp_shell", "exp_intellipaat"],
        "preferred_pors": ["Smart India Hackathon (SIH) — National Top 1% Finalist"],
        "preferred_patents": ["Advanced Data Science & Artificial Intelligence"]
    },
    "ds": {
        "title": "Data Scientist & Analytics Specialist",
        "keywords": ["data science", "analytics", "statistics", "pandas", "numpy", "sql", "regression", "hypothesis", "power bi", "tableau", "forecasting"],
        "coursework_keys": ["quantitative", "computing_ai"],
        "skill_categories": ["programming", "data_systems", "ai_ml"],
        "primary_tags": ["ai_ml", "quant"],
        "preferred_projects": ["proj_bitslens", "proj_kalpana_dashboard", "proj_freewind_aqi", "proj_ice_melting"],
        "preferred_experiences": ["exp_intellipaat", "exp_pieds"],
        "preferred_pors": ["Indian Space Academy — Remote Sensing & GIS Training"],
        "preferred_patents": ["Ice Melting Rate Prediction Model"]
    },
    "product": {
        "title": "Product Management & Operations Lead",
        "keywords": ["product", "roadmap", "analytics", "operations", "stakeholder", "kpi", "growth", "agile", "venture", "market", "startup", "dashboard"],
        "coursework_keys": ["business_operations", "quantitative"],
        "skill_categories": ["programming", "data_systems", "frameworks_web"],
        "primary_tags": ["product"],
        "preferred_projects": ["proj_shell_hte", "proj_kalpana_dashboard", "proj_freewind_aqi", "proj_xai_retinopathy"],
        "preferred_experiences": ["exp_pieds", "exp_intellipaat", "exp_shell"],
        "preferred_pors": ["SAE Formula Bharat — Chassis Development Engineer", "Smart India Hackathon (SIH) — National Top 1% Finalist"],
        "preferred_patents": ["Ice Melting Rate Prediction Model"]
    },
    "finance": {
        "title": "Corporate Finance, Investment & Valuation Analyst",
        "keywords": ["corporate finance", "valuation", "dcf", "wacc", "3-statement", "capm", "m&a", "equity", "financial modelling", "accounting", "venture capital"],
        "coursework_keys": ["finance", "business_operations"],
        "skill_categories": ["programming", "quant_methods", "data_systems"],
        "primary_tags": ["finance", "quant"],
        "preferred_projects": ["proj_paints_valuation", "proj_powergrid_corp", "proj_systemic_risk", "proj_bitslens"],
        "preferred_experiences": ["exp_pieds", "exp_intellipaat"],
        "preferred_pors": ["SAE Formula Bharat — Chassis Development Engineer"],
        "preferred_patents": ["Ice Melting Rate Prediction Model"]
    },
    "chemical": {
        "title": "Chemical Engineering, Energy & Catalysis Specialist",
        "keywords": ["chemical", "catalysis", "reactor", "hte", "gc", "dha", "mass balance", "thermodynamics", "refining", "energy", "process control", "patent"],
        "coursework_keys": ["chemical_process", "quantitative"],
        "skill_categories": ["chemical_engineering", "programming", "data_systems"],
        "primary_tags": ["chemical"],
        "preferred_projects": ["proj_shell_hte", "proj_ice_melting", "proj_algae_manthan", "proj_freewind_aqi"],
        "preferred_experiences": ["exp_shell", "exp_intellipaat"],
        "preferred_pors": ["SAE Formula Bharat — Chassis Development Engineer"],
        "preferred_patents": ["Ice Melting Rate Prediction Model", "Advanced Data Science & Artificial Intelligence"]
    }
}

class TailorAgent:
    def __init__(self, profile_manager: Optional[ProfileManager] = None, gemini_thinker: Optional[GeminiThinker] = None):
        self.pm = profile_manager or ProfileManager()
        self.thinker = gemini_thinker or GeminiThinker()

    def _score_text(self, text: str, keywords: List[str]) -> float:
        text_lower = text.lower()
        score = 0.0
        for kw in keywords:
            if kw in text_lower:
                score += 1.0 + (0.5 if len(kw) > 5 else 0.0)
        return score

    def tailor_resume(
        self,
        category: str = "quant",
        company: str = "",
        role: str = "",
        custom_jd: str = "",
        project_tiers: Optional[Dict[str, str]] = None,
        experience_tiers: Optional[Dict[str, str]] = None,
        active_project_ids: Optional[List[str]] = None,
        active_experience_ids: Optional[List[str]] = None,
        active_skills: Optional[List[Dict[str, str]]] = None,
        use_gemini: bool = False
    ) -> Dict[str, Any]:
        """
        Builds a strictly 1-page tailored resume configuration.
        """
        profile = self.pm.get_all()

        # Auto-detect role category if user specified role, company, or custom JD
        detected_category = category
        full_query = f"{role} {company} {custom_jd}".lower().strip()
        if full_query:
            scores = {}
            for cat_key, cat_cfg in CATEGORY_CONFIGS.items():
                score = 0
                for kw in cat_cfg["keywords"]:
                    if kw in role.lower():
                        score += 5
                    elif kw in full_query:
                        score += 2
                scores[cat_key] = score
            best_cat, best_score = max(scores.items(), key=lambda x: x[1])
            if best_score >= 2:
                detected_category = best_cat

        config = CATEGORY_CONFIGS.get(detected_category, CATEGORY_CONFIGS["quant"])
        
        reasoning = ""
        gemini_plan = None

        # 1. If Gemini thinking requested and API key available
        if use_gemini and self.thinker.api_key and (company or role or custom_jd):
            print(f"Executing Gemini strategic thinking for {company} / {role}...")
            gemini_plan = self.thinker.think_and_tailor(company or detected_category, role or config["title"], custom_jd, profile)
            if gemini_plan and "reasoning" in gemini_plan:
                reasoning = gemini_plan["reasoning"]
                print(f"Gemini reasoning generated: {reasoning}")
            elif not gemini_plan:
                print("Gemini thinking returned None or failed.")

        # Aggregate keywords
        active_keywords = list(config["keywords"])
        if full_query:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', full_query.lower())
            freq = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            active_keywords = list(set(active_keywords + [w for w, _ in sorted_words[:15]]))

        # 2. Select Coursework
        coursework_lines = []
        cw_keys = config["coursework_keys"]
        if gemini_plan and "coursework_categories" in gemini_plan:
            g_cw = [k for k in gemini_plan["coursework_categories"] if k in profile.get("coursework", {})]
            if g_cw:
                cw_keys = g_cw

        for k in cw_keys:
            if k in profile["coursework"]:
                label = k.replace("_", " ").title()
                entries_str = ", ".join(profile["coursework"][k][:6])
                coursework_lines.append({"category": label, "entries": entries_str})

        # 3. Select Skills (top 3 lines, or user active_skills, or Gemini recommended)
        skill_lines = []
        if active_skills is not None:
            skill_lines = active_skills
        elif gemini_plan and "skill_categories" in gemini_plan:
            for sk_cat in gemini_plan["skill_categories"]:
                # find matching key in profile skills
                matched_key = None
                for k in profile.get("skills", {}).keys():
                    if k.lower() == sk_cat.lower() or k.replace('_', ' ').lower() == sk_cat.replace('_', ' ').lower():
                        matched_key = k
                        break
                if matched_key:
                    label = matched_key.replace("_", " ").title()
                    if label == "Quant Methods":
                        label = "Quantitative Methods"
                    elif label == "Ai Ml":
                        label = "AI & Machine Learning"
                    entries_str = ", ".join(profile["skills"][matched_key])
                    skill_lines.append({"category": label, "entries": entries_str})

        if not skill_lines:
            for sk_cat in config["skill_categories"][:3]:
                if sk_cat in profile.get("skills", {}):
                    label = sk_cat.replace("_", " ").title()
                    if label == "Quant Methods":
                        label = "Quantitative Methods"
                    elif label == "Ai Ml":
                        label = "AI & Machine Learning"
                    entries_str = ", ".join(profile["skills"][sk_cat])
                    skill_lines.append({"category": label, "entries": entries_str})

        # 4. Select Experiences
        all_exps = profile.get("experiences", [])
        selected_exps = []
        if active_experience_ids is not None:
            candidate_exps = [e for e in all_exps if e.get("id") in active_experience_ids]
        elif gemini_plan and "selected_experience_ids" in gemini_plan:
            g_exps = [e for e in all_exps if e.get("id") in gemini_plan["selected_experience_ids"]]
            candidate_exps = g_exps if g_exps else all_exps[:2]
        else:
            bm25_exps = {item.get("id"): score for item, score in semantic_engine.rank_items(full_query or " ".join(active_keywords), all_exps, top_k=len(all_exps))}
            scored_exps = []
            for exp in all_exps:
                tag_overlap = len(set(exp.get("tags", [])) & set(config["primary_tags"]))
                preferred_bonus = 3.0 if exp["id"] in config["preferred_experiences"] else 0.0
                kw_score = self._score_text(exp["role"] + " " + " ".join(exp.get("bullets", [])), active_keywords)
                sem_score = bm25_exps.get(exp.get("id"), 0.0)
                total_score = tag_overlap * 2.0 + preferred_bonus + kw_score + (sem_score * 0.5)
                scored_exps.append((total_score, exp))
            scored_exps.sort(key=lambda x: x[0], reverse=True)
            candidate_exps = [e for _, e in scored_exps[:2]]

        for exp in candidate_exps:
            exp_id = exp["id"]
            tier = "2"
            if experience_tiers and exp_id in experience_tiers:
                tier = str(experience_tiers[exp_id])
            elif "selected_tier" in exp:
                tier = str(exp["selected_tier"])

            bullets_dict = exp.get("points_tier", {})
            tier_int = max(1, int(tier)) if str(tier).isdigit() else 2
            bullets = bullets_dict.get(tier, exp.get("bullets", [])[:tier_int])

            selected_exps.append({
                "id": exp_id,
                "role": exp["role"],
                "company": exp["company"],
                "duration": exp["duration"],
                "location": exp["location"],
                "selected_tier": tier,
                "bullets": bullets
            })

        # 5. Select Projects
        all_projects = profile.get("projects", [])
        selected_projs = []
        if active_project_ids is not None:
            candidate_projs = [p for p in all_projects if p.get("id") in active_project_ids]
        elif gemini_plan and "selected_project_ids" in gemini_plan:
            g_projs = [p for p in all_projects if p.get("id") in gemini_plan["selected_project_ids"]]
            # if fewer than 3, fill with scored projects
            if len(g_projs) < 3:
                existing_ids = {p["id"] for p in g_projs}
                extra = [p for p in all_projects if p["id"] not in existing_ids and p["id"] in config["preferred_projects"]]
                g_projs.extend(extra[:3 - len(g_projs)])
            candidate_projs = g_projs
        else:
            bm25_projs = {item.get("id"): score for item, score in semantic_engine.rank_items(full_query or " ".join(active_keywords), all_projects, top_k=len(all_projects))}
            scored_projs = []
            for proj in all_projects:
                tag_overlap = len(set(proj.get("tags", [])) & set(config["primary_tags"]))
                preferred_bonus = 4.0 if proj["id"] in config["preferred_projects"] else 0.0
                kw_score = self._score_text(proj["title"] + " " + " ".join(proj.get("bullets", [])), active_keywords)
                sem_score = bm25_projs.get(proj.get("id"), 0.0)
                total_score = tag_overlap * 2.5 + preferred_bonus + kw_score + (sem_score * 0.7)
                scored_projs.append((total_score, proj))
            scored_projs.sort(key=lambda x: x[0], reverse=True)
            candidate_projs = [p for _, p in scored_projs[:4]]

        # Points overrides from Gemini if present
        g_pts_override = gemini_plan.get("project_points_override", {}) if gemini_plan else {}

        for idx, proj in enumerate(candidate_projs):
            proj_id = proj.get("id")
            tier = "2"
            if project_tiers and proj_id in project_tiers:
                tier = str(project_tiers[proj_id])
            elif proj_id in g_pts_override:
                tier = str(g_pts_override[proj_id])
            elif "selected_tier" in proj:
                tier = str(proj["selected_tier"])
            else:
                tier = "3" if idx == 0 else "2"

            bullets_dict = proj.get("points_tier", {})
            tier_int = max(1, int(tier)) if str(tier).isdigit() else 2
            bullets = bullets_dict.get(tier, proj.get("bullets", [])[:tier_int])

            # Apply tailored bullets from Gemini if available
            if gemini_plan and "customized_project_bullets" in gemini_plan:
                if proj_id in gemini_plan["customized_project_bullets"]:
                    custom_b = gemini_plan["customized_project_bullets"][proj_id]
                    if isinstance(custom_b, list) and custom_b:
                        bullets = custom_b

            selected_projs.append({
                "id": proj_id,
                "title": proj["title"],
                "context": proj.get("context", ""),
                "selected_tier": tier,
                "bullets": bullets
            })

        # 6. Patents & Certifications
        all_pc = profile.get("patents_certifications", [])
        selected_pc = [item for item in all_pc if any(t in item.get("tags", []) for t in config["primary_tags"])]
        if not selected_pc:
            selected_pc = all_pc[:2]
        else:
            selected_pc = selected_pc[:2]

        # 7. POR & Achievements
        all_pors = profile.get("pors_achievements", [])
        selected_pors = [item for item in all_pors if any(t in item.get("tags", []) for t in config["primary_tags"])]
        if not selected_pors:
            selected_pors = all_pors[:2]
        else:
            selected_pors = selected_pors[:2]

        return {
            "category": detected_category,
            "company": company,
            "role": role,
            "reasoning": reasoning,
            "target_title": config["title"] if not role else f"{role} ({company})" if company else role,
            "personal_info": profile["personal_info"],
            "education": profile["education"],
            "coursework": coursework_lines,
            "skills": skill_lines,
            "experiences": selected_exps,
            "projects": selected_projs,
            "patents_certifications": selected_pc,
            "pors_achievements": selected_pors
        }

    def get_role_recommendations(self, role_query: str) -> Dict[str, Any]:
        """
        Computes BM25 & semantic match score for every project and skill for a query.
        """
        profile = self.pm.get_all()
        query_words = re.findall(r'\b[a-zA-Z]{3,}\b', role_query.lower())
        all_projs = profile.get("projects", [])
        bm25_scores = {item.get("id"): score for item, score in semantic_engine.rank_items(role_query, all_projs, top_k=len(all_projs))}
        
        project_recs = []
        for p in all_projs:
            kw_score = self._score_text(p["title"] + " " + " ".join(p.get("tags", [])) + " " + " ".join(p.get("bullets", [])), query_words)
            sem_score = bm25_scores.get(p.get("id"), 0.0)
            total_score = kw_score + (sem_score * 0.8)
            project_recs.append({
                "id": p["id"],
                "title": p["title"],
                "tags": p.get("tags", []),
                "score": round(total_score, 2),
                "is_recommended": total_score > 1.2 or any(q in t for q in query_words for t in p.get("tags", []))
            })

        project_recs.sort(key=lambda x: x["score"], reverse=True)

        return {
            "query": role_query,
            "projects": project_recs
        }
