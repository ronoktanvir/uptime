"""Strict-parser clause classifier: parity with compile_terms, every failure at once, and no source text."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from uptime.vendor_strict_diagnostics import classify
from uptime.vendor_terms import Document, compile_terms

from test_vendor_catalog import DOC, proposition_document
from test_vendor_model_jobs_runtime import DOC as ASTER
from test_vendor_requirements_89 import NEW_DOC

ROOT = Path(__file__).resolve().parent.parent
INSERTS = ['Halcyon Ferry provides Queue Mesh on the Basin plan.', 'Downtime during scheduled maintenance is excluded.',
           'Northfield Queue Service Level Agreement', '| 99.9 | 10 |', 'Credits are capped at 50% of the monthly fee.']


@pytest.mark.parametrize('source', [DOC, ASTER, NEW_DOC])
def test_accepted_sources_classify_exactly_like_the_parser(source):
    document = Document(**source)
    manifest, report = compile_terms(document), classify(document)
    assert report['unrecognized_clauses'] == [] and report['missing_required'] == [] and report['tier_present']
    assert [row['category'] for row in report['clauses']] == [c['field'] for c in manifest['citations']]
    assert [(row['start'], row['end']) for row in report['clauses']] == [(c['start'], c['end']) for c in manifest['citations']]


@pytest.mark.parametrize('insert', INSERTS)
@pytest.mark.parametrize('position', [0, 3, -1])
def test_first_unread_clause_is_the_clause_the_parser_refuses(insert, position):
    lines = DOC['text'].split('\n')
    lines.insert(position if position >= 0 else len(lines), insert)
    document = Document(**(DOC | {'text': '\n'.join(lines)}))
    with pytest.raises(ValueError) as refused:
        compile_terms(document)
    report = classify(document)
    clause = re.search(r'at clause ([0-9]+)', str(refused.value))
    assert clause and report['unrecognized_clauses'][0] == int(clause[1])


def test_every_unread_clause_and_missing_term_is_reported_at_once():
    document, _ = proposition_document()
    report = classify(Document(**document))
    with pytest.raises(ValueError, match='at clause 1'):
        compile_terms(Document(**document))
    assert len(report['unrecognized_clauses']) > 1
    assert set(report['missing_required']) >= {'vendor', 'agreement'}


def test_the_report_and_command_carry_no_source_text(tmp_path):
    document, _ = proposition_document()
    report = json.dumps(classify(Document(**document)))
    for line in document['text'].split('\n'):
        assert line.strip() not in report
    path = tmp_path / 'source.json'
    path.write_text(json.dumps(document))
    printed = subprocess.run([sys.executable, 'scripts/diagnose_strict_terms.py', str(path)], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
    assert printed.returncode == 0, printed.stderr
    assert json.loads(printed.stdout)['schema'] == 'strict-clause-classification/1'
    assert not any(line.strip() and line.strip() in printed.stdout for line in document['text'].split('\n'))
