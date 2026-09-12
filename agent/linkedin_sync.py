import re
import os
from typing import Dict, Any, List, Optional
import pypdf

DEFAULT_LINKEDIN_URL = "https://www.linkedin.com/in/debanjan-kakati-5517891b7/"

class LinkedInSync:
    def __init__(self, profile_url: str = DEFAULT_LINKEDIN_URL):
        self.profile_url = profile_url

    def parse_pdf_export(self, pdf_path: str) -> Dict[str, Any]:
        """Parse a LinkedIn 'Save to PDF' exported file."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found at {pdf_path}")
        
        reader = pypdf.PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        return self.parse_text_content(full_text)

    def parse_text_content(self, text: str) -> Dict[str, Any]:
        """Parse raw text from LinkedIn profile copy-paste."""
        results = {
            "experiences": [],
            "projects": [],
            "skills": []
        }
        
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # Simple extraction heuristics for standard LinkedIn text copies
        curr_section = None
        for line in lines:
            line_lower = line.lower()
            if "experience" in line_lower and len(line) < 25:
                curr_section = "experience"
                continue
            elif "projects" in line_lower and len(line) < 25:
                curr_section = "projects"
                continue
            elif "skills" in line_lower and len(line) < 25:
                curr_section = "skills"
                continue
            
            if curr_section == "experience":
                if any(w in line for w in ["Intern", "Associate", "Engineer", "Lead", "Developer", "Analyst"]):
                    results["experiences"].append({
                        "role": line,
                        "raw_snippet": line
                    })
            elif curr_section == "projects":
                if len(line) > 5 and len(line) < 80 and not line.startswith("http"):
                    results["projects"].append({
                        "title": line,
                        "raw_snippet": line
                    })
            elif curr_section == "skills":
                if len(line) < 40 and not line.startswith("http"):
                    results["skills"].append(line)
        
        return results
