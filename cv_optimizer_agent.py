#!/usr/bin/env python3
"""
cv_optimizer_agent.py
Engine module: PDF generation, text extraction, and Gemini AI analysis.
Imported by app.py (Streamlit) — no CLI entry point.
"""

import io
import json
import os
import re
import time
from datetime import date
from pathlib import Path

import pdfplumber
from groq import Groq

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    Flowable, KeepTogether, HRFlowable,
)
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ── Page geometry ───────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_LR = 1.8 * cm
MARGIN_TB = 1.5 * cm
TEXT_W    = PAGE_W - 2 * MARGIN_LR

# ── Colours ─────────────────────────────────────────────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')


# ── Font registration ───────────────────────────────────────────────────────────
def _register_fonts():
    """Use Arial (Windows) for full Unicode; fall back to Helvetica on Linux."""
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    regular   = os.path.join(win_fonts, 'arial.ttf')
    bold      = os.path.join(win_fonts, 'arialbd.ttf')
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('CV',      regular))
        pdfmetrics.registerFont(TTFont('CV-Bold', bold))
        registerFontFamily('CV', normal='CV', bold='CV-Bold',
                           italic='CV', boldItalic='CV-Bold')
        return 'CV', 'CV-Bold'
    registerFontFamily('Helvetica', normal='Helvetica', bold='Helvetica-Bold',
                       italic='Helvetica-Oblique', boldItalic='Helvetica-BoldOblique')
    return 'Helvetica', 'Helvetica-Bold'

FONT, FONT_BOLD = _register_fonts()

# ── Pipeline constants ───────────────────────────────────────────────────────────
_JD_SUMMARY_WORDS = 400   # truncate JD for experience batch calls to save TPM
_EXP_BATCH_SIZE   = 2     # roles per bullet-generation call


# ── Custom flowable: coloured section header ────────────────────────────────────
class SectionHeader(Flowable):
    HEIGHT = 19

    def __init__(self, text, width=TEXT_W):
        super().__init__()
        self.text   = text
        self.width  = width
        self.height = self.HEIGHT

    def draw(self):
        c = self.canv
        c.setFillColor(TEAL)
        c.rect(0, 3, 3.5, 13, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 10)
        c.drawString(9, 4, self.text.upper())
        c.setStrokeColor(HexColor('#DDDDDD'))
        c.setLineWidth(0.4)
        c.line(0, 0, self.width, 0)


# ── Paragraph styles factory ────────────────────────────────────────────────────
def make_styles(body_size=8.4):
    """Return a styles dict scaled to body_size. Fixed header sizes stay constant."""
    lead = body_size * 1.49

    def _s(**kw):
        defaults = dict(fontName=FONT, fontSize=body_size, textColor=DKGRY,
                        leading=lead, spaceAfter=0)
        defaults.update(kw)
        return ParagraphStyle('', **defaults)

    return {
        'name':      _s(fontName=FONT_BOLD, fontSize=22, textColor=NAVY,
                        leading=26, spaceAfter=2),
        'subtitle':  _s(fontSize=9.8, textColor=TEAL, leading=13, spaceAfter=3),
        'contact':   _s(fontSize=8.1, textColor=MDGRY, leading=11, spaceAfter=0),
        'accroche':  _s(fontSize=body_size, alignment=TA_JUSTIFY, leading=lead),
        'role':      _s(fontName=FONT_BOLD, fontSize=9.3, textColor=NAVY,
                        leading=12, spaceAfter=1),
        'employer':  _s(fontSize=body_size - 0.1, textColor=MDGRY,
                        leading=lead - 1.5, spaceAfter=3),
        'bullet':    _s(fontSize=body_size - 0.1, alignment=TA_JUSTIFY,
                        leading=lead, leftIndent=11, bulletIndent=0, spaceAfter=2.5),
        'oneliner':  _s(fontSize=body_size - 0.2, textColor=MDGRY,
                        leading=lead - 1, spaceAfter=3),
        'skill_cat': _s(fontName=FONT_BOLD, fontSize=body_size, textColor=NAVY,
                        leading=lead - 1, spaceAfter=0),
        'skill_val': _s(fontSize=body_size - 0.2, alignment=TA_JUSTIFY,
                        leading=lead, spaceAfter=4),
        'edu_title': _s(fontName=FONT_BOLD, fontSize=9, textColor=DKGRY,
                        leading=12, spaceAfter=1),
        'edu_sub':   _s(fontSize=body_size - 0.2, textColor=MDGRY,
                        leading=lead - 1, spaceAfter=5),
        'lang':      _s(fontSize=body_size, leading=lead, spaceAfter=2),
        'project':   _s(fontSize=body_size - 0.2, alignment=TA_JUSTIFY,
                        leading=lead, leftIndent=11, bulletIndent=0, spaceAfter=2.5),
        'cl_body':   _s(fontSize=body_size, alignment=TA_JUSTIFY,
                        leading=lead + 1, spaceAfter=6),
        'cl_meta':   _s(fontSize=body_size, textColor=MDGRY, leading=lead, spaceAfter=2),
    }


