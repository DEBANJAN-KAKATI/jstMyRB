import os
import json
import re
from typing import Dict, Any, List, Optional

CANDIDATE_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp"
]

def clean_json_string(text: str) -> str:
    text = text.strip()
    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

class GeminiThinker:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    def think_and_tailor(self, company: str, role: str, jd: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini to analyze company culture, job description, and role expectations,
        then strategically selects and formulates the optimal 1-page resume configuration.
        """
        if not self.api_key:
            print("GeminiThinker: No API key set.")
            return None

        system_prompt = """
You are an elite Wall Street, Silicon Valley, and top-tier engineering Resume Strategist.
Your goal is to build a hyper-targeted, 1-PAGE resume configuration for Debanjan Kakati tailored to a specific Company, Role, and Job Description.
Debanjan is a B.E. Chemical (Hons.) student with Minor in Finance at BITS Pilani (Goa Campus).

CRITICAL RULES:
1. STRICT 1-PAGE FIT: Recommend exactly 3 to 4 projects maximum.
2. For each project, select whether 1, 2, or 3 points are best to keep white space minimal while ensuring it fits on 1 page.
3. Quantify results with bold HTML tags (<b>X%</b>, <b>$Y</b>, <b><Z ms</b>).
4. Highlight technical, quantitative, and business impact matching the target company's priorities.
5. Return strictly valid JSON conforming to the requested schema.
"""

        available_exps = [{'id': e['id'], 'role': e['role'], 'company': e['company']} for e in profile.get('experiences', [])]
        available_projs = [{'id': p['id'], 'title': p['title'], 'context': p.get('context')} for p in profile.get('projects', [])]
        available_skills = list(profile.get('skills', {}).keys())
        available_cw = list(profile.get('coursework', {}).keys())

        user_prompt = f"""
TARGET APPLICATION:
- Company: {company}
- Role: {role}
- Job Description:
{jd}

CANDIDATE PROFILE DATA:
- Available Experiences: {json.dumps(available_exps)}
- Available Projects: {json.dumps(available_projs)}
- Available Skill Categories: {json.dumps(available_skills)}
- Available Coursework Categories: {json.dumps(available_cw)}

TASK:
1. Analyze what {company} values most for {role}.
2. Select the top 2 experience IDs.
3. Select the top 3-4 most relevant project IDs.
4. For each project ID, specify point_count (1, 2, or 3) and provide tailored bullets highlighting synergy with {role}.
5. Select 2-3 coursework category keys.
6. Select 3 skill category keys from available categories.

Return output in pure JSON with this exact structure:
{{
  "reasoning": "2-3 sentences explaining the strategic positioning for {company} and {role}",
  "coursework_categories": ["cat1", "cat2"],
  "skill_categories": ["cat1", "cat2", "cat3"],
  "selected_experience_ids": ["id1", "id2"],
  "selected_project_ids": ["proj_id1", "proj_id2", "proj_id3"],
  "project_points_override": {{
      "proj_id1": 2,
      "proj_id2": 2,
      "proj_id3": 2
  }},
  "customized_project_bullets": {{
      "proj_id1": ["Tailored bullet 1 with <b>metrics</b>...", "Tailored bullet 2..."]
  }}
}}
"""

        # Try LLMRouter with auto/gemini provider first (with caching and cost logging)
        try:
            from agent.llm_router import router
            routed_res = router.generate_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                purpose="resume_tailoring"
            )
            if routed_res and isinstance(routed_res, dict) and "selected_project_ids" in routed_res:
                print("✓ LLMRouter generated strategic tailoring plan successfully.")
                return routed_res
        except Exception as re:
            print(f"LLMRouter attempt error: {re}")

        # 1. Try google.genai directly
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            for m in CANDIDATE_MODELS:
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2,
                            response_mime_type="application/json"
                        )
                    )
                    if response and response.text:
                        raw = clean_json_string(response.text)
                        data = json.loads(raw)
                        print(f"✓ Gemini thinking successful with model {m}")
                        return data
                except Exception as me:
                    print(f"Gemini model {m} attempt failed: {me}")
                    continue
        except Exception as ge:
            print(f"google.genai SDK invocation failed: {ge}")

        # 2. Fallback to google.generativeai
        try:
            import google.generativeai as gai
            gai.configure(api_key=self.api_key)
            for m in CANDIDATE_MODELS:
                try:
                    model = gai.GenerativeModel(
                        model_name=m,
                        system_instruction=system_prompt,
                        generation_config={"response_mime_type": "application/json", "temperature": 0.2}
                    )
                    resp = model.generate_content(user_prompt)
                    if resp and resp.text:
                        raw = clean_json_string(resp.text)
                        data = json.loads(raw)
                        print(f"✓ Gemini fallback thinking successful with model {m}")
                        return data
                except Exception as me:
                    print(f"google.generativeai model {m} attempt failed: {me}")
                    continue
        except Exception as fe:
            print(f"google.generativeai fallback failed: {fe}")

        return None

    def generate_github_repo_bullets(self, repo_name: str, desc: str, lang: str, topics: List[str]) -> Optional[Dict[str, List[str]]]:
        """
        Generates 1-point, 2-point, and 3-point tiers for a GitHub project using Gemini.
        """
        if not self.api_key:
            return None

        prompt = f"""
Generate 3 professional resume bullet variations for a GitHub project:
Project Name: {repo_name}
Description: {desc}
Language: {lang}
Topics: {', '.join(topics)}

Requirements:
- Tier 1 (1 point): A single high-impact comprehensive bullet summarizing architecture, technology stack, and performance metrics.
- Tier 2 (2 points): Two structured bullets (Bullet 1: Architecture/Algorithms, Bullet 2: Performance/Impact metrics).
- Tier 3 (3 points): Three dense, quantified bullets (System architecture, Algorithms/ML techniques, Production deployment/testing).

Return strictly JSON:
{{
  "point_1": ["One power bullet with bold metrics like <b>X%</b>"],
  "point_2": ["Bullet 1 with <b>bold tags</b>", "Bullet 2 with <b>bold tags</b>"],
  "point_3": ["Bullet 1 with <b>bold tags</b>", "Bullet 2 with <b>bold tags</b>", "Bullet 3 with <b>bold tags</b>"]
}}
"""
        # Try google.genai
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            for m in CANDIDATE_MODELS:
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2
                        )
                    )
                    if resp and resp.text:
                        return json.loads(clean_json_string(resp.text))
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback google.generativeai
        try:
            import google.generativeai as gai
            gai.configure(api_key=self.api_key)
            for m in CANDIDATE_MODELS:
                try:
                    model = gai.GenerativeModel(
                        model_name=m,
                        generation_config={"response_mime_type": "application/json", "temperature": 0.2}
                    )
                    resp = model.generate_content(prompt)
                    if resp and resp.text:
                        return json.loads(clean_json_string(resp.text))
                except Exception:
                    continue
        except Exception:
            pass

        return None
