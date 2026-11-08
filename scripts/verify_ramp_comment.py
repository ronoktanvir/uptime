#!/usr/bin/env python3
"""Optional, read-only proof that a HUMAN-posted Ramp sandbox bill note is visible.

A person posts the review note in the Ramp UI. This tool only reads it back. It never
creates, edits or deletes comments, never calls provider write or draft procedures, and
does not claim that Uptime created the note. It proves no author identity, permission or
recovered money. The receipt is a local observation made by this machine; Ramp does not
sign it.

Read sequence, all through the existing sandbox transport (fixed demo-api origin, exact
scopes, read-only path allowlist):
  1. Validate the business UUID, the exact observed bill URL and the bounds. No network yet.
  2. Reverify the installation business (business:read) equals the expected business.
  3. Get an exact bills:read token and GET bills/{id}; the returned id must match.
  4. Read complete, bounded comments/bills/{id} pages and keep only exact message matches.
  5. If exactly one matches, read the complete list a second time with the same token and
     object. The same id, body, timestamp and user_id must appear exactly once again.
  6. Reverify the business binding after the reads.

How expected_comment_id is used: without it, two or more exact-body matches give AMBIGUOUS
and no comment is chosen. With it, the candidates are the exact-body matches that have that
exact id. Comment ids must be unique within a complete listing (duplicates are rejected),
so the result is zero candidates (NOT_FOUND) or exactly one. A match is never picked by
position.
"""
import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from uptime.ramp import (ORIGIN, ROOT as _RAMP_ROOT, RampError, RampHTTPError,  # noqa: E402
                         SandboxRampProvider, Token, _timestamp, now, uuid_text)
from uptime.ramp_installation import browser_bill_id, current_business  # noqa: E402
from uptime.ramp_records import _pages  # noqa: E402

SCHEMA = "uptime-human-ramp-note-readback/1"
NOTE = ("Uptime review: governing agreement or usage evidence is missing for this bill. "
        "Unable to verify charges against contract terms. Please attach the signed agreement "
        "or usage records.")
VERIFIED = "VERIFIED_READBACK"
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS = "AMBIGUOUS"
CHANGED = "CHANGED_OR_AMBIGUOUS"
READ_SCOPES = ("business:read", "bills:read")
BILLS_READ = frozenset({"bills:read"})
PAGE_SIZE = 100
MAX_PAGES = 10
MAX_MESSAGE_CHARS = 100_000
MAX_RECEIPT_BYTES = 1_000_000
COMMENT_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")  # Same bound as ramp_records.sanitize_comment.
RECEIPT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}")
RECEIPT_NOTE = ("Local read-only observation recorded by this machine; not signed or attested by "
                "Ramp. Intended to verify a separately posted note; this verifier did not create, edit or post "
                "it. author_user_id is the user_id that Ramp reports on the comment and proves no "
                "identity, permission or authorship. No money recovery is claimed.")
_ERRORS = (RampError, ValueError, TypeError, KeyError, AttributeError, OverflowError)


class CommentVerificationError(RampError):
    """Fixed, display-safe messages only. Never provider bodies, tokens or exception text."""


def _validate_inputs(business_id, bill_url, expected_body, expected_comment_id, max_pages):
    try:
        business_id = uuid_text(business_id)
    except RampError:
        raise CommentVerificationError("Canonical business UUID required") from None
    try:
        bill_id = browser_bill_id(bill_url)
    except RampError:
        raise CommentVerificationError("Exact observed sandbox bill URL required") from None
    if not isinstance(expected_body, str) or not 1 <= len(expected_body) <= MAX_MESSAGE_CHARS:
        raise CommentVerificationError("Bounded expected note body required")
    if expected_comment_id is not None and (not isinstance(expected_comment_id, str)
                                            or not COMMENT_ID.fullmatch(expected_comment_id)):
        raise CommentVerificationError("Bounded comment ID required")
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_PAGES:
        raise CommentVerificationError("Invalid page bound")
    return business_id, bill_id, expected_body, expected_comment_id, max_pages


def _http_message(exc):
    status = exc.status if type(exc.status) is int and 100 <= exc.status <= 599 else None
    return "Ramp read rejected" + (f" (HTTP {status})" if status is not None else "")


def _require_business(provider, expected):
    try:
        observed = current_business(provider)
    except RampHTTPError as exc:
        raise CommentVerificationError(_http_message(exc)) from None
    except _ERRORS:
        raise CommentVerificationError("Ramp business binding could not be verified") from None
    if observed != expected:
        raise CommentVerificationError("Ramp business binding mismatch")


