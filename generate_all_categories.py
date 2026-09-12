import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from agent.tailor_agent import TailorAgent, CATEGORY_CONFIGS
from agent.renderer import ResumeRenderer

def generate_all():
    tailor = TailorAgent()
    renderer = ResumeRenderer()

    categories = ["quant", "ai_ml", "full_stack", "product", "finance", "chemical"]
    filenames = {
        "quant": "Resume_Quant_Researcher",
        "ai_ml": "Resume_AIML_Engineer",
        "full_stack": "Resume_Full_Stack_Developer",
        "product": "Resume_Product_Management",
        "finance": "Resume_Finance_Corporate",
        "chemical": "Resume_Chemical_Energy_Shell"
    }

    print("Generating resumes for all 6 categories...")
    results = {}
    for cat in categories:
        data = tailor.tailor_resume(category=cat)
        prefix = filenames[cat]
        paths = renderer.save_outputs(prefix, data)
        results[cat] = paths
        print(f"✅ Generated {cat.upper()}:")
        print(f"   HTML: {paths['html']}")
        print(f"   TeX:  {paths['tex']}")

    print("\nAll 6 category resumes generated successfully!")
    return results

if __name__ == "__main__":
    generate_all()
