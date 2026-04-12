"""
app.py — Streamlit entry point for the CV Optimizer web app.
Run locally: streamlit run app.py
Deploy: push to GitHub, connect to Streamlit Community Cloud.
"""

import io

import streamlit as st

from cv_optimizer_agent import (
    build_cover_letter_pdf,
    build_cv_pdf,
    extract_cv_pdf,
    run_analysis,
    run_cover_letter,
    _slugify,
)

st.set_page_config(
    page_title="CV Optimizer",
    page_icon="📄",
    layout="centered",
)

st.title("CV Optimizer")
st.write(
    "Upload your CV and paste a job description — get an ATS score, "
    "an optimized CV, and a cover letter in under 60 seconds."
)

st.divider()

uploaded_file = st.file_uploader("Upload your CV (PDF only)", type=["pdf"])
jd_text = st.text_area("Paste the job description", height=300)
company = st.text_input("Company name", placeholder="e.g. MotorK")

if st.button("Optimize my CV →", type="primary"):
    # ── Input validation ───────────────────────────────────────────────────────
    if not uploaded_file:
        st.error("Please upload your CV PDF.")
        st.stop()
    if not jd_text or len(jd_text.strip()) < 50:
        st.error(
            "Please paste the full job description (at least a few sentences)."
        )
        st.stop()
    if not company.strip():
        st.error("Please enter the company name.")
        st.stop()

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        st.error(
            "API key not configured. Add GEMINI_API_KEY to your Streamlit secrets."
        )
        st.stop()

    # ── Step 1: Extract CV text ────────────────────────────────────────────────
    cv_bytes  = uploaded_file.read()
    cv_source = io.BytesIO(cv_bytes)

    try:
        cv_text, page_count = extract_cv_pdf(cv_source)
    except Exception:
        st.error(
            "Your PDF appears to be a scanned image. "
            "Please export a text-based PDF from Word, Google Docs, or Canva."
        )
        st.stop()

    if not cv_text:
        st.error(
            "Your PDF appears to be a scanned image. "
            "Please export a text-based PDF from Word, Google Docs, or Canva."
        )
        st.stop()

    # ── Step 2: Gemini analysis ────────────────────────────────────────────────
    try:
        with st.spinner("Step 1/2: Analysing your CV against the job description..."):
            analysis = run_analysis(cv_text, jd_text.strip(), api_key)
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            st.error(
                "We're at capacity right now. Please try again in a few minutes."
            )
        else:
            st.error("Something went wrong during analysis. Please try again.")
        st.stop()

    opt_cv   = analysis.get("optimized_cv") or {}
    labels   = analysis.get("section_labels") or {}
    language = analysis.get("language") or "English"

    if not opt_cv or not opt_cv.get("name"):
        st.error("Something went wrong. Please try again.")
        st.stop()

    # ── Step 3: Cover letter ───────────────────────────────────────────────────
    try:
        with st.spinner("Step 2/2: Writing your cover letter..."):
            cover_letter_text = run_cover_letter(
                cv_text, jd_text.strip(), language, opt_cv, company.strip(), api_key
            )
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            st.error(
                "We're at capacity right now. Please try again in a few minutes."
            )
        else:
            st.error("Something went wrong. Please try again.")
        st.stop()

    # ── Step 4: Generate PDFs ──────────────────────────────────────────────────
    try:
        with st.spinner("Generating PDFs..."):
            cv_pdf_bytes = build_cv_pdf(opt_cv, labels, page_count)
            cl_pdf_bytes = build_cover_letter_pdf(cover_letter_text, opt_cv)
    except Exception:
        st.error("Something went wrong generating the PDFs. Please try again.")
        st.stop()

    # ── Results ────────────────────────────────────────────────────────────────
    score0 = analysis.get("ats_score_initial", "?")
    score1 = analysis.get("ats_score_improved", "?")

    st.success(f"ATS Score: **{score0}/10 → {score1}/10**")

    skill_matrix = analysis.get("skill_matrix", [])
    if skill_matrix:
        with st.expander("Improvement areas"):
            sorted_matrix = sorted(
                skill_matrix,
                key=lambda x: x.get("strategic_score", 0),
                reverse=True,
            )
            table_data = {
                "Skill": [],
                "In CV": [],
                "Transferable": [],
                "Score": [],
                "Reason": [],
            }
            for row in sorted_matrix:
                table_data["Skill"].append(row.get("skill", ""))
                table_data["In CV"].append("Yes" if row.get("present_in_cv") else "No")
                table_data["Transferable"].append(
                    "Yes" if row.get("transferable") else "No"
                )
                table_data["Score"].append(
                    f"{row.get('strategic_score', '?')}/10"
                )
                table_data["Reason"].append(row.get("score_reason", ""))
            st.dataframe(table_data, use_container_width=True)

    recs = analysis.get("recommendations", [])
    if recs:
        with st.expander("Top recommendations"):
            for r in recs:
                st.write(f"• {r}")

    # ── Download buttons ───────────────────────────────────────────────────────
    name_parts   = opt_cv.get("name", "candidate").split()
    last_name    = _slugify(name_parts[-1]) if name_parts else "candidate"
    company_slug = _slugify(company.strip())

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇ Download Optimized CV (PDF)",
            data=cv_pdf_bytes,
            file_name=f"cv_opt_{company_slug}_{last_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label="⬇ Download Cover Letter (PDF)",
            data=cl_pdf_bytes,
            file_name=f"cover_letter_{company_slug}_{last_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
