"""Native loopback client for named reviewer proofs and synthetic inbound service fixtures."""
import json
import secrets
from time import time

from .auth_keys import rehearsal_key, reviewer_signature
from .auth import SCRIPT, digest, service_message, signature, valid_origin


def action_headers(origin):
    return {"Origin": valid_origin(origin), "X-Uptime-Action": "1", "Content-Type": "application/json"}


class ReviewerClient:
    """An authenticated native client; a valid read session alone cannot sign a write."""
    def __init__(self, client, origin, subject, credential):
        self.client, self.origin, self.subject = client, valid_origin(origin), subject
        self.headers = action_headers(origin)
        challenge = self.challenge("/api/auth/login", "")
        self.key = rehearsal_key(credential) if subject == SCRIPT and isinstance(credential, str) else credential
        response = self.client.post("/api/auth/login", headers=self.headers, json={
            "challenge": challenge["challenge"], "proof": reviewer_signature(self.key, challenge["message"])})
        response.raise_for_status()
        self.headers["Authorization"] = "Bearer " + response.json()["token"]

    def challenge(self, path, body_hash):
        response = self.client.post("/api/auth/challenge", headers=self.headers, json={
            "subject": self.subject, "path": path, "body_sha256": body_hash})
        response.raise_for_status()
        return response.json()

    def prepare(self, path, payload):
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        challenge = self.challenge(path, digest(raw))
        return {"content": raw, "headers": {**self.headers, "X-Uptime-Challenge": challenge["challenge"],
                                            "X-Uptime-Proof": reviewer_signature(self.key, challenge["message"])}}

    def post(self, path, payload):
        return self.client.post(path, **self.prepare(path, payload))


def service_headers(*, instance, origin, subject, key, path, body):
    stamp, nonce = str(int(time())), secrets.token_urlsafe(32)
    message = service_message(instance, origin, subject, path, body, stamp, nonce)
    return {**action_headers(origin), "X-Uptime-Service": subject, "X-Uptime-Time": stamp,
            "X-Uptime-Nonce": nonce, "X-Uptime-Proof": signature(key.encode(), message)}
