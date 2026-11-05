"""Verify that an observed native bill URL belongs to the selected sandbox API installation."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.ramp import RampError, RampHTTPError, SandboxRampProvider
from uptime.ramp_installation import verify_browser_bill


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bill-url', required=True, help='Exact URL observed in the signed-in Ramp sandbox UI')
    parser.add_argument('--output', type=Path, required=True, help='New sanitized association receipt; never overwritten')
    args = parser.parse_args()
    try:
        # Validate output before sending even read-only requests. Keep native IDs private by default.
        output = args.output
        if not output.is_absolute() or output.resolve() != output or output.exists() or output.is_symlink():
            raise ValueError
        if output.parent.stat().st_uid != os.getuid() or output.parent.stat().st_mode & 0o077:
            raise ValueError
        provider = SandboxRampProvider()
        result = verify_browser_bill(provider, args.bill_url)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor,'w') as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        print(json.dumps({'status':result['status'], 'bill_id':result['bill_id'],
                          'business_id':result['business_id'], 'receipt':str(output), 'write_attempted':False}))
        return 0
    except RampHTTPError as exc:
        print(f'Ramp association refused (HTTP {exc.status}); no write attempted.', file=sys.stderr)
    except (RampError, OSError, ValueError, TypeError, KeyError):
        print('Ramp association unavailable. Check protected profile, read grants and exact observed bill identity; no write attempted.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
