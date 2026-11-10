#!/usr/bin/env python3
"""Build only the candidate after verifying its immutable local base identity."""
import json
import hashlib
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
base = 'camofox-bitwarden:2026.10.2-4ad5a5b931ed'
expected = 'sha256:202ef6061a786c5afdc7413a70716d5a4266389169b23a1e328d62293d21f029'
actual = json.loads(subprocess.check_output(['docker', 'image', 'inspect', base]))[0]['Id']
if actual != expected:
    raise SystemExit('Base image identity mismatch; no build was started')
manifest = {}
for directory, subdirs, names in os.walk(root):
    subdirs[:] = [name for name in subdirs if name not in {'.git', 'node_modules', '__pycache__', 'work', 'secrets'}]
    for name in names:
        file = Path(directory) / name
        if name == '.env' or file.suffix in {'.pyc', '.tgz', '.tar'}: continue
        manifest[file.relative_to(root).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
print('Candidate source digest:', digest, flush=True)
subprocess.run(['docker', 'build', '--force-rm', '--pull=false', '--network=none', '-f', str(root/'release/Dockerfile'),
                '--build-arg', 'BASE_IMAGE='+expected, '--build-arg', 'CANDIDATE_SOURCE_SHA256='+digest, '-t', 'camofox-bitwarden:2026.11.09-native-r4f', str(root)], check=True, env={**os.environ, 'DOCKER_BUILDKIT': '0'})
