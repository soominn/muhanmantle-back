"""Exit 0 when the API health endpoint answers on the bind address."""

import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    host = os.environ.get("BIND_HOST", "127.0.0.1")
    port = os.environ.get("BIND_PORT", "8000")
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read()
            if resp.status == 200 and b"ok" in body:
                return 0
            print(f"unexpected health response: {resp.status} {body!r}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(exc, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
