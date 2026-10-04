#!/usr/bin/env python3
"""Mechanical PRE/RP draft checks. No network, rewrites, or AI detection.

Python 3.10+. Exit 0: no mechanical errors; 1: errors found; 2: input/config error.
A passing result is NOT evidence that a draft is true, compliant, or ready to submit.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

METRICS = {
    'words_whitespace', 'words_english_regex', 'characters_including_spaces',
    'characters_excluding_whitespace', 'utf16_code_units', 'cjk_characters'
}
PLACEHOLDERS = re.compile(
    r'\{\{[^{}\n]{1,120}\}\}|\[(?:\[)?(?:TODO|TBD|待补充|待填写|待确认|待核实|INSERT|Applicant name|Programme|Entry year|Working title)[^\]\n]{0,120}\](?:\])?|\b(?:TODO|TBD)\b',
    re.IGNORECASE
)
STYLE_PATTERNS = [
    r'\bgroundbreaking\b', r'\brevolutionary\b', r'\bunparalleled\b',
    r'\bprofound passion\b', r'\bworld[- ]class\b',
    r'\bpassionate about\b', r'\balways been interested\b',
    r'\bcutting[- ]edge\b', r'\bexcellent reputation\b',
    r'\bprestigious university\b', r'\binternationally renowned\b',
    r'\bteamwork and leadership\b', r'\bbroaden my horizons?\b',
    r'\bholistic\b', r'\bdelve\b', r'\btapestry\b', r'\blandscape of\b',
    r'\bnot only .{0,40} but also\b',
    r'\bthis experience (?:strengthened|deepened|enhanced)\b',
    r'填补(?:了)?(?:研究)?空白', r'颠覆性', r'赋能', r'注入新活力'
]

def count_text(text: str) -> dict[str, int]:
    """Normalize CRLF/CR to LF, but retain all spaces and all line breaks."""
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    return {
        'raw_characters_including_spaces': len(text),
        'characters_including_spaces': len(normalized),
        'characters_excluding_whitespace': len(re.sub(r'\s', '', normalized)),
        'utf16_code_units': len(normalized.encode('utf-16-le')) // 2,
        'words_whitespace': len(normalized.split()),
        'words_english_regex': len(re.findall(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*", normalized)),
        'cjk_characters': sum(1 for c in normalized if '\u3400' <= c <= '\u4dbf' or '\u4e00' <= c <= '\u9fff' or 0x20000 <= ord(c) <= 0x3134f),
    }

def validate_requirements(req: Any) -> dict[str, Any]:
    if not isinstance(req, dict):
        raise ValueError('Requirements must be a JSON object.')
    limits=req.get('limits', [])
    if not isinstance(limits, list):
        raise ValueError('limits must be an array.')
    for entry in limits:
        if not isinstance(entry, dict) or entry.get('metric') not in METRICS:
            raise ValueError('Each limit needs a supported metric: '+', '.join(sorted(METRICS)))
        if 'max' not in entry and 'min' not in entry:
            raise ValueError('Each limit needs max or min.')
        for key in ('max','min'):
            if key in entry and (type(entry[key]) is not int or entry[key] < 0):
                raise ValueError(f'{key} must be a nonnegative integer.')
        if entry.get('min', 0) > entry.get('max', sys.maxsize):
            raise ValueError('min cannot exceed max.')
    for key in ('required_literals','forbidden_literals','protected_literals'):
        values=req.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError(f'{key} must be an array of non-empty strings.')
    return req

def contains_literal(text: str, literal: str, *, case_sensitive: bool=False) -> bool:
    """ASCII boundary guards avoid MIT matching the letters within submitted."""
    pattern=re.escape(literal)
    if literal[0].isascii() and literal[0].isalnum(): pattern=r'(?<![A-Za-z0-9_])'+pattern
    if literal[-1].isascii() and literal[-1].isalnum(): pattern+=r'(?![A-Za-z0-9_])'
    return re.search(pattern,text,flags=0 if case_sensitive else re.IGNORECASE) is not None

def audit_text(text: str, requirements: dict[str, Any] | None=None) -> dict[str, Any]:
    req=validate_requirements({} if requirements is None else requirements)
    normalized=text.replace('\r\n','\n').replace('\r','\n')
    counts=count_text(text)
    errors: list[dict[str, Any]]=[]
    warnings: list[dict[str, Any]]=[]
    if not normalized.strip(): errors.append({'code':'empty_draft','message':'Draft is empty.'})
    for entry in req.get('limits',[]):
        actual=counts[entry['metric']]
        if 'max' in entry and actual>entry['max']:
            errors.append({'code':'over_limit','metric':entry['metric'],'actual':actual,'max':entry['max']})
        if 'min' in entry and actual<entry['min']:
            errors.append({'code':'under_limit','metric':entry['metric'],'actual':actual,'min':entry['min']})
    for match in PLACEHOLDERS.finditer(normalized):
        errors.append({'code':'placeholder','text':match.group(0),'line':normalized.count('\n',0,match.start())+1})
    for literal in req.get('forbidden_literals',[]):
        if contains_literal(normalized,literal): errors.append({'code':'forbidden_literal','text':literal})
    for literal in req.get('required_literals',[]):
        if not contains_literal(normalized,literal): errors.append({'code':'missing_required_literal','text':literal})
    for literal in req.get('protected_literals',[]):
        if not contains_literal(normalized,literal,case_sensitive=True):
            warnings.append({'code':'protected_literal_missing_or_changed','text':literal,'message':'Check against the source; omission is not proof of an error.'})
    for pattern in STYLE_PATTERNS:
        matches=list(re.finditer(pattern,normalized,re.IGNORECASE))
        if matches:
            warnings.append({'code':'style_review_only','text':matches[0].group(0),'occurrences':len(matches),'message':'Contextual review signal, not a banned word or evidence of AI authorship.'})
    if req.get('ai_policy_status') in (None,'unknown'):
        warnings.append({'code':'policy_not_confirmed','message':'Target AI policy has not been confirmed in this configuration.'})
    return {
        'status':'mechanical_errors_found' if errors else 'no_mechanical_errors_found',
        'counts':counts,'errors':errors,'warnings':warnings,
        'count_scope_note':req.get('count_scope_note','Entire input; bibliography/headings are NOT automatically excluded.'),
        'count_method':'CRLF/CR normalized to LF; spaces and line breaks retained. Whitespace-token and ASCII-word counts are approximations, not portal-authoritative counts. UTF-16 differs from Unicode code points for some characters.',
        'manual_checks_required':['Truth and personal attribution','Research status and certainty','Question-method fit and feasibility','Actual target prompt, AI policy and declaration','Citation existence and relevance','Document rendering and portal count'],
        'not_an_ai_detector':True,
        'submission_ready_not_established':True,
    }

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('draft',type=Path,help='UTF-8 plain text with the intended count scope')
    parser.add_argument('--requirements',type=Path)
    parser.add_argument('--output',type=Path,help='Optional JSON report; never modifies the draft')
    args=parser.parse_args()
    try:
        with args.draft.open('r',encoding='utf-8',newline='') as handle: text=handle.read()
        req=json.loads(args.requirements.read_text(encoding='utf-8')) if args.requirements else {}
        report=audit_text(text,req)
        rendered=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        if args.output:
            if args.output.resolve()==args.draft.resolve() or (args.requirements and args.output.resolve()==args.requirements.resolve()):
                raise ValueError('Output must not overwrite the draft or requirements file.')
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(rendered,encoding='utf-8')
        else: print(rendered,end='')
        return 1 if report['errors'] else 0
    except (OSError,UnicodeError,ValueError) as exc:
        print(f'audit_draft: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
