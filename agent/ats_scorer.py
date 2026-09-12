import re
from typing import Dict, Any, List

STRONG_ACTION_VERBS = {
    "engineered", "architected", "developed", "spearheaded", "optimized",
    "implemented", "designed", "formulated", "deployed", "automated",
    "accelerated", "modeled", "orchestrated", "quantified", "delivered",
    "scaled", "analyzed", "benchmarked", "synthesized", "executed"
}

WEAK_VERBS = {
    "worked on", "helped", "assisted", "responsible for", "participated in",
    "handled", "attempted", "learned", "tried"
}

class ATSScorer:
    def score_resume(
        self,
        resume_data: Dict[str, Any],
        jd_keywords: List[str] = None
    ) -> Dict[str, Any]:
        """
        Computes a comprehensive ATS parseability & impact score (0 to 100).
        """
        suggestions = []
        breakdown = {
            "keywords": 0,       # Max 35
            "metrics": 0,        # Max 25
            "action_verbs": 0,   # Max 20
            "formatting": 0      # Max 20
        }

        # 1. Formatting & Section Completeness (Max 20)
        format_score = 0
        p_info = resume_data.get("personal_info", {})
        if p_info.get("name") and p_info.get("email") and p_info.get("phone"):
            format_score += 5
        else:
            suggestions.append("Ensure header contains full name, professional email, and phone number.")

        if resume_data.get("education"):
            format_score += 5
        if resume_data.get("experiences") or resume_data.get("projects"):
            format_score += 5
        if resume_data.get("skills"):
            format_score += 5
        breakdown["formatting"] = format_score

        # Collect all bullets
        all_bullets = []
        for exp in resume_data.get("experiences", []):
            all_bullets.extend(exp.get("bullets", []))
        for proj in resume_data.get("projects", []):
            all_bullets.extend(proj.get("bullets", []))

        # 2. Metrics & Quantification Score (Max 25)
        # Check for numbers, percentages, dollar signs, multipliers (3x), ms, bps
        metric_pattern = re.compile(r'(\b\d+(\.\d+)?%?|\$\d+|\b\d+x\b|\b\d+\s*ms\b|\bbps\b|<b>.*?</b>)', re.IGNORECASE)
        quantified_bullets = 0
        for b in all_bullets:
            if metric_pattern.search(b):
                quantified_bullets += 1

        if all_bullets:
            quant_ratio = quantified_bullets / len(all_bullets)
            breakdown["metrics"] = min(25, int(quant_ratio * 25))
            if quant_ratio < 0.7:
                suggestions.append(f"Only {int(quant_ratio*100)}% of bullets have quantified metrics. Aim for at least 75% with bold statistics.")
        else:
            breakdown["metrics"] = 0

        # 3. Action Verbs Score (Max 20)
        strong_verb_count = 0
        weak_verb_count = 0
        for b in all_bullets:
            clean_b = re.sub(r'<[^>]+>', '', b).strip()
            first_word = clean_b.split()[0].lower() if clean_b else ""
            if first_word in STRONG_ACTION_VERBS:
                strong_verb_count += 1
            for wv in WEAK_VERBS:
                if clean_b.lower().startswith(wv):
                    weak_verb_count += 1
                    suggestions.append(f"Replace passive opener '{wv}' with a strong action verb like 'Engineered' or 'Architected'.")

        if all_bullets:
            verb_ratio = strong_verb_count / len(all_bullets)
            breakdown["action_verbs"] = min(20, int(verb_ratio * 20))
            if verb_ratio < 0.6:
                suggestions.append("Start each bullet with a high-impact past-tense verb (e.g., Engineered, Spearheaded, Optimized).")
        else:
            breakdown["action_verbs"] = 0

        # 4. Keyword Match Score (Max 35)
        if jd_keywords:
            skills_val = resume_data.get("skills", [])
            skills_parts = []
            if isinstance(skills_val, dict):
                for cat, slist in skills_val.items():
                    skills_parts.append(str(cat) + " " + (" ".join(slist) if isinstance(slist, list) else str(slist)))
            elif isinstance(skills_val, list):
                for s in skills_val:
                    if isinstance(s, dict):
                        skills_parts.append(s.get("category", "") + " " + str(s.get("skills", "")))
                    elif isinstance(s, str):
                        skills_parts.append(s)

            full_resume_text = " ".join([
                p_info.get("name", ""),
                " ".join(skills_parts),
                " ".join(all_bullets)
            ]).lower()

            matched_kws = [kw for kw in jd_keywords if kw.lower() in full_resume_text]
            match_rate = len(matched_kws) / max(1, len(jd_keywords))
            breakdown["keywords"] = min(35, int(match_rate * 35))

            unmatched = [kw for kw in jd_keywords if kw.lower() not in full_resume_text][:5]
            if unmatched:
                suggestions.append(f"Missing high-frequency JD keywords: {', '.join(unmatched)}")
        else:
            # Default full marks for standard tailored profiles if no JD provided
            breakdown["keywords"] = 30

        total_score = sum(breakdown.values())

        # Grade classification
        if total_score >= 90:
            grade = "A+"
            status = "Elite ATS Ready"
        elif total_score >= 80:
            grade = "A"
            status = "Strong Match"
        elif total_score >= 70:
            grade = "B"
            status = "Good / Needs Minor Polish"
        else:
            grade = "C"
            status = "Needs Improvement"

        return {
            "total_score": total_score,
            "grade": grade,
            "status": status,
            "breakdown": breakdown,
            "suggestions": suggestions[:5]
        }

ats_scorer = ATSScorer()
