#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec /usr/bin/python3 - <<'PY'
import getpass
import os
from pathlib import Path
value=getpass.getpass('OpenObservatory API token (hidden; blank to remove): ').strip()
p=Path('token.txt')
if value:
    if '\r' in value or '\n' in value: raise SystemExit('Use a single-line token.')
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f: f.write(value+'\n')
    p.chmod(0o600)
    print('Saved token.txt with owner-only permissions. Restart the service to use it.')
else:
    p.unlink(missing_ok=True)
    print('Removed token file.')
PY
