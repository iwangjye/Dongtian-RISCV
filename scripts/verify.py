#!/usr/bin/env python3
"""Verify every release file listed in PUBLIC_MANIFEST.json, without networking."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    errors = []
    try:
        manifest = json.loads((root / 'PUBLIC_MANIFEST.json').read_text())
        expected = manifest['files']
        if not isinstance(expected, dict) or not expected:
            raise ValueError('files must be a nonempty object')
        for name, record in sorted(expected.items()):
            path = PurePosixPath(name)
            if not path.parts or path.is_absolute() or '..' in path.parts or str(path) != name or name == 'PUBLIC_MANIFEST.json':
                errors.append('invalid manifest path: ' + name)
                continue
            if path.parts[0] in ('.git', 'build', 'runs') or '__pycache__' in path.parts or name == 'images/Image':
                errors.append('generated or excluded manifest path: ' + name)
                continue
            target = root / name
            if any((root.joinpath(*path.parts[:i])).is_symlink() for i in range(1, len(path.parts) + 1)):
                errors.append('symlink: ' + name)
            elif not target.is_file():
                errors.append('missing file: ' + name)
            else:
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest != record['sha256']:
                    errors.append('hash mismatch: ' + name)
                if 'bytes' in record and target.stat().st_size != record['bytes']:
                    errors.append('size mismatch: ' + name)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append('invalid or unreadable PUBLIC_MANIFEST.json: ' + str(error))
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'PASS: verified {len(expected)} listed release files; unlisted worktree files ignored')
    return 0


if __name__ == '__main__':
    sys.exit(main())
