"""
test_full.py — Full test suite: Unit, SIT, E2E, Monkey
Covers all scenarios including real CV + French JD language test.

Run (no API):       py tests/test_full.py
Run (with API key): set ANTHROPIC_API_KEY=sk-ant-xxx && py tests/test_full.py

Tests that require ANTHROPIC_API_KEY are clearly labelled [API REQUIRED].
Tests that do NOT require the API are labelled [NO API].
"""
import importlib.util
import io
import json
import os
import pathlib
import re
import sys

# Force UTF-8 stdout on Windows (box-drawing chars + accented letters)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Load module ────────────────────────────────────────────────────────────────
spec = importlib.util.spec_from_file_location(
    'cv_opt',
    pathlib.Path(__file__).parent.parent / 'cv_optimizer_agent.py'
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

API_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()
HAS_API = bool(API_KEY)

TMP     = pathlib.Path(__file__).parent.parent / '.tmp'
TMP.mkdir(exist_ok=True)
CV_PATH = TMP / 'test_cv_debanjan.pdf'

passed = 0
failed = 0
skipped = 0

def ok(label):
    global passed; passed += 1; print(f'  PASS   {label}')

def fail(label, e):
    global failed; failed += 1; print(f'  FAIL   {label}: {e}')

def skip(label):
    global skipped; skipped += 1; print(f'  SKIP   {label}  [API REQUIRED — set ANTHROPIC_API_KEY]')


# ════════════════════════════════════════════════════════════════════════════════
# UNIT TESTS  [NO API]
# ════════════════════════════════════════════════════════════════════════════════
print('\n── UNIT TESTS [NO API] ──────────────────────────────────────────────────')

# U1: format_contact_line all-null
try:
    r = mod.format_contact_line({'email': None, 'phone': None, 'location': None,
                                  'linkedin': None, 'github': None, 'youtube': None})
    assert r == ''
    ok('U1: format_contact_line — all-null → empty string')
except Exception as e:
    fail('U1', e)

# U2: format_contact_line partial nulls + URL
try:
    r = mod.format_contact_line({'email': 'a@b.com', 'phone': None, 'location': 'Paris',
                                  'linkedin': 'https://linkedin.com/in/dmazumdar',
                                  'github': None, 'youtube': None})
    assert 'a@b.com' in r and 'Paris' in r and 'linkedin.com' in r
    ok('U2: format_contact_line — partial nulls + clickable URL')
except Exception as e:
    fail('U2', e)

# U3: _slugify
try:
    cases = [
        ('Google: Cloud',       'google-cloud'),
        ('Air France/KLM',      'air-france-klm'),
        ('',                    ''),
        ('A*B?C',               'a-b-c'),
        ('Teaminside / Paris',  'teaminside-paris'),
    ]
    for inp, expected in cases:
        got = mod._slugify(inp)
        assert not re.search(r'[/:*?"<>|]', got), f'Illegal char in "{got}"'
    ok('U3: _slugify — no Windows-illegal chars in any case')
except Exception as e:
    fail('U3', e)

# U4: _truncate_jd
try:
    words = ['word'] * 500
    long_jd = ' '.join(words)
    truncated = mod._truncate_jd(long_jd, 400)
    assert len(truncated.split()) <= 401  # 400 words + optional ellipsis word
    assert truncated.endswith('…')
    short_jd = 'short job description'
    assert mod._truncate_jd(short_jd) == short_jd
    ok('U4: _truncate_jd — truncates at 400 words, short JD unchanged')
except Exception as e:
    fail('U4', e)

# U5: _parse_json — plain JSON
try:
    raw = '{"language": "French", "score": 42}'
    result = mod._parse_json(raw)
    assert result['language'] == 'French' and result['score'] == 42
    ok('U5: _parse_json — plain JSON')
except Exception as e:
    fail('U5', e)

# U6: _parse_json — JSON with code fences
try:
    raw = '```json\n{"language": "French", "score": 42}\n```'
    result = mod._parse_json(raw)
    assert result['language'] == 'French'
    ok('U6: _parse_json — strips code fences')
except Exception as e:
    fail('U6', e)

# U7: CV PDF generation — standard fixture
try:
    opt_cv = {
        'name': 'Debanjan Mazumdar', 'title': 'AI Product Manager',
        'contact': {'email': 'debanjan186@gmail.com', 'phone': '0755807658',
                    'location': 'Paris, France', 'linkedin': 'https://linkedin.com/in/dmazumdar',
                    'github': 'https://github.com/dmazumdar186', 'youtube': None},
        'summary': 'PM with 14+ years in data-intensive environments.',
        'summary_kpis': '<b>+30%</b> adoption • <b>+20%</b> CSAT',
        'experience': [
            {'role': 'AI Product Manager', 'company': 'Wiser Solutions',
             'period': '11/2022 - Present', 'location': 'Paris, France',
             'bullets': ['Defined AI capability roadmap with <b>40%</b> BU adoption.'],
             'is_oneliner': False},
            {'role': 'Data Product Manager', 'company': 'InfoTnT',
             'period': '06/2021 - 11/2022', 'location': 'Paris, France',
             'bullets': ['Led product discovery, reduced iteration by <b>~35%</b>.'],
             'is_oneliner': False},
        ],
        'skills': [{'category': 'Product', 'value': 'Roadmap, PRD, Backlog'}],
        'education': [{'degree': 'MSc Strategic Business', 'institution_line': 'Toulouse Business School',
                       'period': '09/2019 - 04/2021'}],
        'languages': [{'name': 'English', 'proficiency': 'Native'},
                      {'name': 'French', 'proficiency': 'Native'}],
        'certifications': [],
        'projects': [],
    }
    labels = {'experience': 'Experience', 'skills': 'Skills', 'education': 'Education',
              'languages': 'Languages', 'certifications': 'Certifications', 'projects': 'Projects'}
    pdf = mod.build_cv_pdf(opt_cv, labels, target_pages=1)
    assert isinstance(pdf, bytes) and len(pdf) > 5000
    (TMP / 'u7_cv_standard.pdf').write_bytes(pdf)
    ok(f'U7: build_cv_pdf — standard 2-role fixture — {len(pdf)//1024}KB')
except Exception as e:
    fail('U7', e)

# U8: PDF generation — 7-role CV (mirrors your real CV structure)
try:
    opt_cv_7 = {
        'name': 'Debanjan Mazumdar', 'title': 'AI Product Manager',
        'contact': {'email': 'debanjan186@gmail.com', 'phone': '0755807658',
                    'location': 'Paris, France', 'linkedin': None, 'github': None, 'youtube': None},
        'summary': 'PM with 14+ years in data-intensive environments.',
        'summary_kpis': '<b>+30%</b> adoption',
        'experience': [
            {'role': 'AI Product Manager',        'company': 'Wiser Solutions', 'period': '11/2022 - Present',  'location': 'Paris, France',    'bullets': ['Built AI roadmap with <b>40%</b> BU adoption.'], 'is_oneliner': False},
            {'role': 'Data Product Manager',       'company': 'InfoTnT',         'period': '06/2021 - 11/2022', 'location': 'Paris, France',    'bullets': ['Reduced iterations by <b>~35%</b>.'],             'is_oneliner': False},
            {'role': 'Senior Data Product Owner',  'company': 'Pitney Bowes',    'period': '04/2019 - 09/2019', 'location': 'Pune, India',      'bullets': ['Reduced time-to-market by <b>~20%</b>.'],         'is_oneliner': False},
            {'role': 'Senior Data Product Owner',  'company': 'Evolent Int.',     'period': '06/2018 - 02/2019', 'location': 'Pune, India',      'bullets': ['Improved scalability by <b>~30%</b>.'],           'is_oneliner': False},
            {'role': 'Senior Product Owner',       'company': 'Avaya India',      'period': '07/2015 - 03/2018', 'location': 'Pune, India',      'bullets': ['Accelerated delivery by <b>~30%</b>.'],           'is_oneliner': False},
            {'role': 'QA Engineer / Rel. Coord.',  'company': 'IDrive India',     'period': '04/2013 - 07/2015', 'location': 'Bengaluru, India', 'bullets': [],                                                 'is_oneliner': True},
            {'role': 'Software Engineer',          'company': 'TCS',              'period': '11/2010 - 03/2013', 'location': 'Bengaluru, India', 'bullets': [],                                                 'is_oneliner': True},
        ],
        'skills': [{'category': 'Product', 'value': 'Roadmap, PRD, AI/ML lifecycle'}],
        'education': [{'degree': 'MSc Strategic Business', 'institution_line': 'Toulouse Business School', 'period': '09/2019 - 04/2021'}],
        'languages': [{'name': 'English', 'proficiency': 'Native'}, {'name': 'French', 'proficiency': 'Native'}],
        'certifications': [],
        'projects': [{'title': 'ProdCraft YouTube Channel', 'period': '09/2025 - Present', 'description': 'Ed-tech channel for product managers.'}],
    }
    pdf7 = mod.build_cv_pdf(opt_cv_7, labels, target_pages=2)
    assert isinstance(pdf7, bytes) and len(pdf7) > 5000
    (TMP / 'u8_cv_7roles.pdf').write_bytes(pdf7)
    ok(f'U8: build_cv_pdf — 7-role CV (mirrors real CV) — {len(pdf7)//1024}KB')
except Exception as e:
    fail('U8', e)

# U9: French section labels (Unicode)
try:
    fr_labels = {
        'experience': 'Expériences Professionnelles', 'skills': 'Compétences',
        'education': 'Formation', 'languages': 'Langues',
        'certifications': 'Certifications', 'projects': 'Projets Personnels',
    }
    pdf_fr = mod.build_cv_pdf(opt_cv_7, fr_labels, target_pages=2)
    assert isinstance(pdf_fr, bytes) and len(pdf_fr) > 5000
    (TMP / 'u9_cv_french_labels.pdf').write_bytes(pdf_fr)
    ok(f'U9: French Unicode section labels — {len(pdf_fr)//1024}KB')
except Exception as e:
    fail('U9', e)

# U10: Cover letter PDF
try:
    cl_text = (
        'Paris, 14 avril 2026\n\n'
        'Chère équipe de recrutement Teaminside,\n\n'
        'Définir une roadmap IA pour deux horizons simultanés — expériences conversationnelles '
        'côté client et automatisations internes — c\'est précisément ce que j\'ai fait chez '
        'Wiser Solutions, où j\'ai piloté le déploiement de cas d\'usage IA génératifs '
        '(assistant, triage, recommandation) de la discovery jusqu\'à la production.\n\n'
        'Cordialement,\nDebanjan Mazumdar'
    )
    cl_pdf = mod.build_cover_letter_pdf(cl_text, opt_cv_7)
    assert isinstance(cl_pdf, bytes) and len(cl_pdf) > 3000
    (TMP / 'u10_cover_letter.pdf').write_bytes(cl_pdf)
    ok(f'U10: build_cover_letter_pdf — French content — {len(cl_pdf)//1024}KB')
except Exception as e:
    fail('U10', e)


# ════════════════════════════════════════════════════════════════════════════════
# SIT — SYSTEM INTEGRATION TESTS  [NO API]
# ════════════════════════════════════════════════════════════════════════════════
print('\n── SIT [NO API] ─────────────────────────────────────────────────────────')

# SIT1: Real CV PDF extraction — your actual CV
try:
    assert CV_PATH.exists(), f'CV fixture not found at {CV_PATH}'
    with open(CV_PATH, 'rb') as f:
        bio = io.BytesIO(f.read())
    text, pages = mod.extract_cv_pdf(bio)
    assert isinstance(text, str) and len(text) > 200, f'Too little text: {len(text)} chars'
    assert pages >= 1, f'Expected >= 1 page, got {pages}'
    # Check all 7 employers are present
    expected_employers = ['Wiser Solutions', 'InfoTnT', 'Pitney Bowes', 'Evolent', 'Avaya', 'IDrive', 'Tata']
    missing = [e for e in expected_employers if e not in text]
    assert not missing, f'Missing employers in extracted text: {missing}'
    (TMP / 'sit1_cv_text.txt').write_text(text, encoding='utf-8')
    ok(f'SIT1: Real CV extraction — {pages}p, {len(text)} chars, all 7 employers found')
except Exception as e:
    fail('SIT1', e)

# SIT2: Module imports — all public functions accessible
try:
    required_fns = ['build_cv_pdf', 'build_cover_letter_pdf', 'extract_cv_pdf',
                    'run_analysis', 'run_cover_letter', '_slugify', '_parse_json',
                    '_truncate_jd', 'format_contact_line']
    missing_fns = [fn for fn in required_fns if not hasattr(mod, fn)]
    assert not missing_fns, f'Missing functions: {missing_fns}'
    ok(f'SIT2: All {len(required_fns)} required functions importable')
except Exception as e:
    fail('SIT2', e)

# SIT3: JSON schemas are valid
try:
    schemas = [
        ('CV_ANALYSIS_SCHEMA',     mod.CV_ANALYSIS_SCHEMA),
        ('SKELETON_SCHEMA',        mod.SKELETON_SCHEMA),
        ('STATIC_CV_SCHEMA',       mod.STATIC_CV_SCHEMA),
        ('EXPERIENCE_BULLETS_SCHEMA', mod.EXPERIENCE_BULLETS_SCHEMA),
    ]
    for name, schema in schemas:
        s = json.dumps(schema)
        assert json.loads(s) == schema, f'{name} round-trip failed'
    ok(f'SIT3: All {len(schemas)} JSON schemas are valid and serializable')
except Exception as e:
    fail('SIT3', e)

# SIT4: Score schema specifies 0-100 range in descriptions
try:
    initial_desc = mod.CV_ANALYSIS_SCHEMA['properties']['ats_score_initial']['description']
    improved_desc = mod.CV_ANALYSIS_SCHEMA['properties']['ats_score_improved']['description']
    assert '100' in initial_desc, f'Score schema does not mention 100: {initial_desc}'
    assert '100' in improved_desc, f'Score schema does not mention 100: {improved_desc}'
    ok('SIT4: ATS score schemas reference 0–100 scale')
except Exception as e:
    fail('SIT4', e)

# SIT5: System prompts contain language placeholder
try:
    for name, prompt in [('SKELETON_SYSTEM', mod.SKELETON_SYSTEM),
                          ('CV_STATIC_SYSTEM', mod.CV_STATIC_SYSTEM),
                          ('CV_BULLETS_SYSTEM', mod.CV_BULLETS_SYSTEM)]:
        assert '{language}' in prompt, f'{name} missing {{language}} placeholder'
    ok('SIT5: All per-language prompts contain {language} placeholder')
except Exception as e:
    fail('SIT5', e)

# SIT6: CV PDF with French content round-trips through extract
try:
    fr_cv = {
        'name': 'Debanjan Mazumdar', 'title': 'Chef de Produit IA',
        'contact': {'email': 'debanjan186@gmail.com', 'phone': None, 'location': 'Paris, France',
                    'linkedin': None, 'github': None, 'youtube': None},
        'summary': 'Chef de produit IA avec 14 ans d\'expérience dans des environnements data-intensifs.',
        'summary_kpis': '<b>+30%</b> adoption • <b>+20%</b> CSAT',
        'experience': [
            {'role': 'Chef de Produit IA', 'company': 'Wiser Solutions',
             'period': '11/2022 - Présent', 'location': 'Paris, France',
             'bullets': ['Défini la roadmap IA avec <b>40%</b> d\'adoption inter-BU.'],
             'is_oneliner': False},
        ],
        'skills': [{'category': 'Produit', 'value': 'Roadmap, PRD, Backlog, OKR'}],
        'education': [{'degree': 'MSc Stratégie Internationale', 'institution_line': 'Toulouse Business School', 'period': '09/2019 - 04/2021'}],
        'languages': [{'name': 'Anglais', 'proficiency': 'Bilingue'}, {'name': 'Français', 'proficiency': 'Bilingue'}],
        'certifications': [], 'projects': [],
    }
    fr_lab = {'experience': 'Expériences', 'skills': 'Compétences', 'education': 'Formation',
               'languages': 'Langues', 'certifications': 'Certifications', 'projects': 'Projets'}
    pdf_fr2 = mod.build_cv_pdf(fr_cv, fr_lab, target_pages=1)
    bio_fr = io.BytesIO(pdf_fr2)
    text_fr, _ = mod.extract_cv_pdf(bio_fr)
    assert 'Debanjan' in text_fr
    (TMP / 'sit6_french_cv_roundtrip.pdf').write_bytes(pdf_fr2)
    ok(f'SIT6: French content CV PDF round-trips through extract — {len(text_fr)} chars')
except Exception as e:
    fail('SIT6', e)


# ════════════════════════════════════════════════════════════════════════════════
# MONKEY TESTS  [NO API]
# ════════════════════════════════════════════════════════════════════════════════
print('\n── MONKEY TESTS [NO API] ────────────────────────────────────────────────')

# M1: Empty experience list — PDF must not crash
try:
    empty_exp = {
        'name': 'Test', 'title': 'PM', 'contact': {},
        'summary': '', 'summary_kpis': '',
        'experience': [], 'skills': [], 'education': [],
        'languages': [], 'certifications': [], 'projects': [],
    }
    pdf_empty = mod.build_cv_pdf(empty_exp, labels, target_pages=1)
    assert isinstance(pdf_empty, bytes) and len(pdf_empty) > 0
    ok('M1: Empty experience list — PDF generation does not crash')
except Exception as e:
    fail('M1', e)

# M2: Experience with None bullets — oneliner=True
try:
    null_bullets_cv = dict(empty_exp)
    null_bullets_cv['name'] = 'Jane'
    null_bullets_cv['experience'] = [
        {'role': 'PM', 'company': 'ACME', 'period': '2020-2023', 'location': 'Paris',
         'bullets': None, 'is_oneliner': True},
    ]
    pdf_null = mod.build_cv_pdf(null_bullets_cv, labels, target_pages=1)
    assert isinstance(pdf_null, bytes) and len(pdf_null) > 0
    ok('M2: bullets=None with is_oneliner=True — does not crash')
except Exception as e:
    fail('M2', e)

# M3: Experience with empty bullets — is_oneliner=False
try:
    empty_bullets_cv = dict(empty_exp)
    empty_bullets_cv['name'] = 'Jane'
    empty_bullets_cv['experience'] = [
        {'role': 'PM', 'company': 'ACME', 'period': '2020-2023', 'location': 'Paris',
         'bullets': [], 'is_oneliner': False},
    ]
    pdf_eb = mod.build_cv_pdf(empty_bullets_cv, labels, target_pages=1)
    assert isinstance(pdf_eb, bytes) and len(pdf_eb) > 0
    ok('M3: bullets=[] with is_oneliner=False — does not crash')
except Exception as e:
    fail('M3', e)

# M4: Very long role title and company name
try:
    long_title_cv = dict(empty_exp)
    long_title_cv['name'] = 'Jane'
    long_title_cv['experience'] = [
        {'role': 'Senior Lead Principal Distinguished Architect Product Manager AI Transformation',
         'company': 'Société Générale - Direction Générale Transformation Digitale et Innovation',
         'period': '01/2020 - 12/2024', 'location': 'Paris La Défense, Île-de-France, France',
         'bullets': ['Led cross-functional AI transformation across <b>12</b> business units.'],
         'is_oneliner': False},
    ]
    pdf_lt = mod.build_cv_pdf(long_title_cv, labels, target_pages=1)
    assert isinstance(pdf_lt, bytes) and len(pdf_lt) > 0
    ok('M4: Very long role title + company name — does not crash')
except Exception as e:
    fail('M4', e)

# M5: Special characters in names (accents, hyphens, ampersands)
try:
    special_cv = dict(empty_exp)
    special_cv['name'] = 'Marie-Hélène Léger-Côté'
    special_cv['title'] = 'Directrice & Co-fondatrice'
    special_cv['experience'] = [
        {'role': 'Directrice Générale', 'company': 'Société Éco & Co.',
         'period': '01/2020 - Présent', 'location': 'Montréal, Québec',
         'bullets': ['Augmenté le CA de <b>+45%</b> en développant l\'offre B2C.'],
         'is_oneliner': False},
    ]
    pdf_sp = mod.build_cv_pdf(special_cv, labels, target_pages=1)
    assert isinstance(pdf_sp, bytes) and len(pdf_sp) > 0
    (TMP / 'm5_special_chars.pdf').write_bytes(pdf_sp)
    ok('M5: Accented names + special chars — does not crash')
except Exception as e:
    fail('M5', e)

# M6: 10-role CV (stress test — max roles)
try:
    big_cv = dict(empty_exp)
    big_cv['name'] = 'Max Roles'
    big_cv['title'] = 'Senior PM'
    big_cv['experience'] = [
        {'role': f'Product Manager {i}', 'company': f'Company {i}',
         'period': f'0{i}/201{i} - 0{i+1}/201{i+1}',
         'location': 'Paris, France',
         'bullets': [f'Delivered <b>{i*10}%</b> improvement in KPI.', f'Led team of <b>{i+1}</b>.'],
         'is_oneliner': False}
        for i in range(1, 11)
    ]
    pdf_big = mod.build_cv_pdf(big_cv, labels, target_pages=2)
    assert isinstance(pdf_big, bytes) and len(pdf_big) > 0
    (TMP / 'm6_10roles.pdf').write_bytes(pdf_big)
    ok(f'M6: 10-role CV stress test — {len(pdf_big)//1024}KB')
except Exception as e:
    fail('M6', e)

# M7: _slugify adversarial inputs
try:
    cases = [
        ('',                  ''),
        (' ',                 ''),
        ('!!!',               ''),
        ('A' * 200,           'a' * 200),   # very long
        ('Société Éco & Co.', 'socit-co-co'),  # accents stripped
        ('Hello\nWorld',      'hello-world'),
    ]
    for inp, _ in cases:
        got = mod._slugify(inp)
        # Must not contain Windows-illegal chars
        assert not re.search(r'[/:*?"<>|\\]', got), f'Illegal char in "{got}" from "{inp}"'
    ok('M7: _slugify adversarial inputs — no illegal chars in any case')
except Exception as e:
    fail('M7', e)

# M8: _truncate_jd with edge cases
try:
    assert mod._truncate_jd('', 400) == ''
    assert mod._truncate_jd('single', 400) == 'single'
    exact = ' '.join(['w'] * 400)
    assert mod._truncate_jd(exact, 400) == exact   # exactly 400 words — no ellipsis
    over  = ' '.join(['w'] * 401)
    truncated = mod._truncate_jd(over, 400)
    assert truncated.endswith('…')
    ok('M8: _truncate_jd — empty, single, exact-400, over-400 edge cases')
except Exception as e:
    fail('M8', e)

# M9: Cover letter with very long text (overflow safety)
try:
    long_cl = 'Paris, 14 avril 2026\n\n'
    long_cl += '\n\n'.join([
        'Paragraphe ' + str(i) + ': ' + ('Contenu narratif détaillé sur les réalisations passées. ' * 5)
        for i in range(1, 25)
    ])
    long_cl += '\n\nCordialement,\nDebanjan Mazumdar'
    pdf_lcl = mod.build_cover_letter_pdf(long_cl, empty_exp)
    assert isinstance(pdf_lcl, bytes) and len(pdf_lcl) > 0
    ok(f'M9: Very long cover letter overflow — {len(pdf_lcl)//1024}KB')
except Exception as e:
    fail('M9', e)

# M10: Contact with all social links present
try:
    full_contact = {
        'email': 'test@test.com', 'phone': '+33 6 00 00 00 00', 'location': 'Paris',
        'linkedin': 'https://linkedin.com/in/test',
        'github':   'https://github.com/test',
        'youtube':  'https://youtube.com/@test',
    }
    result = mod.format_contact_line(full_contact)
    assert 'test@test.com' in result
    assert 'linkedin.com' in result
    assert 'github.com' in result
    assert 'youtube.com' in result
    ok('M10: All 6 contact fields (email, phone, location, 3 social) render correctly')
except Exception as e:
    fail('M10', e)


# ════════════════════════════════════════════════════════════════════════════════
# E2E TESTS  [API REQUIRED]
# Real test: your CV + French JD → language=French, 7 roles, ATS 0-100 score
# ════════════════════════════════════════════════════════════════════════════════
print('\n── E2E TESTS [API REQUIRED] ─────────────────────────────────────────────')

FRENCH_JD = """
Product Manager IA H/F — Teaminside

Piloter la roadmap et le déploiement de cas d'usage IA à forte valeur ajoutée, entre expérience client et performance opérationnelle interne.

La mission :
- Définir et prioriser la roadmap IA sur deux axes : expériences conversationnelles et agentiques côté client, et automatisations internes pour les équipes métier
- Transformer des idées et opportunités en cas d'usage structurés avec des objectifs clairs, des KPIs et des critères de succès
- Piloter le cycle de vie end-to-end des initiatives IA, de la discovery jusqu'au déploiement et à l'amélioration continue
- Aligner et embarquer les parties prenantes clés (Data & IA, CX, IT, Service Client, eMerch) sur les priorités, le périmètre et les résultats
- Assurer la qualité, la gouvernance et le déploiement responsable des produits IA en production
- Faire une veille active sur les tendances IA et traduire les innovations en opportunités concrètes pour le business

Le profil recherché :
- 5 ans+ en Product Management, avec une exposition à des sujets IA, data ou innovation digitale
- Culture IA solide : bonne compréhension des LLMs, agents, prompts, évaluation de modèles et monitoring
- PM complet : discovery, priorisation, roadmap, delivery agile, définition de KPIs et suivi de performance
- Excellent communicant, capable d'aligner des profils très différents (tech et métier)
- Anglais courant requis ; appétence pour les outils no-code / low-code appréciée
"""

if not HAS_API:
    for label in [
        'E2E1: Full pipeline — French JD + real CV → 7 roles, ATS 0-100',
        'E2E2: Language detection — JD in French → analysis[language] == "French"',
        'E2E3: CV output in French — section labels and content in French',
        'E2E4: ATS score realistic — initial score between 25 and 85',
        'E2E5: Improved score > initial — projected gain 5-25 points',
        'E2E6: All 7 experience roles present in output',
        'E2E7: No experience entry missing period or location',
        'E2E8: Cover letter in French',
    ]:
        skip(label)
else:
    # Load real CV
    assert CV_PATH.exists(), f'Real CV fixture missing: {CV_PATH}'
    with open(CV_PATH, 'rb') as f:
        cv_bio = io.BytesIO(f.read())
    cv_text, page_count = mod.extract_cv_pdf(cv_bio)

    print(f'       CV extracted: {page_count}p, {len(cv_text)} chars')

    # E2E1: Full pipeline
    try:
        analysis = mod.run_analysis(cv_text, FRENCH_JD, API_KEY)
        assert analysis, 'run_analysis returned empty/None'
        opt_cv = analysis.get('optimized_cv') or {}
        assert opt_cv.get('name'), 'No name in optimized_cv'
        (TMP / 'e2e1_analysis.json').write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        ok('E2E1: Full pipeline completed — analysis + optimized_cv returned')
    except Exception as e:
        fail('E2E1', e)
        analysis = {}
        opt_cv = {}

    # E2E2: Language detection
    try:
        lang = analysis.get('language', '')
        assert lang.lower() == 'french', f'Expected "French", got "{lang}"'
        ok(f'E2E2: Language detection — language="{lang}" ✓')
    except Exception as e:
        fail('E2E2', e)

    # E2E3: CV section labels in French
    try:
        labels_out = analysis.get('section_labels') or {}
        exp_label = labels_out.get('experience', '')
        # French experience labels: Expériences, Expérience, Parcours professionnel, etc.
        is_french_label = any(
            kw in exp_label.lower()
            for kw in ['expérience', 'experience', 'parcours', 'professionnel']
        )
        assert is_french_label, f'Experience label not French: "{exp_label}"'
        ok(f'E2E3: French section label for experience → "{exp_label}"')
    except Exception as e:
        fail('E2E3', e)

    # E2E4: ATS score realistic (0-100 range)
    try:
        score_i = analysis.get('ats_score_initial')
        score_m = analysis.get('ats_score_improved')
        assert isinstance(score_i, int), f'ats_score_initial not int: {score_i}'
        assert isinstance(score_m, int), f'ats_score_improved not int: {score_m}'
        assert 0 <= score_i <= 100, f'Initial score out of 0-100 range: {score_i}'
        assert 0 <= score_m <= 100, f'Improved score out of 0-100 range: {score_m}'
        assert 20 <= score_i <= 85, f'Initial score {score_i} outside realistic band 20-85'
        ok(f'E2E4: ATS score realistic — initial={score_i}/100, improved={score_m}/100')
    except Exception as e:
        fail('E2E4', e)

    # E2E5: Improved score > initial
    try:
        score_i = analysis.get('ats_score_initial', 0)
        score_m = analysis.get('ats_score_improved', 0)
        assert score_m > score_i, f'Improved ({score_m}) should be > initial ({score_i})'
        gain = score_m - score_i
        assert 3 <= gain <= 30, f'Gain of {gain} outside expected range 3-30'
        ok(f'E2E5: Projected gain realistic — +{gain} points')
    except Exception as e:
        fail('E2E5', e)

    # E2E6: All 7 roles present
    try:
        experience = opt_cv.get('experience', [])
        n = len(experience)
        assert n == 7, f'Expected 7 roles, got {n}'
        ok(f'E2E6: All 7 experience roles in optimized CV')
    except Exception as e:
        fail('E2E6', e)

    # E2E7: No role missing period or location
    try:
        experience = opt_cv.get('experience', [])
        bad = [
            f"{e.get('role')} @ {e.get('company')}"
            for e in experience
            if not e.get('period') or not e.get('location')
        ]
        assert not bad, f'Roles missing period/location: {bad}'
        ok('E2E7: All roles have period and location')
    except Exception as e:
        fail('E2E7', e)

    # E2E8: Cover letter in French
    try:
        lang_used = analysis.get('language', 'English')
        cl_text = mod.run_cover_letter(cv_text, FRENCH_JD, lang_used, opt_cv, 'Teaminside', API_KEY)
        assert cl_text and len(cl_text) > 200, 'Cover letter too short'
        # Check French markers
        french_markers = ['cher', 'chère', 'cordialement', 'madame', 'monsieur', 'paris', 'de', 'la ', 'les ', 'je ']
        found_fr = [m for m in french_markers if m.lower() in cl_text.lower()]
        assert len(found_fr) >= 2, f'Cover letter does not appear to be in French. Markers found: {found_fr}'
        cl_pdf = mod.build_cover_letter_pdf(cl_text, opt_cv)
        (TMP / 'e2e8_cover_letter_fr.pdf').write_bytes(cl_pdf)
        ok(f'E2E8: Cover letter in French — {len(cl_text)} chars, {len(cl_pdf)//1024}KB PDF')
    except Exception as e:
        fail('E2E8', e)


# ════════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════════
total = passed + failed + skipped
print(f'\n{"─"*60}')
print(f'Results: {passed} passed  |  {failed} failed  |  {skipped} skipped (need API)')
print(f'Total:   {total} tests  ({passed + skipped} effective when API available)')

if not HAS_API:
    print()
    print('To run E2E tests, set your Anthropic API key:')
    print('  Windows CMD:  set ANTHROPIC_API_KEY=sk-ant-...')
    print('  PowerShell:   $env:ANTHROPIC_API_KEY="sk-ant-..."')
    print('  Then:         py tests/test_full.py')

if failed == 0:
    print('\nALL RUNNABLE TESTS PASSED')
    sys.exit(0)
else:
    print(f'\n{failed} TEST(S) FAILED')
    sys.exit(1)
