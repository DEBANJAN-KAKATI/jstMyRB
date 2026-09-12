import re
from typing import Dict, Any, List, Optional
from agent.ats_scorer import STRONG_ACTION_VERBS, WEAK_VERBS
from agent.llm_router import router

class BulletCritic:
    def critique_bullet(self, bullet_text: str) -> Dict[str, Any]:
        """
        Analyzes a single bullet against the Google XYZ formula:
        Accomplished [X] as measured by [Y], by doing [Z].
        """
        clean_text = re.sub(r'<[^>]+>', '', bullet_text).strip()
        words = clean_text.split()
        first_word = words[0].lower() if words else ""

        issues = []
        strengths = []

        # 1. Action verb check
        has_strong_verb = first_word in STRONG_ACTION_VERBS
        if has_strong_verb:
            strengths.append(f"Strong action verb: '{first_word.capitalize()}'")
        else:
            for wv in WEAK_VERBS:
                if clean_text.lower().startswith(wv):
                    issues.append(f"Starts with passive phrase '{wv}'.")
                    break
            if not issues:
                issues.append("Consider starting with a definitive action verb (e.g., Engineered, Formulated).")

        # 2. Metric / Number check
        has_metrics = bool(re.search(r'(\d+%|\$\d+|\d+x|\d+\s*ms|top\s*\d+|#\d+|\b\d+\b)', clean_text, re.IGNORECASE))
        if has_metrics:
            strengths.append("Quantified with measurable metrics.")
        else:
            issues.append("Missing quantifiable metrics or results (e.g., %, $, latency, scale).")

        # 3. Length & line fit
        char_len = len(clean_text)
        if char_len < 60:
            issues.append("Too short — may lack technical depth.")
        elif char_len > 240:
            issues.append("Too long — risk of wrapping to 3 lines and overflowing page.")
        else:
            strengths.append("Optimal length for 1-page resume density.")

        # Score out of 100
        score = 50
        if has_strong_verb:
            score += 25
        if has_metrics:
            score += 25
        if 80 <= char_len <= 220:
            score += 10
        score = min(100, max(0, score))

        return {
            "bullet": bullet_text,
            "score": score,
            "strengths": strengths,
            "issues": issues,
            "xyz_compliant": has_strong_verb and has_metrics
        }

    def ai_improve_bullet(self, bullet_text: str, role_context: str = "") -> Optional[str]:
        """
        Uses LLMRouter to rewrite the bullet into the strict Google XYZ formula with bold tags.
        """
        prompt = f"""
Rewrite this resume bullet point using Google's XYZ formula:
'Accomplished [X] as measured by [Y], by doing [Z]'

Context / Target Role: {role_context or 'Software / Quant / ML Engineering'}
Original Bullet:
{bullet_text}

Rules:
1. Start with a powerful past-tense action verb (Engineered, Architected, Spearheaded, Optimized).
2. Wrap key metrics, numbers, and core technologies in <b> tags (e.g. <b>34% latency reduction</b>, <b>Python</b>).
3. Return ONLY the rewritten bullet point text as a single string. No quotation marks or explanations.
"""
        improved = router.generate_text(
            prompt=prompt,
            purpose="bullet_polishing",
            temperature=0.2
        )
        return improved.strip() if improved else None

bullet_critic = BulletCritic()