def _bills_token(provider):
    token = provider.token(set(BILLS_READ))
    if (not isinstance(token, Token) or not token.exact or token.expected != BILLS_READ
            or token.granted != BILLS_READ):
        raise CommentVerificationError("Exact bills:read grant required")
    return token


def _require_bill(provider, token, bill_id):
    record = provider.request(token, "GET", "bills/" + bill_id)
    if not isinstance(record, dict) or record.get("id") != bill_id:
        raise CommentVerificationError("Bill does not match the observed URL")


def _read_comments(provider, token, bill_id, max_pages):
    """One complete listing as (id, message, created_at, user_id) tuples, or a fixed error.

    The existing ramp_records._pages owns pagination checks: an exact-origin and
    exact-path next URL, unchanged filters, a bounded cursor, no repeated cursor and the
    page-size bound. A page that is incomplete, failed or truncated by max_pages is rejected.
    """
    rows, coverage = _pages(provider, token, f"comments/bills/{bill_id}", PAGE_SIZE, max_pages)
    for issue in coverage["issues"]:
        if issue.get("code") == "HTTP_ERROR":
            raise CommentVerificationError(_http_message(RampHTTPError(issue.get("http_status"))))
    if coverage["issues"]:
        raise CommentVerificationError("Invalid or unsafe comment pagination")
    if coverage["list_complete"] is not True or coverage["has_next"] is not False:
        raise CommentVerificationError("Comment list incomplete within page bound")
    comments, seen = [], set()
    for raw in rows:
        ident, message, created, user = (raw.get(k) for k in ("id", "message", "created_at", "user_id"))
        if (not isinstance(ident, str) or not COMMENT_ID.fullmatch(ident)
                or not isinstance(message, str) or len(message) > MAX_MESSAGE_CHARS
                or not isinstance(created, str) or len(created) > 64
                or not isinstance(user, str) or len(user) > 64):
            raise CommentVerificationError("Malformed comment record")
        if ident in seen:
            raise CommentVerificationError("Duplicate comment record")
        seen.add(ident)
        comments.append((ident, message, created, user))
    return comments


def _select(comments, body, comment_id):
    matches = [c for c in comments if c[1] == body]
    return matches if comment_id is None else [c for c in matches if c[0] == comment_id]


def _validate_match(match):
    try:
        created_at = _timestamp(match[2])
    except RampError:
        raise CommentVerificationError("Matched comment timestamp invalid") from None
    try:
        author = uuid_text(match[3])
    except RampError:
        raise CommentVerificationError("Matched comment user ID invalid") from None
    return created_at, author


def _receipt(status, business_id, bill_id, read_passes, comment=None):
    ident, body, created_at, author = comment or (None, None, None, None)
    return {"schema": SCHEMA, "status": status, "observed_at": now(), "origin": ORIGIN,
            "business_id": business_id, "bill_id": bill_id, "comment_id": ident, "body": body,
            "created_at": created_at, "author_user_id": author,
            "verified_read_scopes": list(READ_SCOPES), "read_passes": read_passes,
            "write_attempted": False, "api_write_proven": False, "authorship_proven": False,
            "actual_money_recovered": None,
            "evidence": "LOCAL_OBSERVATION_NOT_PROVIDER_SIGNED", "note": RECEIPT_NOTE}


def _verify(provider, business_id, bill_id, body, comment_id, max_pages):
    _require_business(provider, business_id)
    token = _bills_token(provider)
    _require_bill(provider, token, bill_id)
    matches = _select(_read_comments(provider, token, bill_id, max_pages), body, comment_id)
    if len(matches) != 1:
        _require_business(provider, business_id)
        return _receipt(AMBIGUOUS if matches else NOT_FOUND, business_id, bill_id, 1)
    chosen = matches[0]
    created_at, author = _validate_match(chosen)
    again = _select(_read_comments(provider, token, bill_id, max_pages), body, comment_id)
    _require_business(provider, business_id)
    if len(again) != 1 or again[0] != chosen:
        return _receipt(CHANGED, business_id, bill_id, 2)
    return _receipt(VERIFIED, business_id, bill_id, 2, (chosen[0], chosen[1], created_at, author))


def verify_comment(provider, *, business_id, bill_url, expected_body=NOTE,
                   expected_comment_id=None, max_pages=MAX_PAGES):
    """Return a local readback receipt dict, or raise CommentVerificationError.

    Statuses: VERIFIED_READBACK, NOT_FOUND, AMBIGUOUS, CHANGED_OR_AMBIGUOUS. Business,
    bill, scope, pagination and record failures raise fixed messages and return no receipt.
    """
    business_id, bill_id, expected_body, expected_comment_id, max_pages = _validate_inputs(
        business_id, bill_url, expected_body, expected_comment_id, max_pages)
    try:
        return _verify(provider, business_id, bill_id, expected_body, expected_comment_id, max_pages)
    except CommentVerificationError:
        raise
    except RampHTTPError as exc:
        raise CommentVerificationError(_http_message(exc)) from None
    except _ERRORS:
        raise CommentVerificationError("Read-only verification failed") from None


