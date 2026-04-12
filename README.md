# CV Optimizer Agent

Upload a CV (PDF) + job description → get an ATS score, an optimized CV, and a narrative cover letter. All in one click, in your browser.

**Live app:** [cv-optimizer-agent.streamlit.app](https://cv-optimizer-agent.streamlit.app) *(link live after first deploy)*

---

## What it does

1. **ATS Score** — hypercritical 1–10 scoring against the job description, with a full skill matrix and improvement recommendations
2. **Optimized CV** — same language as the JD, same number of pages as your original, ATS keywords integrated naturally
3. **Cover Letter** — one page, narrative-driven, never a CV rehash — connects your story to the company's values and role requirements

No fabrication. No inflation. If it's not in your CV, it won't appear in the output.

---

## Deploy your own copy

### 1. Fork this repo

Click **Fork** on GitHub.

### 2. Get a Gemini API key

Go to [aistudio.google.com](https://aistudio.google.com) → **Get API key** → create a free key.

### 3. Deploy to Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app** → select your fork → set **Main file path** to `app.py`
3. Open **Advanced settings → Secrets** and add:

```toml
GEMINI_API_KEY = "your-key-here"
```

4. Click **Deploy** — done.

---

## Run locally

```bash
git clone https://github.com/dmazumdar186/cv-optimizer-agent
cd cv-optimizer-agent
pip install -r requirements.txt
```

Create a `.streamlit/secrets.toml` file:

```toml
GEMINI_API_KEY = "your-key-here"
```

Then run:

```bash
streamlit run app.py
```

---

## Running tests

No API key needed — tests cover PDF generation (bytes output), BytesIO extraction, null-safety, and slugify.

```bash
py tests/test_suite.py
```

Expected: `11 passed, 0 failed — ALL TESTS PASSED`

---

## Tech stack

| Layer | Choice |
|-------|--------|
| UI | Streamlit |
| Hosting | Streamlit Community Cloud |
| AI | Google Gemini 2.0 Flash |
| PDF generation | ReportLab |
| PDF parsing | pdfplumber |

---

Built by [Debanjan Mazumdar](https://www.linkedin.com/in/dmazumdar/) · [ProdCraft](https://www.youtube.com/@ProdCraft) on YouTube · MIT License