# ── Content helpers ─────────────────────────────────────────────────────────────
def make_accroche(text, kpi_line, S):
    body = text + ('<br/><br/>' + kpi_line if kpi_line else '')
    inner = Paragraph(body, S['accroche'])
    t = Table([[inner]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LTBLUE),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 9),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 9),
    ]))
    return t


def make_exp_entry(title, company, period, location, bullets, is_oneliner, S):
    """Returns a list of flowables for one experience entry."""
    # Build the employer details line: "Company, Location — Period"
    details_parts = [p for p in (company, location) if p]
    details = ', '.join(details_parts)
    if period:
        details += f'\u2002\u2014\u2002{period}'

    if is_oneliner:
        return [Paragraph(f'{title}\u2002\u2014\u2002{details}', S['oneliner'])]

    elems = [
        KeepTogether([
            Paragraph(title, S['role']),
            Paragraph(details, S['employer']),
        ])
    ]
    for b in (bullets or []):
        elems.append(Paragraph('<bullet>\u2022</bullet>' + b, S['bullet']))
    elems.append(Spacer(1, 5))
    return elems


def make_skill_row(cat, val, S):
    t = Table(
        [[Paragraph(cat + '\u00a0:', S['skill_cat']),
          Paragraph(val, S['skill_val'])]],
        colWidths=[3.6 * cm, TEXT_W - 3.6 * cm],
    )
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return t


def _slugify(s: str) -> str:
    """Convert a string to a safe filename slug (Windows-compatible)."""
    s = (s or '').strip().lower()
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    s = re.sub(r'\s+', '_', s)
    return (s or 'unknown')[:80]


def _truncate_jd(jd: str, max_words: int = _JD_SUMMARY_WORDS) -> str:
    """Truncate job description to max_words to reduce TPM per batch call."""
    words = jd.split()
    return ' '.join(words[:max_words]) + ('\u2026' if len(words) > max_words else '')


def format_contact_line(contact: dict) -> str:
    """Build HTML-enabled contact line with clickable links."""
    parts = []
    for key in ('email', 'phone', 'location'):
        val = (contact.get(key) or '').strip()
        if val:
            parts.append(val)
    for key in ('linkedin', 'github', 'youtube'):
        url = (contact.get(key) or '').strip()
        if url:
            display = url.replace('https://', '').replace('http://', '').rstrip('/')
            parts.append(f'<a href="{url}" color="#1B9AAA">{display}</a>')
    sep = '\u2002\u2022\u2002'
    return sep.join(parts)


