"""Offline synthetic correspondence sources, their public grants and private delivery files."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Annotated, Literal
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .correspondence_types import Delivery, Id, Scope, SOURCE

ROOT = Path(__file__).resolve().parents[1]
Subject = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,63}$")]
Key = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Source = Literal["billing", "customer", "status", "vendor"]
Mode = Literal["sandbox", "replay"]
CLAIM = re.compile(r"^inbox-[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def _validated_verifier(key):
    # libsodium ref10 ge25519_has_small_order enumerates the canonical small-order y coordinates.
    # The high bit encodes the sign of x. Some Ed25519 backends accept forged signatures for these points.
    field_prime = 2**255 - 19
    y = int.from_bytes(bytes.fromhex(key), "little") & (2**255 - 1)
    order_eight_y = 2707385501144840649318225287225658788936804267575313519463743609750303402022
    if y >= field_prime or y in {0, 1, field_prime-1, order_eight_y, field_prime-order_eight_y}:
        raise ValueError("Use a canonical Ed25519 public verifier of nontrivial order")
    return key


EdVerifier = Annotated[Key, AfterValidator(_validated_verifier)]


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class SourceGrant(Strict):
    subject: Subject
    source: Source
    scope: Scope
    public_key: EdVerifier

    def verify(self, message, proof):
        if not re.fullmatch(r"[0-9a-f]{128}", proof):
            return False
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key)).verify(bytes.fromhex(proof), message.encode())
            return True
        except (InvalidSignature, ValueError):
            return False

    def allows(self, path, body):
        prefix, suffix = "/api/correspondence/claims/", "/events"
        if not path.startswith(prefix) or not path.endswith(suffix) or not CLAIM.fullmatch(path[len(prefix):-len(suffix)]):
            return False
        try:
            event = Delivery.model_validate_json(body)
        except ValidationError:
            return False
        return event_in_scope(event, self.source, self.scope)


def event_in_scope(event, source, scope):
    if event.scope != scope or SOURCE[event.body.kind] != source:
        return False
    if event.body.kind == "component":
        return event.body.component_id == scope.component
    # Independently scoped records must corroborate the envelope, including resource-scoped report rows.
    fields = {**scope.model_dump(), "resource_id":scope.component, "agreement":scope.contract}
    for collection in ("lines", "records", "intervals", "causes", "exclusions"):
        for row in getattr(event.body, collection, []):
            for field, value in row.model_dump(exclude_none=True).items():
                if field in fields and value != fields[field]:
                    return False
    return True


class Audience(Strict):
    channel: Literal["LOCAL_SYNTHETIC"]
    tenant: Id
    mode: Mode
    origin: str

    @field_validator("origin")
    @classmethod
    def exact_listener(cls, value):
        port = urlsplit(value).port
        if not port or value != f"http://127.0.0.1:{port}":
            raise ValueError("Select the exact numeric IPv4 loopback listener")
        return value


class SourceConfig(Audience):
    version: Literal[1]
    services: list[SourceGrant] = Field(max_length=128)

    @model_validator(mode="after")
    def unique_services(self):
        if (len({s.subject for s in self.services}) != len(self.services) or
                len({s.public_key for s in self.services}) != len(self.services)):
            raise ValueError("Each source needs a distinct subject and key")
        return self

    def credentials(self, mode, origin, tenant="bears"):
        if self.mode != mode or self.origin != origin or self.tenant != tenant:
            raise ValueError("Source configuration belongs to a different mode or loopback listener")
        return SourceGrants(self, mode, origin, tenant)

    def bind(self, desk):
        for service in self.services:
            s = service.scope
            desk.provision(self.tenant, s.account, s.vendor, s.contract, s.service, s.component, s.region)
            desk.bind_sender(self.tenant, s.account, service.source, service.subject, scope=s)


class SourceGrants(dict):
    """Carry the verified audience alongside programmatically injected fixture grants."""
    def __init__(self, config, mode, origin, tenant):
        super().__init__((s.subject, s) for s in config.services)
        self.audience = (mode, origin, tenant)


class SourceRegistry:
    """Recheck the protected verifier file at delivery. New scope bindings require a launch."""
    def __init__(self, path, mode, origin, tenant):
        self.path = path
        self.audience = (mode, origin, tenant)
        self.config = load_private(path, SourceConfig)
        self.initial = self.config.credentials(*self.audience)

    def lookup(self, subject):
        original = self.initial.get(subject)
        if original is None:
            return None
        current = load_private(self.path, SourceConfig).credentials(*self.audience).get(subject)
        if current and (current.scope, current.source) == (original.scope, original.source):
            return current
        return None


class SenderCredential(Audience):
    version: Literal[1]
    subject: Subject
    source: Source
    scope: Scope
    private_key: Key = Field(repr=False)

    def sign(self, message):
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.private_key))
        return key.sign(message.encode()).hex()


def create_source(config, subject, source, scope):
    key = Ed25519PrivateKey.generate()
    grant = SourceGrant(subject=subject, source=source, scope=scope, public_key=key.public_key().public_bytes_raw().hex())
    audience = config.model_dump(exclude={"services"})
    sender = SenderCredential(**audience, subject=subject, source=source, scope=scope, private_key=key.private_bytes_raw().hex())
    return grant, sender


def _protected_path(path):
    path = Path(path)
    if not path.is_absolute() or path != path.resolve():
        raise ValueError("Use an absolute path without symlinks or traversal")
    if path.is_relative_to(ROOT) or any((parent / ".git").exists() for parent in path.parents):
        raise ValueError("Keep source configurations and credentials outside repositories")
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o022:
        raise ValueError("Use an operator-owned directory that others cannot write")
    return path


def _check_file(fd):
    meta = os.fstat(fd)
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid() or
            stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1):
        raise ValueError("Expected a private, operator-owned, single-link 0600 regular file")


def load_private(path, model):
    path = _protected_path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        _check_file(handle.fileno())
        data = handle.read(262145)
        if len(data) > 262144:
            raise ValueError("Source configuration exceeds the size limit")
    try:
        return model.model_validate_json(data)
    except ValidationError:
        raise ValueError("Invalid source configuration or credential file") from None


def _write_new(path, model):
    path = _protected_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(model.model_dump_json(indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def init_config(path, mode, origin, tenant="bears"):
    config = SourceConfig(version=1, channel="LOCAL_SYNTHETIC", tenant=tenant, mode=mode, origin=origin, services=[])
    _write_new(path, config)


@contextmanager
def _config_edit(path):
    path = _protected_path(path)
    lock = _protected_path(path.with_name(path.name+".lock"))
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "rb+") as handle:
        _check_file(handle.fileno())
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield load_private(path, SourceConfig)


def update_source(path, command, subject, *, source=None, scope=None, sender_path=None):
    """Serialize offline changes; replacing a key or grant takes effect on relaunch."""
    path = _protected_path(path)
    with _config_edit(path) as config:
        existing = next((item for item in config.services if item.subject == subject), None)
        keep = [item for item in config.services if item.subject != subject]
        if command == "add" and existing:
            raise ValueError("Source subject already exists")
        if command in ("rotate","revoke") and not existing:
            raise ValueError("Source subject has no current grant")
        if command == "rotate":
            source, scope = existing.source, existing.scope
        if command in ("add","rotate"):
            grant, sender = create_source(config, subject, source, scope)
            keep.append(grant)
        elif command != "revoke":
            raise ValueError("Unknown source operation")
        updated = SourceConfig.model_validate({**config.model_dump(), "services":keep})
        created = None
        pending = path.with_name(path.name+".pending-"+secrets.token_hex(8))
        try:
            if command != "revoke":
                created = _write_new(sender_path, sender)
            _write_new(pending, updated)
            os.replace(pending, path)
        except BaseException:
            if created is not None:
                created.unlink(missing_ok=True)
            raise
        finally:
            pending.unlink(missing_ok=True)
