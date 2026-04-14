"""
app.py — Streamlit entry point for the CV Optimizer web app.
Run locally: streamlit run app.py
Deploy: push to GitHub, connect to Streamlit Community Cloud.
"""

import io
import time

import streamlit as st

from cv_optimizer_agent import (
    build_cover_letter_pdf,
    build_cv_pdf,
    extract_cv_pdf,
    run_analysis,
    run_cover_letter,
    _slugify,
)


def _call_with_retry(fn, *args, max_attempts=3, backoff=8):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args)
        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "quota" in err.lower() or "rate" in err.lower()
            if is_quota and attempt < max_attempts:
                time.sleep(backoff)
                continue
            raise


st.set_page_config(
    page_title="CV Optimizer",
    page_icon="📄",
    layout="centered",
)

st.title("CV Optimizer")
st.write(
    "Upload your CV and paste a job description — get a hyper-realistic ATS score "
    "and an optimized CV PDF."
)

st.divider()

uploaded_file = st.file_uploader("Upload your CV (PDF only)", type=["pdf"])
jd_text       = st.text_area("Paste the job description", height=300)
company       = st.text_input("Company name", placeholder="e.g. MotorK")

if st.button("Optimize my CV →", type="primary"):
    # Clear any results from a previous run
    for key in ("results", "cl_pdf_bytes"):
        st.session_state.pop(key, None)

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
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        st.error(
            "API key not configured. Add ANTHROPIC_API_KEY to your Streamlit secrets."
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

    # ── Step 2: Claude analysis ────────────────────────────────────────────────
    try:
        with st.spinner("Step 1/2: Analysing your CV against the job description..."):
            analysis = _call_with_retry(run_analysis, cv_text, jd_text.strip(), api_key)
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            st.error("API quota exceeded — rate limit hit. Please try again later.")
        else:
            st.error("Something went wrong during analysis. Please try again.")
        with st.expander("Error details"):
            st.code(err)
        st.stop()

    opt_cv   = analysis.get("optimized_cv") or {}
    labels   = analysis.get("section_labels") or {}
    language = analysis.get("language") or "English"

    if not opt_cv or not opt_cv.get("name"):
        st.error("Something went wrong. Please try again.")
        st.stop()

    if len((analysis.get("optimized_cv") or {}).get("experience", [])) == 0:
        st.error("CV rewrite returned no experience entries. Please try again.")
        st.stop()

    # ── Step 3: Generate CV PDF ────────────────────────────────────────────────
    try:
        with st.spinner("Step 2/2: Generating your optimized CV PDF..."):
            cv_pdf_bytes = build_cv_pdf(opt_cv, labels, page_count)
    except Exception:
        st.error("Something went wrong generating the PDF. Please try again.")
        st.stop()

    # ── Persist to session state ───────────────────────────────────────────────
    name_parts   = opt_cv.get("name", "candidate").split()
    last_name    = _slugify(name_parts[-1]) if name_parts else "candidate"
    company_slug = _slugify(company.strip())

    st.session_state["results"] = {
        "analysis":     analysis,
        "opt_cv":       opt_cv,
        "labels":       labels,
        "language":     language,
        "cv_pdf_bytes": cv_pdf_bytes,
        "cv_text":      cv_text,
        "jd_text":      jd_text.strip(),
        "company":      company.strip(),
        "page_count":   page_count,
        "last_name":    last_name,
        "company_slug": company_slug,
    }


# ── Results section — rendered from session state so buttons never disappear ───
if st.session_state.get("results"):
    res      = st.session_state["results"]
    analysis = res["analysis"]
    opt_cv   = res["opt_cv"]

    # Role count banner
    n_roles = len(opt_cv.get("experience", []))
    st.info(f"✓ {n_roles} experience {'entry' if n_roles == 1 else 'entries'} optimised")

    empty_bullet_roles = [
        e.get("role", "?")
        for e in opt_cv.get("experience", [])
        if not e.get("is_oneliner") and not e.get("bullets")
    ]
    if empty_bullet_roles:
        st.warning(
            f"Bullet generation failed for: {', '.join(empty_bullet_roles)}. "
            "These roles appear in the CV without bullet points."
        )

    # ATS score (0–100 scale)
    score0 = analysis.get("ats_score_initial", "?")
    score1 = analysis.get("ats_score_improved", "?")
    st.success(f"ATS Score: **{score0}/100 → {score1}/100**")

    skill_matrix = analysis.get("skill_matrix", [])
    if skill_matrix:
        with st.expander("Skill gap analysis"):
            sorted_matrix = sorted(
                skill_matrix,
                key=lambda x: x.get("strategic_score", 0),
                reverse=True,
            )
            table_data = {
                "Skill":        [],
                "In CV":        [],
                "Transferable": [],
                "Score":        [],
                "Reason":       [],
            }
            for row in sorted_matrix:
                table_data["Skill"].append(row.get("skill", ""))
                table_data["In CV"].append("Yes" if row.get("present_in_cv") else "No")
                table_data["Transferable"].append(
                    "Yes" if row.get("transferable") else "No"
                )
                table_data["Score"].append(f"{row.get('strategic_score', '?')}/10")
                table_data["Reason"].append(row.get("score_reason", ""))
            st.dataframe(table_data, use_container_width=True)

    recs = analysis.get("recommendations", [])
    if recs:
        with st.expander("Top recommendations"):
            for r in recs:
                st.write(f"• {r}")

    # ── CV download (always visible) ──────────────────────────────────────────
    st.download_button(
        label="⬇ Download Optimized CV (PDF)",
        data=res["cv_pdf_bytes"],
        file_name=f"cv_opt_{res['company_slug']}_{res['last_name']}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.divider()

    # ── Cover letter (optional) ────────────────────────────────────────────────
    if st.session_state.get("cl_pdf_bytes") is None:
        st.info("Your optimized CV is ready. Would you like a tailored cover letter?")
        if st.button("Yes, generate cover letter →", type="secondary"):
            try:
                api_key = st.secrets["ANTHROPIC_API_KEY"]
            except Exception:
                st.error(
                    "API key not configured. Add ANTHROPIC_API_KEY to your Streamlit secrets."
                )
                st.stop()
            try:
                with st.spinner("Writing your cover letter..."):
                    cover_letter_text = _call_with_retry(
                        run_cover_letter,
                        res["cv_text"],
                        res["jd_text"],
                        res["language"],
                        res["opt_cv"],
                        res["company"],
                        api_key,
                    )
                    cl_pdf_bytes = build_cover_letter_pdf(cover_letter_text, res["opt_cv"])
                st.session_state["cl_pdf_bytes"] = cl_pdf_bytes
                st.rerun()
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                    st.error(
                        "API quota exceeded — rate limit hit. Please try again later."
                    )
                else:
                    st.error(
                        "Something went wrong generating the cover letter. Please try again."
                    )
                with st.expander("Error details"):
                    st.code(err)

    if st.session_state.get("cl_pdf_bytes") is not None:
        st.download_button(
            label="⬇ Download Cover Letter (PDF)",
            data=st.session_state["cl_pdf_bytes"],
            file_name=f"cover_letter_{res['company_slug']}_{res['last_name']}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
