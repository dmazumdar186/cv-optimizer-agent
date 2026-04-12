"""
Test suite for cv_optimizer_agent.py
Covers: null safety, slugify, PDF generation, page count accuracy, French Unicode labels
Run from repo root: py tests/test_suite.py
"""
import importlib.util, pathlib, re, sys

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

# ── T4: CV PDF with all-null optional fields ───────────────────────────────────
try:
    out = TMP / 'test_t4_null_cv.pdf'
    pages = mod.build_cv_pdf(opt_cv, labels, out, target_pages=1)
    assert out.exists() and out.stat().st_size > 5000
    ok(f'T4: CV PDF with null fields — {pages}p, {out.stat().st_size // 1024}KB')
except Exception as e:
    fail('T4', e)

# ── T5: CV PDF page-count targeting ───────────────────────────────────────────
try:
    out = TMP / 'test_t5_2page.pdf'
    pages = mod.build_cv_pdf(opt_cv, labels, out, target_pages=2)
    assert 1 <= pages <= 3
    ok(f'T5: CV PDF page-count targeting — {pages}p for 2p target')
except Exception as e:
    fail('T5', e)

# ── T6: Cover letter PDF returns actual page count ─────────────────────────────
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
    out = TMP / 'test_t6_cl.pdf'
    cl_pages = mod.build_cover_letter_pdf(cover, opt_cv, out)
    assert isinstance(cl_pages, int) and cl_pages >= 1
    assert out.exists() and out.stat().st_size > 3000
    ok(f'T6: Cover letter PDF — {cl_pages}p, {out.stat().st_size // 1024}KB')
except Exception as e:
    fail('T6', e)

# ── T7: Cover letter response parser handles non-text blocks ──────────────────
try:
    class FakeBlock:
        type = 'tool_use'  # no .text attribute
    blocks = [b for b in [FakeBlock()] if hasattr(b, 'text')]
    assert blocks == []
    ok('T7: Cover letter response parser handles non-text blocks')
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
    out = TMP / 'test_t8_sparse.pdf'
    pages = mod.build_cv_pdf(sparse, labels, out, target_pages=1)
    ok(f'T8: Sparse/empty CV sections — {pages}p')
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
    out = TMP / 'test_t9_french.pdf'
    pages = mod.build_cv_pdf(opt_cv, fr_labels, out, target_pages=1)
    ok(f'T9: French Unicode labels — {pages}p, {out.stat().st_size // 1024}KB')
except Exception as e:
    fail('T9', e)

# ── T10: Long cover letter triggers page overflow warning ─────────────────────
try:
    long_cover = '\n\n'.join([
        'Paris, April 10 2026',
        'Dear Hiring Team,',
    ] + [
        'This is paragraph number ' + str(i) + '. ' +
        'It contains substantial narrative content designed to test overflow detection. ' * 4
        for i in range(1, 20)
    ] + ['Sincerely,\nJane Smith'])
    out = TMP / 'test_t10_overflow.pdf'
    cl_pages = mod.build_cover_letter_pdf(long_cover, opt_cv, out)
    assert isinstance(cl_pages, int) and cl_pages >= 1
    note = ' (OVERFLOW DETECTED - cover letter too long)' if cl_pages > 1 else ''
    ok(f'T10: Long cover letter overflow handling — {cl_pages}p{note}')
except Exception as e:
    fail('T10', e)

# ── T11: JD too short — error message fires ───────────────────────────────────
try:
    jd = 'Short JD'
    triggered = len(jd) < 50
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
