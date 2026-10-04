import importlib.util
from pathlib import Path
import unittest
SPEC=importlib.util.spec_from_file_location('audit_draft',Path(__file__).resolve().parents[1]/'scripts'/'audit_draft.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)

class AuditTests(unittest.TestCase):
    def test_ascii_counts(self):
        self.assertEqual(m.count_text('A B')['characters_including_spaces'],3)
        self.assertEqual(m.count_text('A B')['words_whitespace'],2)
    def test_chinese_not_english_words(self):
        c=m.count_text('研究计划');self.assertEqual(c['cjk_characters'],4);self.assertEqual(c['words_english_regex'],0)
    def test_emoji_utf16(self):
        c=m.count_text('A😀');self.assertEqual(c['characters_including_spaces'],2);self.assertEqual(c['utf16_code_units'],3)
    def test_line_endings_explicit(self):
        c=m.count_text('A\r\nB');self.assertEqual(c['raw_characters_including_spaces'],4);self.assertEqual(c['characters_including_spaces'],3)
    def test_whitespace(self):
        self.assertEqual(m.count_text('A\t B\n C')['characters_excluding_whitespace'],3)
    def test_exact_limit_passes(self):
        r=m.audit_text('A B',{'limits':[{'metric':'words_whitespace','max':2}]});self.assertFalse(r['errors'])
    def test_over_limit(self):
        r=m.audit_text('A B C',{'limits':[{'metric':'words_whitespace','max':2}]});self.assertEqual(r['errors'][0]['code'],'over_limit')
    def test_char_limit_is_not_word_limit(self):
        r=m.audit_text('A B',{'limits':[{'metric':'characters_including_spaces','max':2}]});self.assertTrue(r['errors'])
    def test_under_limit(self):
        r=m.audit_text('A',{'limits':[{'metric':'words_whitespace','min':2}]});self.assertEqual(r['errors'][0]['code'],'under_limit')
    def test_placeholder_zh(self):
        self.assertTrue(any(e['code']=='placeholder' for e in m.audit_text('结果[待补充]')['errors']))
    def test_placeholder_curly(self):
        self.assertTrue(m.audit_text('{{METHOD}}')['errors'])
    def test_placeholder_route(self):
        self.assertTrue(m.audit_text('[Applicant name]')['errors'])
    def test_numeric_citation_not_placeholder(self):
        self.assertFalse(m.audit_text('As reported [12].')['errors'])
    def test_robust_regression_preserved(self):
        r=m.audit_text('I used robust regression.');self.assertFalse(any(w['code']=='style_review_only' for w in r['warnings']))
    def test_style_is_warning_only(self):
        r=m.audit_text('A groundbreaking project.');self.assertFalse(r['errors']);self.assertTrue(any(w['code']=='style_review_only' for w in r['warnings']))
    def test_literal_boundary(self):
        self.assertFalse(m.contains_literal('We submitted the draft.','MIT'))
    def test_wrong_school(self):
        r=m.audit_text('I want to study at Caltech.',{'forbidden_literals':['Caltech']});self.assertTrue(r['errors'])
    def test_required_heading(self):
        self.assertTrue(m.audit_text('Introduction',{'required_literals':['Research question']})['errors'])
    def test_protected_term_warns(self):
        r=m.audit_text('Our results support an association.',{'protected_literals':['preliminary']});self.assertTrue(any(w['code']=='protected_literal_missing_or_changed' for w in r['warnings']))
    def test_invalid_metric(self):
        with self.assertRaises(ValueError):m.audit_text('x',{'limits':[{'metric':'tokens','max':2}]})
    def test_invalid_bool_limit(self):
        with self.assertRaises(ValueError):m.audit_text('x',{'limits':[{'metric':'words_whitespace','max':True}]})
    def test_invalid_root(self):
        with self.assertRaises(ValueError):m.validate_requirements([])
    def test_no_false_ready_claim(self):
        r=m.audit_text('I prepared a draft.');self.assertTrue(r['submission_ready_not_established']);self.assertTrue(r['not_an_ai_detector'])
    def test_empty(self):
        self.assertEqual(m.audit_text(' \n')['errors'][0]['code'],'empty_draft')

if __name__=='__main__':unittest.main()
