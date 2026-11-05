"""Source definitions and server-authorized literal meaning; never infer opaque IDs.

This module deliberately has no model caller, source-name exception or permissive
empty context. Original source/evidence scalars remain immutable.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from typing import Callable

from .contracts import fingerprint

PROTOCOL = 'semantic-literal-bindings/1'
LIST_ROLES = ('symptoms', 'provider_causes', 'exclusions', 'fee_exclusions', 'request_fields')
TELEMETRY_ROLES = ('customer_status', 'provider_status', 'customer_nonqualifying', 'provider_nonqualifying')
ATTESTATIONS = ('complete_source_reviewed', 'conditions_supported', 'overrides_resolved',
                'evidence_meaning_verified', 'scope_verified')
_SEAL = object()


class SemanticBindingRequired(ValueError):
    pass


def literal(value):
    """Only reviewed whitespace equivalence; no case, punctuation or ID folding."""
    if (not isinstance(value, str) or not 0 < len(value) <= 256
            or any((unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} or c.isspace()) and c not in ' \t\r\n\u00a0' for c in value)
            or any(c in value for c in ('\u200b', '\u200c', '\u200d', '\ufeff', '\u00ad'))
            or any(0x202a <= ord(c) <= 0x202e or 0x2066 <= ord(c) <= 0x2069 for c in value)):
        raise SemanticBindingRequired('A bounded explicit literal representation is required.')
    result = ' '.join(value.split())
    if not result:
        raise SemanticBindingRequired('An empty literal cannot establish a source definition.')
    return result


def source_spans(original, phrase):
    """Find full-token occurrences and map them back to original character offsets.

