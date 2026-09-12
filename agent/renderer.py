import os
import re
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from path_utils import get_base_dir, get_bundle_dir, get_writable_dir

TEMPLATE_DIR = os.path.join(get_bundle_dir(), "templates")
OUTPUT_DIR = get_writable_dir("output")

class ResumeRenderer:
    def __init__(self, template_dir: str = TEMPLATE_DIR, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception:
            pass
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.html_template = self.env.get_template("resume_template.html")

    def render_html(
        self,
        resume_data: Dict[str, Any],
        font_size: str = "9.5pt",
        line_height: str = "1.15",
        margin_v: str = "0.38in",
        margin_h: str = "0.48in"
    ) -> str:
        data = dict(resume_data)
        data["font_size"] = font_size
        data["line_height"] = line_height
        data["margin_v"] = margin_v
        data["margin_h"] = margin_h
        return self.html_template.render(**data)

    def escape_latex(self, text: str) -> str:
        """Escape LaTeX special characters."""
        text = re.sub(r'<b>(.*?)</b>', r'\\textbf{\1}', text)
        text = re.sub(r'<strong>(.*?)</strong>', r'\\textbf{\1}', text)
        text = text.replace('&ndash;', '--').replace('&mdash;', '---')
        text = text.replace('&rarr;', '$\\rightarrow$').replace('&minus;', '-')
        text = text.replace('&amp;', '\\&')
        text = text.replace('%', '\\%').replace('$', '\\$').replace('_', '\\_')
        text = text.replace('₹', 'Rs. ')
        text = text.replace('#', '\\#')
        return text

    def render_latex(
        self,
        resume_data: Dict[str, Any],
        font_size: str = "10pt",
        margin: str = "0.42in"
    ) -> str:
        info = resume_data["personal_info"]
        target = resume_data.get("target_title", "Resume")

        pt_size = font_size.replace("pt", "") if "pt" in font_size else "10"
        try:
            pt_int = int(round(float(pt_size)))
            pt_val = f"{pt_int}pt"
        except:
            pt_val = "10pt"

        tex = [
            rf"\documentclass[{pt_val},a4paper]{{article}}",
            r"\usepackage[utf8]{inputenc}",
            rf"\usepackage[margin={margin}]{{geometry}}",
            r"\usepackage{times}",
            r"\usepackage{hyperref}",
            r"\usepackage{enumitem}",
            r"\usepackage{titlesec}",
            r"\usepackage{xcolor}",
            r"\hypersetup{colorlinks=true, linkcolor=blue, urlcolor=blue}",
            r"\pagestyle{empty}",
            r"\setlist[itemize]{leftmargin=*, nosep, topsep=1pt, itemsep=1.5pt}",
            r"\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}[\titlerule]",
            r"\titlespacing*{\section}{0pt}{5pt}{2pt}",
            r"\begin{document}",
            "",
            r"\begin{center}",
            rf"  {{\LARGE \textbf{{{info['name']}}}}} \\ \vspace{{2pt}}",
            rf"  \href{{mailto:{info['email']}}}{{{info['email']}}} $|$ {info['phone']} $|$ \href{{{info['linkedin']}}}{{LinkedIn}} $|$ \href{{{info['github']}}}{{GitHub}}",
            r"\end{center}",
            r"\vspace{-6pt}",
            "",
            r"\section{Education}",
        ]

        for edu in resume_data["education"]:
            gpa_part = f" $|$ CGPA: {edu['gpa']}" if edu.get("gpa") else ""
            deg = self.escape_latex(edu['degree'])
            inst = self.escape_latex(edu['institution'])
            dur = edu['duration']
            tex.append(rf"\noindent \textbf{{{inst}}} \hfill \textbf{{{dur}}} \\")
            tex.append(rf"\textit{{{deg}{gpa_part}}} \vspace{{2pt}}")

        tex.append("")
        tex.append(r"\section{Relevant Coursework}")
        tex.append(r"\begin{itemize}")
        for cw in resume_data["coursework"]:
            tex.append(rf"  \item \textbf{{{self.escape_latex(cw['category'])}}}: {self.escape_latex(cw['entries'])}")
        tex.append(r"\end{itemize}")

        tex.append("")
        tex.append(r"\section{Skills}")
        tex.append(r"\begin{itemize}")
        for sk in resume_data["skills"]:
            tex.append(rf"  \item \textbf{{{self.escape_latex(sk['category'])}}}: {self.escape_latex(sk['entries'])}")
        tex.append(r"\end{itemize}")

        tex.append("")
        tex.append(r"\section{Experience}")
        for exp in resume_data["experiences"]:
            tex.append(rf"\noindent \textbf{{{self.escape_latex(exp['role'])}}} \hfill \textbf{{{exp['duration']}}} \\")
            tex.append(rf"\textit{{{self.escape_latex(exp['company'])}}} \hfill \textit{{{exp['location']}}}")
            tex.append(r"\begin{itemize}")
            for b in exp["bullets"]:
                tex.append(rf"  \item {self.escape_latex(b)}")
            tex.append(r"\end{itemize}")
            tex.append(r"\vspace{2pt}")

        tex.append("")
        tex.append(r"\section{Projects}")
        for proj in resume_data["projects"]:
            ctx = f" --- {self.escape_latex(proj['context'])}" if proj.get("context") else ""
            tex.append(rf"\noindent \textbf{{{self.escape_latex(proj['title'])}}}{ctx}")
            tex.append(r"\begin{itemize}")
            for b in proj["bullets"]:
                tex.append(rf"  \item {self.escape_latex(b)}")
            tex.append(r"\end{itemize}")
            tex.append(r"\vspace{2pt}")

        if resume_data.get("patents_certifications"):
            tex.append("")
            tex.append(r"\section{Patent \& Certifications}")
            tex.append(r"\begin{itemize}")
            for pc in resume_data["patents_certifications"]:
                tex.append(rf"  \item \textbf{{{self.escape_latex(pc['type'])}}}: {self.escape_latex(pc['title'])} --- {self.escape_latex(pc['details'])}")
            tex.append(r"\end{itemize}")

        if resume_data.get("pors_achievements"):
            tex.append("")
            tex.append(r"\section{Position of Responsibility \& Achievements}")
            tex.append(r"\begin{itemize}")
            for pa in resume_data["pors_achievements"]:
                tex.append(rf"  \item \textbf{{{self.escape_latex(pa['title'])}}}: {self.escape_latex(pa['details'])}")
            tex.append(r"\end{itemize}")

        tex.append("")
        tex.append(r"\end{document}")
        return "\n".join(tex)

    def save_outputs(self, prefix: str, resume_data: Dict[str, Any], **kwargs) -> Dict[str, str]:
        html_content = self.render_html(resume_data, **kwargs)
        tex_content = self.render_latex(resume_data)

        html_path = os.path.join(self.output_dir, f"{prefix}.html")
        tex_path = os.path.join(self.output_dir, f"{prefix}.tex")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        return {"html": html_path, "tex": tex_path}
