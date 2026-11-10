#!/usr/bin/env python3
"""Run as root in a one-shot container with /release-secrets bound to a NEW directory.

Creates only a new candidate control key. Never imports a production key.
"""
import os
import secrets
from pathlib import Path

directory = Path('/release-secrets')
if not directory.is_dir() or directory.is_symlink():
    raise SystemExit('Bind a new release-secrets directory first')
client_uid = int(os.environ['CLIENT_UID'])
if client_uid < 1:
    raise SystemExit('CLIENT_UID must be the unprivileged host owner UID')
targets = [(directory / 'control-key', 911), (directory / 'client-key', client_uid)]
if any(target.exists() or target.is_symlink() for target, _ in targets):
    raise SystemExit('Use a new directory without existing key files')
value = secrets.token_urlsafe(48) + '\n'
created = []
try:
    for target, owner in targets:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        created.append(target)
        with os.fdopen(fd, 'w') as output:
            output.write(value)
        os.chown(target, owner, owner)
except Exception:
    for target in created: target.unlink(missing_ok=True)
    raise
print('Created new candidate server/client key files; values were not printed.')
