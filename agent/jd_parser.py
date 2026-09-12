import re
from typing import Dict, Any, List, Optional
from agent.llm_router import router

class JDParser:
    def __init__(self):
        pass

    def parse_job_description(self, jd_text: str, company: str = "", role: str = "") -> Dict[str, Any]:
        """
        Parses a Job Description into structured components:
        - hard_skills: must-have technical skills/languages
        - soft_skills: leadership, communication, agile, etc.
        - tools_frameworks: specific systems, databases, cloud providers
        - minimum_qualifications: degree, years experience
        - domain: quant, ai_ml, sde, chemical, product, finance
        """
        if not jd_text or len(jd_text.strip()) < 20:
            return self._heuristic_parse(f"{role} {company}")

        # Attempt LLM parse first if available
        llm_prompt = f"""
Parse the following Job Description into a structured JSON profile:
Company: {company}
Role: {role}
Job Description:
{jd_text}

Output pure JSON conforming to this schema:
{{
  "domain": "quant | ai_ml | sde | full_stack | finance | chemical | product | general",
  "hard_skills": ["skill1", "skill2"],
  "tools_frameworks": ["tool1", "tool2"],
  "soft_skills": ["leadership", "collaboration"],
  "target_keywords": ["keyword1", "keyword2"],
  "summary": "1-sentence summary of candidate requirements"
}}
"""
        result = router.generate_json(
            prompt=llm_prompt,
            system_prompt="You are an expert ATS parser.",
            purpose="jd_parsing"
        )
        if result and isinstance(result, dict) and "hard_skills" in result:
            return result

        # Fallback to deterministic heuristic parsing
        return self._heuristic_parse(jd_text, company, role)

    def _heuristic_parse(self, text: str, company: str = "", role: str = "") -> Dict[str, Any]:
        lower = f"{text} {company} {role}".lower()
        
        known_tech = [
            "python", "c++", "c", "java", "sql", "react", "fastapi", "docker", "git",
            "pytorch", "tensorflow", "kubernetes", "linux", "aws", "gcp", "azure",
            "pandas", "numpy", "scipy", "econometrics", "garch", "cvar", "dcf",
            "time-series", "nlp", "llm", "rag", "transformers", "opencv", "flask",
            "next.js", "node.js", "mongodb", "postgresql", "redis", "kafka", "matlab",
            "aspentech", "simulink", "mass balance", "catalysis", "refining"
        ]
        
        found_tech = [t for t in known_tech if re.search(r'\b' + re.escape(t) + r'\b', lower)]
        
        domain = "general"
        if any(w in lower for w in ["quant", "risk", "garch", "trading", "derivatives", "stochastic"]):
            domain = "quant"
        elif any(w in lower for w in ["ai", "ml", "machine learning", "deep learning", "nlp", "vision"]):
            domain = "ai_ml"
        elif any(w in lower for w in ["react", "full stack", "frontend", "backend", "web development"]):
            domain = "full_stack"
        elif any(w in lower for w in ["sde", "software engineer", "algorithms", "distributed systems"]):
            domain = "sde"
        elif any(w in lower for w in ["valuation", "financial model", "dcf", "equity research", "m&a"]):
            domain = "finance"
        elif any(w in lower for w in ["chemical", "reactor", "process engineering", "catalyst"]):
            domain = "chemical"
        elif any(w in lower for w in ["product manager", "roadmap", "agile", "scrum", "stakeholder"]):
            domain = "product"

        return {
            "domain": domain,
            "hard_skills": found_tech[:8],
            "tools_frameworks": [t for t in found_tech if t in ["docker", "git", "linux", "aws", "gcp", "fastapi", "react", "postgresql"]],
            "soft_skills": ["Cross-functional Leadership", "Analytical Problem Solving", "Effective Communication"],
            "target_keywords": found_tech[:15],
            "summary": f"Targeting {role or 'Candidate'} at {company or 'Target Firm'} focusing on {domain.replace('_', ' ').title()}."
        }

    def compute_gap_analysis(self, parsed_jd: Dict[str, Any], profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares JD requirements against the candidate's vault to identify:
        - matched_skills: present in profile skills or bullets
        - missing_skills: present in JD but absent in profile
        - recommended_vault_items: IDs of projects/experiences that best cover matched skills
        """
        all_profile_text = ""
        for cat, slist in profile_data.get("skills", {}).items():
            all_profile_text += " " + " ".join(slist)
        for proj in profile_data.get("projects", []):
            all_profile_text += " " + proj.get("title", "") + " " + " ".join(proj.get("bullets", [])) + " " + " ".join(proj.get("tags", []))
        for exp in profile_data.get("experiences", []):
            all_profile_text += " " + exp.get("role", "") + " " + exp.get("company", "") + " " + " ".join(exp.get("bullets", []))

        all_profile_lower = all_profile_text.lower()
        jd_skills = parsed_jd.get("hard_skills", []) + parsed_jd.get("tools_frameworks", [])
        
        matched = []
        missing = []
        for sk in set(jd_skills):
            if sk.lower() in all_profile_lower:
                matched.append(sk)
            else:
                missing.append(sk)

        match_rate = round(len(matched) / max(1, len(jd_skills)) * 100, 1) if jd_skills else 100.0

        return {
            "match_rate": match_rate,
            "matched_skills": matched,
            "missing_skills": missing,
            "jd_domain": parsed_jd.get("domain", "general")
        }

jd_parser = JDParser()
