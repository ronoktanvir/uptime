"""Process-selected sandbox credentials; never a request or provider-selected path."""
import base64
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

ORIGIN = 'https://demo-api.ramp.com'
ROOT = Path(__file__).resolve().parents[1]
SELECTOR = 'UPTIME_RAMP_CREDENTIAL_FILE'
MAX_BYTES = 16384


class CredentialError(ValueError):
    pass


@dataclass(frozen=True)
class Credentials:
    basic: str = field(repr=False)
    client_fingerprint: str


def selected_path():
    """Capture this selection at construction, before serving any requests."""
    value = os.environ.get(SELECTOR, str(Path.home()/'.config/uptime/ramp-sandbox.json'))
    path = Path(value)
    if not value or not path.is_absolute() or '..' in path.parts or path.is_relative_to(ROOT):
        raise CredentialError('Protected sandbox credential profile required')
    return path


def _read(path):
    # Directory descriptors prevent path replacement between checking and opening.
    # Root-owned sticky ancestors (macOS /private/tmp in isolated tests) are safe
    # to traverse; the final custody directory must still be owner-only.
    if (not path.is_absolute() or '..' in path.parts or path.resolve() != path
            or path.is_relative_to(ROOT)):
        raise ValueError
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.parts[1:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            trusted_sticky = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
            if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and not trusted_sticky):
                raise ValueError
        parent = os.fstat(descriptor)
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise ValueError
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > MAX_BYTES):
                raise ValueError
            data = handle.read(MAX_BYTES+1)
            if len(data) > MAX_BYTES:
                raise ValueError
            return data
    finally:
        os.close(descriptor)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _constant(_value):
    raise ValueError


def load(path=None):
    """Return memory-only auth material; all failures omit input and exception chains."""
    try:
        if os.environ.get('RAMP_ENV') != 'sandbox' or os.environ.get('RAMP_BASE_URL', ORIGIN) != ORIGIN:
            raise ValueError
        value = json.loads(_read(selected_path() if path is None else Path(path)),
                           object_pairs_hook=_pairs, parse_constant=_constant)
        if (not isinstance(value, dict) or set(value) != {'base_url','client_id','client_secret'}
                or value['base_url'] != ORIGIN):
            raise ValueError
        for name in ('client_id','client_secret'):
            text = value[name]
            if not isinstance(text, str) or not 1 <= len(text) <= 4096 or any(not 33 <= ord(c) <= 126 for c in text):
                raise ValueError
        if ':' in value['client_id']:
            raise ValueError
        basic = base64.b64encode((value['client_id']+':'+value['client_secret']).encode()).decode()
        return Credentials(basic, sha256(value['client_id'].encode()).hexdigest())
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise CredentialError('Protected sandbox credentials unavailable') from None
