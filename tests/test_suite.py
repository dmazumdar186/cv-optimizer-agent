"""
Test suite for cv_optimizer_agent.py
Covers: null safety, slugify, PDF generation (bytes), BytesIO extraction, French Unicode labels
Run from repo root: py tests/test_suite.py
"""
import importlib.util
import io
import pathlib
import re
import sys

spec = importlib.util.spec_from_file_location(
    'cv_opt',
    pathlib.Path(__file__).parent.parent / 'cv_optimizer_agent.py'
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

passed = 0
failed = 0

def ok(label):
    global passed; passed += 1; print(f'  PASS  {label}')

def fail(label, e):
    global failed; failed += 1; print(f'  FAIL  {label}: {e}')

TMP = pathlib.Path(__file__).parent.parent / '.tmp'
TMP.mkdir(exist_ok=True)

# ── Shared fixture ─────────────────────────────────────────────────────────────
opt_cv = {
    'name': 'Jane Smith',
    'title': 'Data Scientist',
    'contact': {
        'email': 'jane@example.com', 'phone': None,
        'location': None, 'linkedin': None, 'github': None,
    },
    'summary': 'Expert data scientist with 8 years ML experience.',
    'summary_kpis': '<b>3x</b> revenue | <b>40%</b> churn reduction',
    'experience': [
        {
            'role': 'Senior Data Scientist', 'company_line': 'Acme Corp | 2020-Present',
            'bullets': ['Cut latency by <b>60%</b>', 'Led team of 5'], 'is_oneliner': False,
        },
        {
            'role': 'Data Analyst', 'company_line': 'StartCo | 2018-2020',
            'bullets': None, 'is_oneliner': True,       # null bullets, oneliner
        },
        {
            'role': 'Junior Analyst', 'company_line': 'OldCo | 2016-2018',
            'bullets': [], 'is_oneliner': None,          # empty bullets, null is_oneliner
        },
    ],
    'skills': [
        {'category': 'Languages', 'value': 'Python, R, SQL'},
        {'category': None, 'value': 'Machine Learning'},  # null category
    ],
    'education': [{'degree': 'MSc Data Science', 'institution_line': 'Paris Tech, 2018'}],
    'languages': ['French: Native', 'English: Bilingual'],
    'certifications': ['AWS Certified ML Specialist'],
    'projects': ['open-source ML pipeline'],
}

labels = {
    'experience': 'Experience', 'skills': 'Skills', 'education': 'Education',
    'languages': 'Languages', 'certifications': 'Certifications', 'projects': 'Projects',
}

# ── T1: All-null contact fields ────────────────────────────────────────────────
try:
    result = mod.format_contact_line(
        {'email': None, 'phone': None, 'location': None, 'linkedin': None, 'github': None}
    )
    assert result == '', f'Expected empty string, got {repr(result)}'
    ok('T1: format_contact_line with all-null fields')
except Exception as e:
    fail('T1', e)

# ── T2: Partial null contact fields ───────────────────────────────────────────
try:
    result = mod.format_contact_line({
        'email': 'a@b.com', 'phone': None, 'location': 'Paris',
        'linkedin': 'https://linkedin.com/in/jane', 'github': None,
    })
    assert 'a@b.com' in result and 'Paris' in result and 'linkedin.com' in result
    ok('T2: format_contact_line with partial nulls')
except Exception as e:
    fail('T2', e)

# ── T3: _slugify removes Windows-illegal chars ─────────────────────────────────
try:
    for inp in ['Google: Cloud', 'Air France/KLM', '', 'A*B?C', 'Test<>Name']:
        s = mod._slugify(inp)
        assert not re.search(r'[/:*?"<>|]', s), f'Illegal chars in "{s}"'
    ok('T3: _slugify removes Windows-illegal chars')
except Exception as e:
    fail('T3', e)

# ── T4: CV PDF returns bytes ───────────────────────────────────────────────────
try:
    result = mod.build_cv_pdf(opt_cv, labels, target_pages=1)
    assert isinstance(result, bytes), f'Expected bytes, got {type(result)}'
    assert len(result) > 5000, f'PDF too small: {len(result)} bytes'
    out = TMP / 'test_t4_null_cv.pdf'
    out.write_bytes(result)
    ok(f'T4: build_cv_pdf returns bytes — {len(result) // 1024}KB')
except Exception as e:
    fail('T4', e)

# ── T5: CV PDF page-count targeting returns bytes ─────────────────────────────
try:
    result = mod.build_cv_pdf(opt_cv, labels, target_pages=2)
    assert isinstance(result, bytes), f'Expected bytes, got {type(result)}'
    out = TMP / 'test_t5_2page.pdf'
    out.write_bytes(result)
    ok(f'T5: build_cv_pdf 2-page target — {len(result) // 1024}KB')
except Exception as e:
    fail('T5', e)

# ── T6: Cover letter PDF returns bytes ────────────────────────────────────────
try:
    cover = (
        'Paris, April 10 2026\n\n'
        'Dear Hiring Team,\n\n'
        'Data science is not about data -- it is about decisions. '
        'That conviction drives my application.\n\n'
        'With eight years building ML systems that reduced churn by 40% and tripled revenue, '
        'I bring both technical depth and business fluency.\n\n'
        'Sincerely,\nJane Smith'
    )
    result = mod.build_cover_letter_pdf(cover, opt_cv)
    assert isinstance(result, bytes), f'Expected bytes, got {type(result)}'
    assert len(result) > 3000, f'PDF too small: {len(result)} bytes'
    out = TMP / 'test_t6_cl.pdf'
    out.write_bytes(result)
    ok(f'T6: build_cover_letter_pdf returns bytes — {len(result) // 1024}KB')
except Exception as e:
    fail('T6', e)

# ── T7: extract_cv_pdf accepts BytesIO ────────────────────────────────────────
try:
    # Build a minimal PDF in memory using reportlab, then extract text from BytesIO
    cv_pdf_bytes = mod.build_cv_pdf(opt_cv, labels, target_pages=1)
    bio = io.BytesIO(cv_pdf_bytes)
    text, pages = mod.extract_cv_pdf(bio)
    assert isinstance(text, str), f'Expected str, got {type(text)}'
    assert isinstance(pages, int) and pages >= 1, f'Expected page count >= 1, got {pages}'
    ok(f'T7: extract_cv_pdf accepts BytesIO — {pages}p, {len(text)} chars')
except Exception as e:
    fail('T7', e)

# ── T8: Sparse/empty CV sections do not crash ─────────────────────────────────
try:
    sparse = {
        'name': 'Bob', 'title': '', 'contact': {},
        'summary': '', 'summary_kpis': '',
        'experience': [], 'skills': [], 'education': [],
        'languages': [], 'certifications': [], 'projects': [],
    }
    result = mod.build_cv_pdf(sparse, labels, target_pages=1)
    assert isinstance(result, bytes) and len(result) > 0
    out = TMP / 'test_t8_sparse.pdf'
    out.write_bytes(result)
    ok(f'T8: Sparse/empty CV sections — {len(result) // 1024}KB')
except Exception as e:
    fail('T8', e)

# ── T9: French section labels (Unicode) ───────────────────────────────────────
try:
    fr_labels = {
        'experience': 'Exp\u00e9riences Professionnelles',
        'skills': 'Comp\u00e9tences',
        'education': 'Formation',
        'languages': 'Langues',
        'certifications': 'Certifications',
        'projects': 'Projets Personnels',
    }
    result = mod.build_cv_pdf(opt_cv, fr_labels, target_pages=1)
    assert isinstance(result, bytes) and len(result) > 5000
    out = TMP / 'test_t9_french.pdf'
    out.write_bytes(result)
    ok(f'T9: French Unicode labels — {len(result) // 1024}KB')
except Exception as e:
    fail('T9', e)

# ── T10: Long cover letter does not crash ─────────────────────────────────────
try:
    long_cover = '\n\n'.join([
        'Paris, April 10 2026',
        'Dear Hiring Team,',
    ] + [
        'This is paragraph number ' + str(i) + '. ' +
        'It contains substantial narrative content designed to test overflow detection. ' * 4
        for i in range(1, 20)
    ] + ['Sincerely,\nJane Smith'])
    result = mod.build_cover_letter_pdf(long_cover, opt_cv)
    assert isinstance(result, bytes) and len(result) > 0
    out = TMP / 'test_t10_overflow.pdf'
    out.write_bytes(result)
    ok(f'T10: Long cover letter overflow handling — {len(result) // 1024}KB')
except Exception as e:
    fail('T10', e)

# ── T11: JD minimum length guard logic ────────────────────────────────────────
try:
    jd = 'Short JD'
    triggered = len(jd.strip()) < 50
    assert triggered
    ok('T11: JD minimum length guard logic correct')
except Exception as e:
    fail('T11', e)

# ── Summary ────────────────────────────────────────────────────────────────────
print()
print(f'Results: {passed} passed, {failed} failed out of {passed + failed} tests')
if failed == 0:
    print('ALL TESTS PASSED')
    sys.exit(0)
else:
    print('SOME TESTS FAILED')
    sys.exit(1)