ASCII case matching preserves existing proposed source casing, but each returned
span retains the actual source text. Evidence matching remains case-sensitive.
"""
    try:
        wanted = literal(phrase)
    except SemanticBindingRequired:
        return []
    chars, positions = [], []
    for match in re.finditer(r'\S+', original):
        if chars:
            chars.append(' ')
            positions.append(match.start() - 1)
        chars.extend(match.group())
        positions.extend(range(match.start(), match.end()))
    canonical = ''.join(chars)
    fold = lambda s: ''.join(chr(ord(c) + 32) if 'A' <= c <= 'Z' else c for c in s)
    result = []
    for match in re.finditer(re.escape(fold(wanted)), fold(canonical)):
        a, b = match.span()
        word = lambda c: c.isalnum() or c == '_'
        if (a and word(canonical[a - 1]) and word(canonical[a])) or (b < len(canonical) and word(canonical[b - 1]) and word(canonical[b])):
            continue
        left, right = positions[a], positions[b - 1] + 1
        result.append({'start':left, 'end':right, 'quote':original[left:right]})
    return result


def _declared(citation, role, label):
    values = citation.get('propositions', {})
    if role in LIST_ROLES:
        return (any(item == label or isinstance(item, dict) and item.get('label') == label
                    for item in values.get(role, []))
                or role == 'request_fields' and label in values.get('cure_clock',{}).get('initial_fields',[]))
    if role in TELEMETRY_ROLES:
        item = values.get('telemetry', {}).get(role)
        return label in item if isinstance(item, list) else item == label
    return role == 'maintenance_cause' and values.get('maintenance', {}).get('cause') == label


def definitions(manifest):
    """All free-form roles, with exact possible source occurrences for named review."""
    rows = []
    roles = {role:list(manifest.get(role, [])) for role in LIST_ROLES}
    roles['request_fields'].extend(manifest.get('cure_clock',{}).get('initial_fields',[]))
    for role in TELEMETRY_ROLES:
        value = manifest.get('telemetry', {}).get(role)
        roles[role] = value if isinstance(value, list) else [value] if value else []
    cause = manifest.get('maintenance', {}).get('cause')
    roles['maintenance_cause'] = [cause] if cause else []
    for role, labels in roles.items():
        for label in dict.fromkeys(labels):
            binding = manifest.get('label_bindings', {}).get(role, {}).get(label)
            phrase = binding['phrase'] if binding else label
            citations = [c for c in manifest['citations'] if
                         (binding and c['id'] == binding['block'] or not binding and _declared(c, role, label))]
            # The compiler derives these two literals from separately attributed telemetry.
            if not citations and role in ('symptoms', 'provider_causes') and manifest.get('telemetry'):
                original_role = 'customer_status' if role == 'symptoms' else 'provider_status'
                citations = [c for c in manifest['citations'] if _declared(c, original_role, label)]
            spans = []
            for citation in citations:
                original = citation['quote']
                if sha256(original.encode()).hexdigest() != citation['block_sha256']:
                    raise SemanticBindingRequired('Source citation integrity requires review.')
                for span in source_spans(original, phrase):
                    span.update(start=span['start'] + citation['start'], end=span['end'] + citation['start'],
                                block=citation['id'], block_sha256=citation['block_sha256'])
                    span['id'] = fingerprint({'source':manifest['document']['sha256'], 'role':role, **span})
                    spans.append(span)
            row = {'role':role, 'label':label, 'phrase':phrase, 'opaque':binding is not None, 'spans':spans}
            row['id'] = fingerprint({'source':manifest['document']['sha256'], **row})
            rows.append(row)
    if manifest.get('fee_exclusions'):
        # A nonmatching excluded category is not evidence of inclusion. The
        # already-supported fee-basis operator supplies the source anchor for
        # an explicit positive category review; no new fee grammar is inferred.
        effect = 'service_fee' if manifest.get('service_fee') else 'fee_basis'
        citations = [c for c in manifest['citations'] if effect in c.get('propositions',{})]
        spans=[]
        for citation in citations:
            if sha256(citation['quote'].encode()).hexdigest()!=citation['block_sha256']:
                raise SemanticBindingRequired('Source citation integrity requires review.')
            span={k:citation[k] for k in ('start','end','quote','block_sha256')}
            span['block']=citation['id']
            span['id']=fingerprint({'source':manifest['document']['sha256'],'role':'fee_inclusions',**span})
            spans.append(span)
        row={'role':'fee_inclusions','label':effect,'phrase':'Reviewed included charge categories under the cited fee basis',
             'opaque':False,'spans':spans}
        row['id']=fingerprint({'source':manifest['document']['sha256'],**row})
        rows.append(row)
    return rows


def required(manifest):
    # An exact operator/whole-block proof may be introduced by a separately
    # reviewed compiler version. No vendor or family is exempted here.
    return bool(definitions(manifest))


def dependency(manifest):
    files = ('vendor_bindings.py', 'vendor_resource_terms.py', 'vendor_resource_eval.py',
             'vendor_resource_scopes.py', 'vendor_service_month.py', 'correspondence_resource.py',
             'correspondence_service.py', 'correspondence_history.py', 'v4_routes.py', 'vendor_registry.py')
    return fingerprint({'protocol':PROTOCOL, 'definitions':definitions(manifest), 'source':manifest['document']['sha256'],
                        'files':{name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in files}})


def requirements(manifest, overlay, source_text):
    if sha256(source_text.encode()).hexdigest() != manifest['document']['sha256']:
        raise SemanticBindingRequired('Complete source does not match its recorded digest.')
    return {'protocol':PROTOCOL, 'source_sha256':manifest['document']['sha256'], 'source_text':source_text,
            'source_uri':manifest['document']['uri'], 'manifest_sha256':fingerprint(manifest),
            'overlay_sha256':fingerprint(overlay), 'dependency_sha256':dependency(manifest),
            'definitions':definitions(manifest), 'attestations':list(ATTESTATIONS),
            'blocks':[{'block':c['id'], 'block_sha256':c['block_sha256'], 'quote':c['quote'],
                       'effects':sorted(c.get('propositions', {}))} for c in manifest['citations']]}


def review_record(manifest, overlay, source_text, tenant, reviewer, submitted, at):
    """Validate an explicitly signed reviewer selection; caller establishes authority."""
    needed = requirements(manifest, overlay, source_text)
    allowed = {'source_sha256', 'manifest_sha256', 'overlay_sha256', 'dependency_sha256',
               'bindings', 'block_reviews', 'attestations'}
    if not isinstance(submitted, dict) or set(submitted) != allowed:
        raise SemanticBindingRequired('An exact semantic review payload is required.')
    if any(submitted[k] != needed[k] for k in allowed - {'bindings', 'block_reviews', 'attestations'}):
        raise SemanticBindingRequired('Semantic review does not match the current source, scope or dependencies.')
    if (not isinstance(submitted['attestations'],dict) or set(submitted['attestations']) != set(ATTESTATIONS)
            or any(value is not True for value in submitted['attestations'].values())):
        raise SemanticBindingRequired('The named reviewer must resolve source meaning, conditions, overrides and evidence scope.')
    block_reviews = submitted['block_reviews']
    if not isinstance(block_reviews, list) or len(block_reviews) != len(needed['blocks']):
        raise SemanticBindingRequired('Review every source block, including governing conditions and overrides.')
    for given, expected in zip(block_reviews, needed['blocks'], strict=True):
        if (not isinstance(given, dict) or set(given) != {'block', 'block_sha256', 'effects', 'conditions_and_overrides'}
                or any(given[k] != expected[k] for k in ('block', 'block_sha256', 'effects'))
                or not isinstance(given['conditions_and_overrides'], str)
                or not 1 <= len(given['conditions_and_overrides'].strip()) <= 1000):
            raise SemanticBindingRequired('Each block needs an exact supported-effect and condition review.')
    supplied = submitted['bindings']
    if not isinstance(supplied, list) or len(supplied) != len(needed['definitions']):
        raise SemanticBindingRequired('Each source definition needs an explicit literal binding.')
    selected, seen, collisions = [], set(), {}
    index = {d['id']:d for d in needed['definitions']}
    for row in supplied:
        if not isinstance(row, dict) or set(row) != {'definition_id', 'span_id', 'literals'}:
            raise SemanticBindingRequired('Unexpected semantic binding fields.')
        definition = index.get(row['definition_id'])
        if definition is None or row['definition_id'] in seen:
            raise SemanticBindingRequired('Missing, duplicate or foreign definition binding.')
        seen.add(row['definition_id'])
        spans = {span['id']:span for span in definition['spans']}
        if row['span_id'] not in spans:
            raise SemanticBindingRequired('The selected source occurrence is absent or lacks token boundaries.')
        values = row['literals']
        if not isinstance(values, list) or not 1 <= len(values) <= 30:
            raise SemanticBindingRequired('Supply bounded explicit literal representations.')
        canonical = [literal(value) for value in values]
        if len(set(canonical)) != len(canonical):
            raise SemanticBindingRequired('Duplicate literal representations are ambiguous.')
        for value in canonical:
            key = (definition['role'], value)
            if key in collisions and collisions[key] != row['span_id']:
                raise SemanticBindingRequired('A literal names conflicting definitions in the same role.')
            collisions[key] = row['span_id']
        selected.append({**row, 'role':definition['role'], 'label':definition['label'], 'canonical_literals':canonical})
    if ({v for role,v in collisions if role == 'provider_causes'} &
            {v for role,v in collisions if role == 'exclusions'}):
        raise SemanticBindingRequired('The same causal literal cannot establish both inclusion and exclusion.')
    if ({v for role,v in collisions if role == 'fee_inclusions'} &
            {v for role,v in collisions if role == 'fee_exclusions'}):
        raise SemanticBindingRequired('The same fee literal cannot establish both inclusion and exclusion.')
    return {'protocol':PROTOCOL, 'tenant':tenant, 'reviewer':reviewer, 'reviewed_at':at,
            'source_sha256':needed['source_sha256'], 'manifest_sha256':needed['manifest_sha256'],
            'overlay_sha256':needed['overlay_sha256'], 'dependency_sha256':needed['dependency_sha256'],
            'bindings':selected, 'block_reviews':block_reviews, 'attestations':submitted['attestations']}


@dataclass(frozen=True)
class BindingContext:
    digest: str
    tenant: str
    manifest_sha256: str
    overlay_sha256: str
    dependency_sha256: str
    entries: tuple
    _current: Callable[[], bool]
    _seal: object

    def check(self):
        try:
            if self._seal is not _SEAL or self._current() is not True:
                raise SemanticBindingRequired('Semantic binding is absent, changed or revoked.')
        except SemanticBindingRequired:
            raise
        except Exception:
            raise SemanticBindingRequired('Current semantic binding authority is unavailable.') from None

    def targets(self, role, raw):
        self.check()
        value = literal(raw)
        return frozenset(label for entry_role, label, values in self.entries if entry_role == role and value in values)

    def resolve(self, role, raw):
        targets = self.targets(role, raw)
        if not targets:
            raise SemanticBindingRequired('Observed literal has no reviewed definition in its evidence role.')
        return targets

    def representations(self, role, label):
        self.check()
        return frozenset(value for entry_role, key, values in self.entries if entry_role == role and key == label for value in values)


def _from_record(record, current):
    """Server loader only; request JSON cannot supply the private seal or live checker."""
    return BindingContext(fingerprint(record), record['tenant'], record['manifest_sha256'], record['overlay_sha256'],
                          record['dependency_sha256'], tuple((r['role'], r['label'], tuple(r['canonical_literals']))
                          for r in record['bindings']), current, _SEAL)


def require_context(manifest, overlay, tenant, context):
    if not required(manifest):
        return None
    if (not isinstance(context, BindingContext) or context.tenant != tenant
            or context.manifest_sha256 != fingerprint(manifest) or context.overlay_sha256 != fingerprint(overlay)
            or context.dependency_sha256 != dependency(manifest)):
        raise SemanticBindingRequired('Named source and evidence semantic binding review is required before monetary evaluation.')
    context.check()
    return context
