"""Explicit opt-in public refresh; no redirects, credentials, or environment proxy."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import http.client
import json
from pathlib import Path
import time

from uptime.evidence import MAX_BYTES, SOURCE_URI, minimize


def fetch_public(*, uri: str = SOURCE_URI, timeout: float = 10.0) -> bytes:
    if uri != SOURCE_URI:
        raise ValueError('only the fixed official HTTPS endpoint is allowed')
    if not 0 < timeout <= 30:
        raise ValueError('timeout must be within 30 seconds')
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPSConnection('status.twilio.com', timeout=timeout)
    try:
        connection.request('GET', '/api/v2/incidents.json', headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        transport_socket = connection.sock
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('public endpoint unavailable; redirects forbidden')
        if response.getheader('Content-Encoding', 'identity') != 'identity':
            raise ValueError('encoded response forbidden')
        length = response.getheader('Content-Length')
        if length is not None and (int(length) < 0 or int(length) > MAX_BYTES):
            raise ValueError('feed too large')
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('public refresh deadline exceeded')
            # read1 performs at most one underlying read; reset its deadline each iteration.
            if transport_socket is not None:
                transport_socket.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if time.monotonic() > deadline:
                raise TimeoutError('public refresh deadline exceeded')
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('feed too large')
        return b''.join(chunks)
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='explicitly permit a public HTTPS GET')
    parser.add_argument('--output', type=Path, required=True, help='minimized snapshot destination')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; replay never refreshes implicitly')
    try:
        raw = fetch_public()
        snapshot = minimize(raw, {'url': SOURCE_URI, 'collected_at': datetime.now(timezone.utc).isoformat(),
                                  'sha256': sha256(raw).hexdigest()})
        temporary = args.output.with_suffix(args.output.suffix + '.tmp')
        temporary.write_text(json.dumps(snapshot.payload(), indent=2) + '\n')
        temporary.replace(args.output)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        print(json.dumps({'state': 'unavailable', 'sources': ['UNAVAILABLE'], 'detail': 'Refresh failed; existing snapshot preserved.'}))
        return 1
    print(json.dumps({'state': 'available', 'sources': ['LIVE_VENDOR_PUBLIC'], 'observed_at': snapshot.observed_at}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