# ── System prompts ──────────────────────────────────────────────────────────────
CV_ADVISOR_SYSTEM = """
You are an advanced ATS system and expert senior recruiter.

Your task: analyse the provided CV against the job description and return a JSON object.

1. Detect the language of the job description ("language" field).
2. Score each skill from the JD using a strategic relevance score (1–10).
3. Identify transferable skills where exact matches are missing.
4. Produce initial ATS score and projected ATS score after optimisation.
5. List the top 5 actionable recommendations to reach 9+/10.
6. Produce section label names translated into the language of the job description.

Be HYPERCRITICAL in scoring. Most CVs score 4–6 initially. 8+ requires exceptional
keyword match, quantified achievements, and role-specific language. Do not inflate scores.
""".strip()

CV_STATIC_SYSTEM = """
You are an expert CV writer. Your task has two parts:

PART A — Rewrite the non-experience sections (summary, skills, education, languages,
certifications, projects, contact) to maximise ATS alignment with the job description.

PART B — Extract a skeleton of EVERY experience entry from the original CV:
role title, company name, period, location, and whether it is a one-liner role.
Do NOT write any bullet points — output empty arrays only.

RULES:
- Preserve exact dates, locations, and names from the original CV.
- Write in: {language}
- No fabrication. No truncation. Complete JSON only.
""".strip()

CV_BULLETS_SYSTEM = """
You are an expert CV writer and ATS specialist. For each experience entry provided,
write 3–5 ATS-optimised bullet points by integrating keywords from the job description
into the candidate's real achievements found in the original CV.

ABSOLUTE RULES:
- Copy role, company, period, location verbatim from the input — do not alter them.
- Wrap every number, percentage, and metric in <b>…</b> HTML tags.
  Examples: <b>40%</b>, <b>14+ years</b>, <b>~30%</b>, <b>25%</b>
- Do NOT invent metrics, companies, or skills not in the original CV.
- is_oneliner=true entries must have bullets=[].
- Write in: {language}
- Output ONLY the raw JSON object — no commentary, no code fences.
""".strip()

COVER_LETTER_SYSTEM = """
You are a world-class cover letter writer. Your cover letters are narrative-driven,
bold, and submission-ready. You never use generic openings.

Rules:
- Write ONLY in the language explicitly specified in the user message.
- 250–400 words. No placeholders. No emojis. No bold/italic formatting.
- Hook: never start with "I am applying...", "I am excited...", or "With X years of experience...".
  Instead open with a bold statement, insight, or provocative question tied to the company's
  mission or a key industry challenge.
- Body: weave achievements into a narrative that answers "Why this candidate for this role?".
  Reference concrete outcomes from the CV. Mirror the tone and keywords of the job description.
- Closing: confident and proactive — not "I look forward to hearing from you."
- Address properly: use the recruiter's name/title from the JD if available, otherwise use
  the generic team salutation in the correct language.
- Final signature: candidate's full name as it appears in the CV.
- Include today's date in the correct format for the target language/country.
- Verify: no [placeholders], no generic phrases, fully personalised.
""".strip()


# ── JSON schema — Pass 1: analysis only ─────────────────────────────────────────
CV_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": [
        "language", "ats_score_initial", "ats_score_improved",
        "skill_matrix", "recommendations", "section_labels"
    ],
    "properties": {
        "language": {
            "type": "string",
            "description": "Language of the job description (e.g. 'French', 'English')"
        },
        "ats_score_initial": {
            "type": "integer",
            "description": "Initial ATS keyword match score out of 10"
        },
        "ats_score_improved": {
            "type": "integer",
            "description": "Projected ATS score after applying recommendations, out of 10"
        },
        "skill_matrix": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "skill", "present_in_cv", "transferable",
                    "transferable_skill", "strategic_score", "score_reason"
                ],
                "properties": {
                    "skill":              {"type": "string"},
                    "present_in_cv":      {"type": "boolean"},
                    "transferable":       {"type": "boolean"},
                    "transferable_skill": {"type": "string"},
                    "strategic_score":    {"type": "integer"},
                    "score_reason":       {"type": "string"}
                }
            }
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top actionable recommendations to reach 9+/10 ATS score"
        },
        "section_labels": {
            "type": "object",
            "required": [
                "experience", "skills", "education",
                "languages", "certifications", "projects"
            ],
            "properties": {
                "experience":     {"type": "string"},
                "skills":         {"type": "string"},
                "education":      {"type": "string"},
                "languages":      {"type": "string"},
                "certifications": {"type": "string"},
                "projects":       {"type": "string"}
            }
        }
    }
}

