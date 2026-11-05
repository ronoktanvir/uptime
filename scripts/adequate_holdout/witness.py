"""Fail-closed observation accounting, independent of the application."""
from collections import Counter
from hashlib import sha256
import json

LABEL = 'new independently frozen adequate-evidence cases under a studied public vendor source'
ADDITIVE_LABEL = 'explicitly new additive fully specified local cases under a studied public vendor source'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return sha256(value).hexdigest()


class Witness:
    def __init__(self, required):
        self.required = tuple(required)
        if not self.required or len(set(self.required)) != len(self.required):
            raise ValueError('A nonempty unique observation schedule is required')
        self.rows = {}

    def record(self, name, *, measured, passed, evidence=None, reason=None):
        if name not in self.required or name in self.rows:
            raise ValueError('Unknown or duplicate observation')
        if passed and (measured is not True or not evidence):
            raise ValueError('A green result requires an actual measured evidence digest')
        if evidence is not None and (len(evidence) != 64 or any(c not in '0123456789abcdef' for c in evidence)):
            raise ValueError('Evidence must be SHA-256')
        self.rows[name] = dict(measured=bool(measured), passed=bool(passed), evidence_sha256=evidence, reason=reason)

    def report(self):
        rows = {name: self.rows.get(name, dict(measured=False, passed=False, evidence_sha256=None,
                                             reason='NOT_MEASURED')) for name in self.required}
        passed = sum(r['passed'] and r['measured'] for r in rows.values())
        measured = sum(r['measured'] for r in rows.values())
        return dict(required=len(rows), measured=measured, passed=passed, failed=measured-passed,
                    unmeasured=len(rows)-measured, all_green=passed == len(rows),
                    reasons=dict(Counter(r['reason'] for r in rows.values() if r['reason'])), observations=rows)


def verify_freeze(directory):
    manifest_bytes = (directory / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest['label'] not in {LABEL, ADDITIVE_LABEL} or not manifest['preexercise'] or manifest['api_exercised']:
        raise ValueError('Not an independently frozen preexercise cohort')
    if manifest['label'] == ADDITIVE_LABEL and not manifest.get('denominator_separate'):
        raise ValueError('Additive cases require a separate denominator')
    for name, expected in manifest['files'].items():
        if digest((directory / name).read_bytes()) != expected:
            raise ValueError('Frozen file changed: ' + name)
    return manifest, digest(manifest_bytes)
