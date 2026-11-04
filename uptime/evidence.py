"""Typed, display-only public observations; never an entitlement evaluator."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from uptime.contracts import Principal, Source, fingerprint

SOURCE_URI = 'https://status.twilio.com/api/v2/incidents.json'
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / 'fixtures/evidence/twilio.json'
MAX_BYTES = 2_000_000


def instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError('timestamp must be a string')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result


def text(value: object, limit: int = 1000) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('invalid bounded text')
    return value


@dataclass(frozen=True)
class PublicObservation:
    incident_id: str
    label: str
    status: str
    created_at: str | None
    started_at: str | None
    resolved_at: str | None
    updated_at: str | None
    components: tuple[str, ...]
    content_hash: str

    @classmethod
    def parse(cls, row: dict) -> 'PublicObservation':
        if not isinstance(row, dict):
            raise ValueError('observation must be an object')
        fields = {key: row.get(key) for key in ('created_at', 'started_at', 'resolved_at', 'updated_at')}
        for value in fields.values():
            if value is not None:
                instant(value)
        incident_id = text(row['id'], 100)
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', incident_id):
            raise ValueError('invalid incident ID')
        components = row.get('components', [])
        if not isinstance(components, list) or len(components) > 500:
            raise ValueError('invalid components')
        data = dict(incident_id=incident_id, label=text(row['name']), status=text(row['status'], 50),
                    **fields, components=tuple(sorted({text(c['id'], 100) for c in components})))
        return cls(**data, content_hash=fingerprint(data))


@dataclass(frozen=True)
class Snapshot:
    source_uri: str
    observed_at: str
    raw_sha256: str
    observations: tuple[PublicObservation, ...]
    gaps: tuple[str, ...] = ('Recent-incident feed is not complete historical coverage.',)

    def payload(self) -> dict:
        data = asdict(self)
        return {**data, 'snapshot_hash': fingerprint(data)}


def minimize(raw: bytes, metadata: dict) -> Snapshot:
    if len(raw) > MAX_BYTES:
        raise ValueError('feed too large')
    if metadata['url'] != SOURCE_URI or sha256(raw).hexdigest() != metadata['sha256']:
        raise ValueError('intake provenance mismatch')
    instant(metadata['collected_at'])
    document = json.loads(raw)
    rows = document['incidents']
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('invalid incident list')
    observations = tuple(sorted((PublicObservation.parse(row) for row in rows), key=lambda row: row.incident_id))
    if len({row.incident_id for row in observations}) != len(observations):
        raise ValueError('duplicate incident ID')
    return Snapshot(SOURCE_URI, metadata['collected_at'], metadata['sha256'], observations)


def load_snapshot(path: Path = DEFAULT_SNAPSHOT) -> Snapshot:
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('snapshot too large')
    data = json.loads(raw)
    digest = data.pop('snapshot_hash')
    if fingerprint(data) != digest or data['source_uri'] != SOURCE_URI:
        raise ValueError('snapshot integrity mismatch')
    instant(data['observed_at'])
    if not re.fullmatch('[0-9a-f]{64}', data['raw_sha256']):
        raise ValueError('invalid raw hash')
    observations = []
    for row in data['observations']:
        row = dict(row)
        digest = row.pop('content_hash')
        if fingerprint(row) != digest:
            raise ValueError('observation integrity mismatch')
        # Reapply the ingest schema even if an envelope hash was recomputed.
        parsed = PublicObservation.parse(dict(id=row['incident_id'], name=row['label'],
            status=row['status'], components=[{'id': c} for c in row['components']],
            **{k: row[k] for k in ('created_at', 'started_at', 'resolved_at', 'updated_at')}))
        if parsed.content_hash != digest:
            raise ValueError('noncanonical observation')
        observations.append(parsed)
    if len({r.incident_id for r in observations}) != len(observations):
        raise ValueError('duplicate incident ID')
    return Snapshot(data['source_uri'], data['observed_at'], data['raw_sha256'], tuple(observations))


def evidence_summary(path: Path = DEFAULT_SNAPSHOT, *, as_of: datetime | None = None,
                     max_age: timedelta = timedelta(hours=24)) -> dict:
    """Offline replay by default. Freshness is operational, not an SLA rule."""
    tags = [Source.PUBLIC.value, Source.REPLAY.value]
    try:
        snapshot = load_snapshot(path)
    except (OSError, ValueError, KeyError, TypeError):
        return {'sources': [Source.UNAVAILABLE.value], 'items': [], 'state': 'unavailable',
                'gaps': ['Verified snapshot unavailable.'], 'standalone_entitlement': False}
    now = as_of or datetime.now(timezone.utc)
    age = now - instant(snapshot.observed_at)
    state = 'stale' if age > max_age else 'available'
    gaps = list(snapshot.gaps)
    if age < timedelta(0):
        state = 'gap'
        gaps.append('Collection timestamp is after the audit clock.')
    items = []
    for row in snapshot.observations:
        item = asdict(row)
        item.update(label=row.label, detail=f'Public incident: {row.status}; customer impact unverified.',
                    sources=tags, observed_at=snapshot.observed_at, source_uri=SOURCE_URI,
                    ref=f'twilio:{row.incident_id}:{row.content_hash}', untrusted_display_only=True)
        items.append(item)
    return {'sources': tags, 'items': items, 'state': state, 'gaps': gaps,
            'observed_at': snapshot.observed_at, 'audit_at': now.isoformat(),
            'source_uri': SOURCE_URI, 'raw_sha256': snapshot.raw_sha256,
            'standalone_entitlement': False}


@dataclass(frozen=True)
class SyntheticTelemetry:
    tenant: str
    service: str
    started_at: str
    ended_at: str
    observed_at: str
    failed_requests: int
    total_requests: int

    def __post_init__(self):
        if not self.tenant or not self.service:
            raise ValueError('tenant and service required')
        if instant(self.ended_at) <= instant(self.started_at):
            raise ValueError('positive telemetry interval required')
        instant(self.observed_at)
        if (type(self.failed_requests) is not int or type(self.total_requests) is not int
                or not 0 <= self.failed_requests <= self.total_requests or self.total_requests == 0):
            raise ValueError('invalid request counts')

    def for_principal(self, principal: Principal) -> dict:
        if principal.tenant != self.tenant:
            raise PermissionError('tenant mismatch')
        data = asdict(self)
        return {**data, 'sources': [Source.CUSTOMER.value], 'content_hash': fingerprint(data),
                'standalone_entitlement': False}