# ── JSON schema — Pass 2: static sections + experience skeleton ──────────────────
STATIC_CV_SCHEMA = {
    "type": "object",
    "required": [
        "name", "title", "contact", "summary", "summary_kpis",
        "skills", "education", "languages", "certifications", "projects",
        "experience_skeleton"
    ],
    "properties": {
        "name":  {"type": "string"},
        "title": {"type": "string"},
        "contact": {
            "type": "object",
            "properties": {
                "email":    {"type": "string"},
                "phone":    {"type": "string"},
                "location": {"type": "string"},
                "linkedin": {"type": "string"},
                "github":   {"type": "string"},
                "youtube":  {"type": "string"}
            }
        },
        "summary":      {"type": "string"},
        "summary_kpis": {"type": "string"},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["category", "value"],
                "properties": {
                    "category": {"type": "string"},
                    "value":    {"type": "string"}
                }
            }
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["degree", "institution_line", "period"],
                "properties": {
                    "degree":           {"type": "string"},
                    "institution_line": {"type": "string"},
                    "period":           {"type": "string"}
                }
            }
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "proficiency"],
                "properties": {
                    "name":        {"type": "string"},
                    "proficiency": {"type": "string"}
                }
            }
        },
        "certifications": {"type": "array", "items": {"type": "string"}},
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title"],
                "properties": {
                    "title":       {"type": "string"},
                    "period":      {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        },
        "experience_skeleton": {
            "type": "array",
            "description": "ALL roles from the original CV — every job, none omitted. No bullets.",
            "items": {
                "type": "object",
                "required": ["role", "company", "period", "location", "is_oneliner"],
                "properties": {
                    "role":        {"type": "string"},
                    "company":     {"type": "string"},
                    "period":      {"type": "string", "description": "e.g. '11/2022 - Present'"},
                    "location":    {"type": "string", "description": "e.g. 'Paris, France'"},
                    "is_oneliner": {"type": "boolean"}
                }
            }
        }
    }
}

# ── JSON schema — Passes 3…K: experience bullets per batch ───────────────────────
EXPERIENCE_BULLETS_SCHEMA = {
    "type": "object",
    "required": ["experience"],
    "properties": {
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["role", "company", "period", "location", "bullets", "is_oneliner"],
                "properties": {
                    "role":        {"type": "string"},
                    "company":     {"type": "string"},
                    "period":      {"type": "string"},
                    "location":    {"type": "string"},
                    "bullets":     {"type": "array", "items": {"type": "string"}},
                    "is_oneliner": {"type": "boolean"}
                }
            }
        }
    }
}


# ── PDF text extraction ─────────────────────────────────────────────────────────
def extract_cv_pdf(cv_source) -> tuple[str, int]:
    """Extract text and page count from a CV PDF.

    cv_source: Path or BytesIO.
    Returns (text, page_count).
    """
    with pdfplumber.open(cv_source) as pdf:
        page_count = len(pdf.pages)
        pages_text = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    full_text = '\n\n'.join(pages_text).strip()
    return full_text, page_count