def _repository_identities():
    identities = set()
    for root in {_ROOT, Path(_RAMP_ROOT).resolve()}:
        try:
            info = os.stat(root)
            identities.add((info.st_dev, info.st_ino))
        except OSError:
            pass
    return identities


def _open_custody_directory(directory):
    """Walk from / without following symlinks. The final directory must be owner-only."""
    repository = _repository_identities()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for component in directory.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) in repository:
                raise ValueError
            trusted_sticky = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
            if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and not trusted_sticky):
                raise ValueError
        final = os.fstat(descriptor)
        if (not stat.S_ISDIR(final.st_mode) or final.st_uid != os.getuid()
                or final.st_mode & 0o077):
            raise ValueError
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class ReceiptTarget:
    """Check a new receipt path before any credential or network use.

    The checked directory descriptor stays open, so the receipt is created in the
    directory that was checked, with O_EXCL|O_NOFOLLOW and mode 0600. A file that already
    exists, including one created after the check, is never overwritten.
    """

    def __init__(self, raw):
        self._dir = None
        try:
            if (not isinstance(raw, str) or not raw or "\x00" in raw or raw.endswith("/")
                    or len(raw) > 4096):
                raise ValueError
            path = Path(raw)
            if not path.is_absolute() or ".." in path.parts or not RECEIPT_NAME.fullmatch(path.name):
                raise ValueError
            parent = path.parent
            if os.path.realpath(parent) != str(parent):
                raise ValueError
            for root in {_ROOT, Path(_RAMP_ROOT).resolve()}:
                if parent == root or parent.is_relative_to(root):
                    raise ValueError
            self._dir = _open_custody_directory(parent)
            try:
                os.stat(path.name, dir_fd=self._dir, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError
        except (OSError, ValueError, TypeError):
            self.close()
            raise CommentVerificationError(
                "Receipt must be a new file in an owner-only directory outside the repository") from None
        self.path = path

    def write(self, receipt):
        data = (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        if len(data) > MAX_RECEIPT_BYTES:
            raise CommentVerificationError("Receipt exceeded size bound")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(self.path.name, flags, 0o600, dir_fd=self._dir)
        except OSError:
            raise CommentVerificationError("Receipt path already exists or is unsafe; nothing overwritten") from None
        try:
            os.fchmod(fd, 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise OSError
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        except OSError:
            os.close(fd)
            fd = None
            try:
                os.unlink(self.path.name, dir_fd=self._dir)
            except OSError:
                pass
            raise CommentVerificationError("Receipt could not be written") from None
        finally:
            if fd is not None:
                os.close(fd)

    def close(self):
        if self._dir is not None:
            os.close(self._dir)
            self._dir = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


class _ArgumentError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # Never echo argument values, which could be secrets.
        raise _ArgumentError


def _fail(message):
    print(f"status=ERROR reason={message}", file=sys.stderr)


def main(argv=None):
    parser = _Parser(prog="verify_ramp_comment.py", add_help=True, allow_abbrev=False,
                     description="Read-only readback of a human-posted Ramp sandbox bill note.")
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--bill-url", required=True)
    parser.add_argument("--comment-id")
    parser.add_argument("--receipt", required=True)
    try:
        args = parser.parse_args(argv)
    except _ArgumentError:
        _fail("Invalid arguments")
        return 2
    try:
        _validate_inputs(args.business_id, args.bill_url, NOTE, args.comment_id, MAX_PAGES)
        target = ReceiptTarget(args.receipt)
    except CommentVerificationError as exc:
        _fail(str(exc))
        return 2
    with target:
        try:
            provider = SandboxRampProvider()  # Existing protected credential selection only.
            receipt = verify_comment(provider, business_id=args.business_id, bill_url=args.bill_url,
                                     expected_comment_id=args.comment_id)
            target.write(receipt)
        except CommentVerificationError as exc:
            _fail(str(exc))
            return 1
        except RampError:
            _fail("Ramp sandbox read unavailable")
            return 1
        except Exception:  # noqa: BLE001 - no tracebacks or raw exception text on the console.
            _fail("Read-only verification failed")
            return 1
    print(f"status={receipt['status']}")
    print(f"receipt={target.path}")
    return 0 if receipt["status"] == VERIFIED else 3


if __name__ == "__main__":
    sys.exit(main())
