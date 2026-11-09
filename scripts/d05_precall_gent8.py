#!/usr/bin/env python3
"""Pre-call checks for the D05 unseen-vendor proof (no model, no server, no parsing of the document).

Verifies, without revealing the sealed vendor: the SHA-256 commitments recorded in
docs/v4/evaluation-gent8/D05-SELECTION-RECORD.md (branch work/release-evaluation-gent8), snapshot
integrity, that D05 phase 2 is merged into the tested commit, that the frozen document satisfies the
application's input contract (uptime.vendor_terms.Document and _validate_document only; the rule
parser and selection are NOT run), the pinned CLI identity, and that no tracked file names the vendor.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SEALED = Path(os.environ.get('UPTIME_D05_SEALED', Path.home() / '.local/share/uptime-engineering/review/d05-unseen-vendor'))
COMMITMENTS = {'frame.json': '0a1e4ca19f33514f02ae16189addc64bd7e1273b09588b0019a4e0260e75b6b3',
               'selection.json': 'b704d99d2052dcaf5d8298c29143e02d55493b2989d4eb5231e8ebb08f12221c',
               'sealed-bundle.json': '625f93470b222ffd5ac6a1303fa1655eb59f002521fd2d7dc3e223c635b42958',
               'amendment-1.json': '6e8c8ea323902c3e8ed8d3a1c706d68a0cf30b20ca0b1034160d5ad2bee3a360'}
EXTRACTOR_SHA256 = '86e56f5a0c9696fa99782f72f995ed3259b561d85d77e41be512a764850b17e9'
PHASE2 = 'f1a37a1'


def _git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


def checks(cli=None):
    out = {}
    out['commitments'] = {name: sha256((SEALED / name).read_bytes()).hexdigest() == digest for name, digest in COMMITMENTS.items()}
    selection = json.loads((SEALED / 'selection.json').read_bytes())
    vendor = selection['selected']
    folder = SEALED / 'candidates' / vendor
    snapshot = json.loads((folder / 'snapshot.json').read_bytes())
    document_bytes = (folder / 'document.json').read_bytes()
    out['snapshot'] = {'document_sha256_matches': sha256(document_bytes).hexdigest() == snapshot['document_sha256'],
                       'raw_sha256_matches': sha256((folder / 'page.html').read_bytes()).hexdigest() == snapshot['raw_sha256'],
                       'extractor_matches_preregistration': snapshot['extractor_sha256'] == EXTRACTOR_SHA256,
                       'document_sha256': snapshot['document_sha256']}
    head = _git('rev-parse', 'HEAD').stdout.strip()
    out['source'] = {'head': head, 'clean': _git('status', '--porcelain').stdout.strip() == '',
                     'phase2_merged': _git('merge-base', '--is-ancestor', PHASE2, 'HEAD').returncode == 0,
                     'selection_module_present': (ROOT / 'uptime/vendor_family_selection.py').is_file()}
    from uptime.vendor_terms import Document, _validate_document
    document = Document.model_validate(json.loads(document_bytes))
    _validate_document(document)  # input contract only: classification, HTTPS provenance, encoding
    out['document_contract'] = {'accepted': True, 'classification': document.classification, 'characters': len(document.text)}
    hits = _git('grep', '-i', '-l', '-w', vendor, 'HEAD', '--', '.').stdout.split()
    out['blinding'] = {'tracked_files_naming_vendor': len(hits)}
    if cli:
        version = subprocess.run([cli, '--version'], capture_output=True, text=True, timeout=10).stdout.strip()
        out['cli'] = {'path': cli, 'version': version, 'sha256': sha256(Path(cli).read_bytes()).hexdigest()}
    out['ready'] = (all(out['commitments'].values()) and all(v for k, v in out['snapshot'].items() if k != 'document_sha256')
                    and out['source']['clean'] and out['source']['phase2_merged'] and out['source']['selection_module_present']
                    and out['blinding']['tracked_files_naming_vendor'] == 0)
    return out


if __name__ == '__main__':
    print(json.dumps(checks(sys.argv[1] if len(sys.argv) > 1 else None), indent=2))
