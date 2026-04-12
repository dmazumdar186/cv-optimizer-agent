# CV Optimizer Agent

A local AI agent that takes **any CV PDF + a job description**, scores the match, rewrites the CV for ATS + recruiters, and generates a ready-to-send cover letter — both as formatted PDFs.

Built with Claude Opus 4 (Anthropic API) + ReportLab. Runs entirely on your machine. Nothing leaves your computer except the API call to Claude.

---

## What It Does

```
You provide:
  → Your CV (PDF)
  → The job description (paste or .txt file)
  → The company name

The agent:
  1. Extracts your CV text and page count
  2. Scores your CV against the JD (ATS score: initial vs. optimised)
  3. Builds a skill matrix — present vs. missing vs. transferable
  4. Rewrites every section of your CV to match the JD language & keywords
  5. Generates an optimised CV PDF (same page count as your original)
  6. Writes a tailored cover letter PDF (in the language of the JD)
```

### Console output

```
  CV loaded : my_cv.pdf  (2 pages, 3,241 chars extracted)

  Analysis complete.

  ┌───────────────────────────────────────────┐
  │  Initial ATS Score   : 5 / 10            │
  │  Optimised ATS Score : 9 / 10            │
  │  JD Language         : French            │
  └───────────────────────────────────────────┘

  Skill Matrix (top skills by strategic relevance):
  ┌────────────────────────────┬──────────┬─────────────┬───────┐
  │ Skill                      │ Present  │ Transferable│ Score │
  ├────────────────────────────┼──────────┼─────────────┼───────┤
  │ Machine Learning           │ Yes      │ No          │ 9/10  │
  │ Agile / Scrum              │ No       │ Yes         │ 8/10  │
  │ SQL                        │ Yes      │ No          │ 8/10  │
  └────────────────────────────┴──────────┴─────────────┴───────┘

  Key Recommendations:
    • Add 'Agile' to your skills section — listed 4× in the JD
    • Quantify ML model impact in role 1 (revenue, latency, accuracy)
    • Translate CV to French — JD language mismatch detected

  Generating optimised CV PDF...  ✓ 2 pages
  Generating cover letter PDF...  ✓ 1 page

  ══════════════════════════════════════════════
  Output files:
    CV           : .tmp/cv_opt_acme_smith.pdf
    Cover Letter : .tmp/cover_letter_acme_smith.pdf
    Sizes        : CV 91 KB  |  Cover Letter 74 KB
  ══════════════════════════════════════════════
```

---

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) (Claude Opus 4)
- Your CV as a **text-based PDF** (not a scanned image)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/dmazumdar186/cv-optimizer-agent.git
cd cv-optimizer-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API key
cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY

# 4. Run
py cv_optimizer_agent.py
```

The agent will prompt you for the job description, your CV PDF path, and the company name. Both PDFs are saved to `.tmp/`.

---

## How It Works

Two Claude API calls:

**Call 1 — Analysis + CV rewrite** (`claude-opus-4-6`, structured output via `tool_use`)
- Detects JD language, scores skills, identifies gaps
- Rewrites all CV sections in the JD language with ATS-optimised keywords
- Returns a structured JSON with the full optimised CV

**Call 2 — Cover letter** (`claude-opus-4-6`, plain text)
- Uses the optimised CV summary + full JD context
- Returns a 250–400 word cover letter with no placeholders
- Written in the JD language, ready to send

**PDF generation** (ReportLab)
- CV: auto-scales font size (8.4pt → 6.8pt) to match your original page count
- Cover letter: professional letterhead with your name/contact, full body text
- Both use Arial with Unicode support (French, Spanish, etc.)

---

## Output

Both PDFs land in `.tmp/` (gitignored):

| File | Contents |
|---|---|
| `cv_opt_{company}_{lastname}.pdf` | ATS-optimised CV, page-count-matched |
| `cover_letter_{company}_{lastname}.pdf` | Tailored cover letter, ready to attach |

---

## Running the Tests

No API key needed — tests cover PDF generation, null-safety, and slugify logic.

```bash
py tests/test_suite.py
```

Expected: `11 passed, 0 failed — ALL TESTS PASSED`

---

## Cost

Each run makes 2 Claude API calls. At Anthropic's current pricing for Claude Opus 4:

- A typical run costs roughly **$0.10–$0.25** depending on CV and JD length
- Check [Anthropic pricing](https://www.anthropic.com/pricing) for current rates

---

## Contributing

PRs welcome. The script is intentionally a single file to make it easy to run without any project setup.

If you add a feature, run `py tests/test_suite.py` before submitting.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Debanjan Mazumdar](https://www.linkedin.com/in/dmazumdar/) · [ProdCraft](https://www.youtube.com/@ProdCraft) on YouTube
