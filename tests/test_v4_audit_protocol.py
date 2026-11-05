"""Wire-only V3/V4 bridge. Expected outcomes never come from candidate auth helpers."""
import base64
import hashlib
import inspect
import json
import secrets

ORIGIN = 'http://127.0.0.1:8765'
SUBJECT = 'qa-reviewer'


def is_v4():
    from uptime.server import create_app
    return 'approvals_enabled' in inspect.signature(create_app).parameters


def generate_key():
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1()).private_numbers()
    def coordinate(number):
        return base64.urlsafe_b64encode(number.to_bytes(32, 'big')).decode().rstrip('=')
    return dict(kty='EC', crv='P-256', x=coordinate(key.public_numbers.x),
                y=coordinate(key.public_numbers.y), d=coordinate(key.private_value),
                ext=True, key_ops=['sign'])


def sign(key, message):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    private = ec.derive_private_key(int.from_bytes(base64.urlsafe_b64decode(key['d']+'='), 'big'), ec.SECP256R1())
    r, s = decode_dss_signature(private.sign(message.encode(), ec.ECDSA(hashes.SHA256())))
    return (r.to_bytes(32, 'big')+s.to_bytes(32, 'big')).hex()


class SignedClient:
    def __init__(self, client, subject, key, origin=ORIGIN):
        self.raw, self.subject, self.key = client, subject, key
        self.headers = {'Origin': origin, 'X-Uptime-Action': '1', 'Content-Type': 'application/json'}
        challenge = client.post('/api/auth/challenge', json={'subject': subject}, headers=self.headers)
        if challenge.status_code != 200:
            raise RuntimeError('NamedLoginChallengeRejected')
        c = challenge.json()
        login = client.post('/api/auth/login', json={'challenge': c['challenge'], 'proof': sign(key, c['message'])}, headers=self.headers)
        if login.status_code != 200:
            raise RuntimeError('NamedLoginRejected')
        self.headers['Authorization'] = 'Bearer ' + login.json()['token']
        self.identity = {k: login.json()[k] for k in ('subject', 'role', 'approvals_enabled', 'rehearsal')}

    def get(self, path, **kwargs):
        return self.raw.get(path, headers=self.headers, **kwargs)

    def prepare(self, path, payload):
        body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        challenge = self.raw.post('/api/auth/challenge', headers=self.headers, json={
            'subject': self.subject, 'path': path, 'body_sha256': hashlib.sha256(body).hexdigest()})
        if challenge.status_code != 200:
            return challenge
        c = challenge.json()
        return {'content': body, 'headers': {**self.headers, 'X-Uptime-Challenge': c['challenge'],
                                           'X-Uptime-Proof': sign(self.key, c['message'])}}

    def post(self, path, *, json, headers=None):
        if path == '/api/guide':
            return self.raw.post(path, json=json, headers=self.headers)
        prepared = self.prepare(path, json)
        return self.raw.post(path, **prepared) if isinstance(prepared, dict) else prepared

    def close(self):
        self.raw.close()


def bootstrap(db, mode='replay', rehearsal=True):
    from fastapi.testclient import TestClient
    from uptime import server
    if not is_v4():
        secret = secrets.token_urlsafe(32)
        app = server.create_app(db, session_secret=secret, mode=mode, rehearsal=rehearsal)
        user, viewer = (TestClient(app, raise_server_exceptions=False) for _ in range(2))
        user.get('/session/'+secret)
        viewer.get('/session/'+server.viewer_token(secret))
    else:
        from uptime.auth import enroll
        reviewer_key, viewer_key = generate_key(), generate_key()
        enroll(db, SUBJECT, reviewer_key, mode=mode)
        enroll(db, 'qa-viewer', viewer_key, role='viewer', mode=mode)
        app = server.create_app(db, mode=mode, rehearsal=False, approvals_enabled=True, origin=ORIGIN)
        def client():
            return TestClient(app, base_url=ORIGIN, client=('127.0.0.1', 55123), raise_server_exceptions=False)
        user = SignedClient(client(), SUBJECT, reviewer_key)
        viewer = SignedClient(client(), 'qa-viewer', viewer_key)
    if user.get('/api/policy').status_code != 200:
        raise RuntimeError('PositiveReadControlRejected')
    return user, viewer, app


def scoped_dossier(dossier):
    """Provision explicit synthetic intake facts after mutation, before the attack.

    Does not repair mutated missing components or conflicting line scope. Hashes
    attest the supplied synthetic bytes, not their truth or eligibility.
    """
    from uptime.contracts import fingerprint
    if 'invoice_registry' not in dossier:
        return dossier
    for line in dossier['invoice_lines']:
        for key in ('account', 'month', 'product', 'region', 'currency'):
            line.setdefault(key, dossier[key])
        line.setdefault('invoice_id', dossier['invoice_id'])
        line.setdefault('evidence_ref', line['invoice_id']+'/'+line['id'])
    dossier['invoice_registry'] = {line['id']: fingerprint(line) for line in dossier['invoice_lines']}
    dossier['artifact_registry'] = {doc['ref']: fingerprint(doc)
        for group in ('initial_documents', 'supplemental_archive', 'customer_notice_archive')
        for doc in dossier.get(group, [])}
    return dossier