# ── Groq: CV Analysis (two-pass) ────────────────────────────────────────────────
def _parse_json(raw: str) -> dict:
    """Strip optional code fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw.strip())
    return json.loads(raw)


def run_analysis(cv_text: str, jd_text: str, api_key: str) -> dict:
    """Skeleton-first pipeline: 4 passes to guarantee all roles are retained.

    Pass 1 (llama-3.1-8b-instant): ATS analysis — language, scores, skill matrix,
            recommendations, section labels. Uses a separate TPM pool.
    Pass 2 (llama-3.3-70b): Static sections (summary, skills, edu, etc.) +
            experience skeleton — role/company/period/location, NO bullets.
    Passes 3…K (llama-3.3-70b): Bullets for each batch of _EXP_BATCH_SIZE roles.
    Merge: full optimized_cv dict assembled in Python, same shape as before.
    """
    client    = Groq(api_key=api_key)
    jd_short  = _truncate_jd(jd_text)

    # ── Pass 1: Analysis (8b-instant — separate TPM pool, fast) ─────────────────
    r1 = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": CV_ADVISOR_SYSTEM},
            {"role": "user", "content": (
                f"<cv>\n{cv_text}\n</cv>\n\n"
                f"<job_description>\n{jd_text}\n</job_description>\n\n"
                "Analyse this CV against the job description. "
                f"Return a JSON object exactly matching this schema:\n"
                f"{json.dumps(CV_ANALYSIS_SCHEMA, ensure_ascii=False)}"
            )},
        ],
        response_format={"type": "json_object"},
        max_tokens=2000,
        temperature=0.01,
    )
    analysis = _parse_json(r1.choices[0].message.content)
    language = analysis.get('language', 'English')

    # ── Pass 2: Static sections + experience skeleton (70b) ─────────────────────
    r2 = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system",
             "content": CV_STATIC_SYSTEM.format(language=language)},
            {"role": "user", "content": (
                f"<original_cv>\n{cv_text}\n</original_cv>\n\n"
                f"<job_description>\n{jd_short}\n</job_description>\n\n"
                "Return a JSON object exactly matching this schema:\n"
                f"{json.dumps(STATIC_CV_SCHEMA, ensure_ascii=False)}"
            )},
        ],
        response_format={"type": "json_object"},
        max_tokens=3500,
        temperature=0.01,
    )
    static_cv = _parse_json(r2.choices[0].message.content)
    skeleton  = static_cv.pop('experience_skeleton', [])

    # ── Passes 3…K: Bullet generation in batches of _EXP_BATCH_SIZE ─────────────
    bulk_schema          = json.dumps(EXPERIENCE_BULLETS_SCHEMA, ensure_ascii=False)
    optimized_experience = []

    for i in range(0, len(skeleton), _EXP_BATCH_SIZE):
        chunk = skeleton[i : i + _EXP_BATCH_SIZE]
        if i > 0:
            time.sleep(3)   # pace 70b calls to stay under 12k TPM/min free tier
        try:
            r_exp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system",
                     "content": CV_BULLETS_SYSTEM.format(language=language)},
                    {"role": "user", "content": (
                        f"Roles to optimise:\n"
                        f"{json.dumps(chunk, ensure_ascii=False)}\n\n"
                        f"<original_cv>\n{cv_text}\n</original_cv>\n\n"
                        f"<job_keywords>\n{jd_short}\n</job_keywords>\n\n"
                        f"Return a JSON object exactly matching this schema:\n"
                        f"{bulk_schema}"
                    )},
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.01,
            )
            batch_result = _parse_json(r_exp.choices[0].message.content)
            optimized_experience.extend(batch_result.get('experience', chunk))
        except Exception:
            # Fallback: keep skeleton entries with empty bullets rather than crash
            for entry in chunk:
                optimized_experience.append({**entry, 'bullets': []})

    static_cv['experience'] = optimized_experience
    analysis['optimized_cv'] = static_cv
    return analysis


# ── Groq: Cover Letter ──────────────────────────────────────────────────────────
def run_cover_letter(cv_text: str, jd_text: str, language: str,
                     optimized_cv: dict, company: str, api_key: str) -> str:
    """Call Groq to generate a cover letter. Returns plain text."""
    client = Groq(api_key=api_key)
    summary = optimized_cv.get('summary', '')
    name    = optimized_cv.get('name', '')
    title   = optimized_cv.get('title', '')
    user_msg = (
        f"Write the cover letter in: {language}\n\n"
        f"Candidate: {name} — {title}\n\n"
        f"<cv_summary>\n{summary}\n</cv_summary>\n\n"
        f"<full_cv>\n{cv_text}\n</full_cv>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
        f"Company applying to: {company}\n"
        f"Today's date: {date.today().strftime('%d %B %Y')}\n\n"
        "Generate a submission-ready cover letter following all instructions in your system prompt. "
        "Return only the final cover letter text — no commentary, no step-by-step notes."
    )
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": COVER_LETTER_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
    )
    return response.choices[0].message.content.strip()


# ── CV story builder ────────────────────────────────────────────────────────────
def build_cv_story(opt_cv: dict, labels: dict, S: dict) -> list:
    """Build the ReportLab story (flowables) from the optimised CV dict."""
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    contact_line = format_contact_line(opt_cv.get('contact', {}))
    st += [
        Paragraph(opt_cv.get('name', ''), S['name']),
        Paragraph(opt_cv.get('title', ''), S['subtitle']),
        Spacer(1, 3),
        Paragraph(contact_line, S['contact']),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 7),
    ]

    # ── Summary / Accroche ───────────────────────────────────────────────────────
    summary     = opt_cv.get('summary') or ''
    summary_kpi = opt_cv.get('summary_kpis') or ''
    if summary:
        st.append(make_accroche(summary, summary_kpi, S))
        st.append(Spacer(1, 9))

    # ── Experience ───────────────────────────────────────────────────────────────
    experience = opt_cv.get('experience', [])
    if experience:
        st.append(SectionHeader(labels.get('experience', 'Professional Experience')))
        st.append(Spacer(1, 5))
        for entry in experience:
            for flowable in make_exp_entry(
                entry.get('role') or '',
                entry.get('company') or entry.get('company_line') or '',
                entry.get('period') or '',
                entry.get('location') or '',
                entry.get('bullets') or [],
                bool(entry.get('is_oneliner')),
                S,
            ):
                st.append(flowable)
        st.append(Spacer(1, 3))

    # ── Skills ───────────────────────────────────────────────────────────────────
    skills = opt_cv.get('skills', [])
    if skills:
        skills_block = [
            SectionHeader(labels.get('skills', 'Skills')),
            Spacer(1, 5),
        ]
        for sk in skills:
            skills_block.append(
                make_skill_row(sk.get('category') or '', sk.get('value') or '', S)
            )
        skills_block.append(Spacer(1, 8))
        st.append(KeepTogether(skills_block))

    # ── Education ────────────────────────────────────────────────────────────────
    education = opt_cv.get('education', [])
    if education:
        st.append(SectionHeader(labels.get('education', 'Education')))
        st.append(Spacer(1, 5))
        for edu in education:
            st.append(Paragraph(edu.get('degree') or '', S['edu_title']))
            inst = edu.get('institution_line') or ''
            period = edu.get('period') or ''
            inst_display = inst + (f'\u2002\u2014\u2002{period}' if period else '')
            st.append(Paragraph(inst_display, S['edu_sub']))

    # ── Languages ────────────────────────────────────────────────────────────────
    langs = opt_cv.get('languages', [])
    if langs:
        st.append(SectionHeader(labels.get('languages', 'Languages')))
        st.append(Spacer(1, 5))
        parts = []
        for lang in langs:
            if isinstance(lang, dict):
                name_part = (lang.get('name') or '').strip()
                level = (lang.get('proficiency') or '').strip()
                parts.append(f'<b>{name_part}</b>\u2002:\u2002{level}' if level else name_part)
            else:
                lang_str = str(lang)
                if ':' in lang_str:
                    name_part, level = lang_str.split(':', 1)
                    parts.append(f'<b>{name_part.strip()}</b>\u2002:\u2002{level.strip()}')
                else:
                    parts.append(lang_str)
        st.append(Paragraph('\u2002\u2022\u2002'.join(parts), S['lang']))
        st.append(Spacer(1, 8))

    # ── Certifications ───────────────────────────────────────────────────────────
    certs = opt_cv.get('certifications', [])
    if certs:
        st.append(SectionHeader(labels.get('certifications', 'Certifications')))
        st.append(Spacer(1, 5))
        for cert in certs:
            st.append(Paragraph('<bullet>\u2022</bullet>' + cert, S['project']))
        st.append(Spacer(1, 8))

    # ── Projects ─────────────────────────────────────────────────────────────────
    projects = opt_cv.get('projects', [])
    if projects:
        st.append(SectionHeader(labels.get('projects', 'Personal Projects')))
        st.append(Spacer(1, 5))
        for proj in projects:
            if isinstance(proj, dict):
                title = (proj.get('title') or '').strip()
                period = (proj.get('period') or '').strip()
                description = (proj.get('description') or '').strip()
                header = f'<b>{title}</b>' + (f'\u2002({period})' if period else '')
                st.append(Paragraph('<bullet>\u2022</bullet>' + header, S['project']))
                if description:
                    st.append(Paragraph(description, S['project']))
            else:
                st.append(Paragraph('<bullet>\u2022</bullet>' + str(proj), S['project']))

    return st


def _count_pdf_pages(buf: io.BytesIO) -> int:
    """Count pages in a BytesIO PDF buffer using pdfplumber."""
    buf.seek(0)
    with pdfplumber.open(buf) as pdf:
        return len(pdf.pages)


# ── CV PDF builder ──────────────────────────────────────────────────────────────
def build_cv_pdf(opt_cv: dict, labels: dict, target_pages: int) -> bytes:
    """Build the CV PDF, auto-scaling body font size to match target_pages.
    Returns PDF bytes."""
    font_sizes = [8.4, 8.0, 7.6, 7.2, 6.8]
    buf = io.BytesIO()

    for fs in font_sizes:
        S   = make_styles(body_size=fs)
        buf = io.BytesIO()
        doc = BaseDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN_LR,
            rightMargin=MARGIN_LR,
            topMargin=MARGIN_TB,
            bottomMargin=MARGIN_TB,
        )
        frame = Frame(
            MARGIN_LR, MARGIN_TB,
            TEXT_W, PAGE_H - 2 * MARGIN_TB,
            id='main', showBoundary=0,
        )
        doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
        doc.build(build_cv_story(opt_cv, labels, S))

        if _count_pdf_pages(buf) <= target_pages:
            break

    return buf.getvalue()


# ── Cover Letter PDF builder ────────────────────────────────────────────────────
def build_cover_letter_pdf(cover_letter_text: str, opt_cv: dict) -> bytes:
    """Render the cover letter as a single-page PDF. Returns PDF bytes."""
    cl_body_style = ParagraphStyle('', fontName=FONT, fontSize=10.5,
                                   textColor=DKGRY, leading=16,
                                   alignment=TA_JUSTIFY, spaceAfter=8)
    cl_meta_style = ParagraphStyle('', fontName=FONT, fontSize=9.5,
                                   textColor=MDGRY, leading=13, spaceAfter=3)
    name_style    = ParagraphStyle('', fontName=FONT_BOLD, fontSize=14,
                                   textColor=NAVY, leading=18, spaceAfter=2)
    contact       = opt_cv.get('contact', {})
    contact_line  = format_contact_line(contact)

    story = [
        Paragraph(opt_cv.get('name', ''), name_style),
        Paragraph(opt_cv.get('title', ''), cl_meta_style),
        Paragraph(contact_line, cl_meta_style),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 18),
    ]

    paragraphs = [p.strip() for p in cover_letter_text.split('\n\n') if p.strip()]
    for para in paragraphs:
        para_text = para.replace('\n', ' ')
        story.append(Paragraph(para_text, cl_body_style))

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        topMargin=MARGIN_TB,
        bottomMargin=MARGIN_TB,
    )
    frame = Frame(
        MARGIN_LR, MARGIN_TB,
        TEXT_W, PAGE_H - 2 * MARGIN_TB,
        id='main', showBoundary=0,
    )
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
    doc.build(story)
    return buf.getvalue()
