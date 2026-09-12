import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader
from agent.llm_router import router
from agent.profile_manager import ProfileManager
from path_utils import get_base_dir, get_bundle_dir

class CoverLetterAgent:
    def __init__(self, profile_manager: Optional[ProfileManager] = None):
        self.pm = profile_manager or ProfileManager()
        template_dirs = [
            os.path.join(get_base_dir(), "templates"),
            os.path.join(get_bundle_dir(), "templates")
        ]
        self.env = Environment(loader=FileSystemLoader(template_dirs))

    def generate_cover_letter(
        self,
        company: str,
        role: str,
        jd_text: str = "",
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Generates structured cover letter content and renders HTML.
        """
        profile = self.pm.get_all()
        p_info = profile.get("personal_info", {})
        now_str = datetime.now().strftime("%B %d, %Y")

        paragraphs = []
        key_highlights = []
        closing = ""

        # Attempt LLM generation if requested
        if use_llm and (router.get_api_key("gemini") or router.get_api_key("openai") or router.get_api_key("anthropic")):
            llm_result = self._generate_with_llm(company, role, jd_text, profile)
            if llm_result:
                paragraphs = llm_result.get("paragraphs", [])
                key_highlights = llm_result.get("key_highlights", [])
                closing = llm_result.get("closing", "")

        # Fallback to smart rule-based template
        if not paragraphs:
            paragraphs, key_highlights, closing = self._generate_rule_based(company, role, jd_text, profile)

        # Render HTML
        template = self.env.get_template("cover_letter_template.html")
        html_output = template.render(
            candidate_name=p_info.get("name", "Debanjan Kakati"),
            candidate_email=p_info.get("email", "debanjan.kakati@gmail.com"),
            candidate_phone=p_info.get("phone", "+91 93657 56123"),
            candidate_linkedin=p_info.get("linkedin", "https://linkedin.com/in/debanjan-kakati-5517891b7/"),
            candidate_github=p_info.get("github", "https://github.com/DEBANJAN-KAKATI"),
            current_date=now_str,
            company=company or "the Hiring Organization",
            role=role or "Engineering / Quantitative Associate",
            paragraphs=paragraphs,
            key_highlights=key_highlights,
            closing_paragraph=closing
        )

        return {
            "html": html_output,
            "paragraphs": paragraphs,
            "key_highlights": key_highlights,
            "closing": closing
        }

    def _generate_with_llm(self, company: str, role: str, jd_text: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt = f"""
Write a hyper-personalized, executive cover letter for Debanjan Kakati applying to {company} for the role of {role}.
Candidate Background:
- Degree: B.E. Chemical Engineering (Hons.) + Minor in Finance at BITS Pilani (Goa Campus).
- Core Strengths: Full-stack systems (React/FastAPI/Docker), AI/ML & RAG architectures, High-Throughput Automation (Shell), and Quantitative Valuation / Risk Modeling.
- Key Wins: Shell R&D HTE automation reducing experiment cycles by 70%, Smart India Hackathon (SIH) National Finalist (Top 1%), Patents on Ice Melting Prediction & XAI for Retinopathy.

Job Description:
{jd_text[:1500]}

Rules:
- High caliber, authentic, and persuasive tone matching elite quantitative finance / tech firms.
- 3 clear paragraphs:
  1. Compelling hook showing passion for {company}'s specific mission and why this candidate is uniquely suited.
  2. Deep dive into 2 quantifiable technical accomplishments directly relevant to {role}.
  3. Culture & collaborative alignment showing cross-functional leadership.
- 2-3 concise bullet points summarizing standout achievements.
- 1 concise closing paragraph with a proactive call to action.

Return pure JSON:
{{
  "paragraphs": ["Paragraph 1...", "Paragraph 2...", "Paragraph 3..."],
  "key_highlights": ["Highlight 1 with <b>metrics</b>", "Highlight 2 with <b>metrics</b>"],
  "closing": "Closing paragraph..."
}}
"""
        return router.generate_json(
            prompt=prompt,
            system_prompt="You are an elite career strategist for top Wall Street & Silicon Valley roles.",
            purpose="cover_letter_generation"
        )

    def _generate_rule_based(self, company: str, role: str, jd_text: str, profile: Dict[str, Any]):
        comp = company or "your organization"
        r = role or "the engineering team"

        p1 = f"I am writing to express my enthusiastic interest in the <b>{r}</b> role at <b>{comp}</b>. As a dual-disciplined engineering student completing a B.E. in Chemical Engineering (Hons.) with a Minor in Finance at <b>BITS Pilani (Goa Campus)</b>, I combine rigorous mathematical modeling, high-throughput systems engineering, and modern full-stack development to build resilient, data-driven solutions."
        
        p2 = f"At <b>Shell</b>, I engineered an automated processing suite using Python, COM, and Streamlit for High-Throughput Experimentation (HTE), eliminating manual GC report consolidation and saving <b>over 20 engineering hours weekly</b>. Concurrently, as a <b>National Top 1% Finalist at Smart India Hackathon (SIH)</b>, I spearheaded an AI-driven disaster response system selected among 50,000+ competitors nationwide. My project portfolio spans production-grade multi-agent RAG pipelines, distributed valuation platforms, and explainable deep learning models."

        p3 = f"What excites me most about <b>{comp}</b> is your commitment to technical excellence and solving mission-critical challenges. My interdisciplinary background enables me to navigate complex problem spaces seamlessly—whether deploying low-latency backend microservices, tuning predictive algorithms, or translating analytical insights into measurable business value."

        highlights = [
            "<b>High-Throughput Engineering (Shell):</b> Automated catalyst data pipelines, reducing cycle times by <b>70%</b> with 100% precision.",
            "<b>Advanced AI & Systems Architecture:</b> Built production RAG frameworks, vision explainability pipelines (Grad-CAM), and financial risk engines (GARCH/CVaR).",
            "<b>Leadership & Execution:</b> National Top 1% Finalist at Smart India Hackathon; Chassis Engineer for SAE Formula Bharat electric vehicle."
        ]

        closing = f"I would welcome the opportunity to discuss how my technical foundation, competitive drive, and interdisciplinary mindset can contribute to high-impact initiatives at <b>{comp}</b>. Thank you for your time and consideration."

        return [p1, p2, p3], highlights, closing

cover_letter_agent = CoverLetterAgent()
