"""Changing monthly admission or evidence meaning invalidates prior adapter versions."""
import os
from pathlib import Path
import subprocess
import sys


def test_every_monthly_admission_dependency_changes_reviewed_version():
    # Isolate module reload from the test process and registry imports. No files
    # are altered; the source reader receives a one-byte change for each input.
    script = r"""
import importlib
from pathlib import Path
from uptime import vendor_terms
original = Path.read_bytes
baseline = vendor_terms.SEMANTICS_REVISIONS[vendor_terms.REVISION]
for name in ('vendor_monthly_basis.py', 'correspondence_monthly.py', 'claim_scope.py',
             'correspondence_types.py', 'v4_routes.py', 'evidence_applicability.py'):
    def changed(path):
        value = original(path)
        return value + b'\n' if path.name == name else value
    Path.read_bytes = changed
    importlib.reload(vendor_terms)
    assert vendor_terms.SEMANTICS_REVISIONS[vendor_terms.REVISION] != baseline, name
Path.read_bytes = original
importlib.reload(vendor_terms)
assert vendor_terms.SEMANTICS_REVISIONS[vendor_terms.REVISION] == baseline
"""
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, '-c', script], cwd=root,
                               env=dict(os.environ, PYTHONPATH=str(root)),
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
