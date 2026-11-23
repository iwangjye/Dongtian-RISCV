#!/usr/bin/env python3
"""Fetch the pinned official Debian kernel, or verify a local .deb, on request."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import urllib.request

MAX_PACKAGE_BYTES = 256 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def data_archive(package):
    """Read simple Debian ar members without invoking package scripts or tools."""
    with package.open('rb') as stream:
        if stream.read(8) != b'!<arch>\n':
            raise ValueError('not a Debian ar archive')
        while True:
            header = stream.read(60)
            if not header:
                break
            if len(header) != 60 or header[58:] != b'`\n':
                raise ValueError('invalid ar member header')
            size = int(header[48:58])
            if size < 0 or size > MAX_PACKAGE_BYTES:
                raise ValueError('invalid ar member size')
            name = header[:16].decode('ascii').strip().rstrip('/')
            if name.startswith('data.tar.') or name == 'data.tar':
                if name not in ('data.tar.xz', 'data.tar.gz', 'data.tar.bz2', 'data.tar'):
                    raise ValueError('unsupported data archive: ' + name + '; this script supports xz/gzip/bzip2/uncompressed tar')
                data = stream.read(size)
                if len(data) != size:
                    raise ValueError('truncated ar member')
                return io.BytesIO(data)
            stream.seek(size + size % 2, 1)
    raise ValueError('Debian data archive missing')


def extract_image(package, output, info):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tarfile.open(fileobj=data_archive(package), mode='r:*') as archive:
            found = None
            for member in archive:
                # Match only the exact pinned member (Debian tar commonly adds ./).
                if member.name not in (info['image_archive_member'], './' + info['image_archive_member']):
                    continue
                if found is not None or not member.isfile() or member.size != info['image_bytes']:
                    raise ValueError('invalid or duplicate kernel member')
                found = member
            if found is None:
                raise ValueError('pinned kernel member missing')
            source = archive.extractfile(found)
            if source is None:
                raise ValueError('kernel member cannot be read')
            with source, tempfile.NamedTemporaryFile(dir=output.parent, prefix='.kernel-', delete=False) as target:
                temporary = Path(target.name)
                digest = hashlib.sha256()
                count = 0
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    count += len(chunk)
                    if count > info['image_bytes']:
                        raise ValueError('kernel member exceeds expected length')
                    digest.update(chunk)
                    target.write(chunk)
                if count != info['image_bytes'] or digest.hexdigest() != info['image_sha256']:
                    raise ValueError('kernel image hash or length mismatch')
                target.flush()
                os.fsync(target.fileno())
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deb', type=Path, help='verify and extract an already downloaded package; no network')
    parser.add_argument('--output', type=Path, default=root / 'images/Image')
    args = parser.parse_args()
    info = json.loads((root / 'images/kernel-info.json').read_text())
    try:
        with tempfile.TemporaryDirectory(prefix='dongtian-kernel-') as temporary:
            package = args.deb
            if package is None:
                url = info['package_url']
                if not url.startswith('https://deb.debian.org/debian/'):
                    raise ValueError('expected official Debian HTTPS URL')
                package = Path(temporary) / 'kernel.deb'
                with urllib.request.urlopen(url, timeout=30) as response, package.open('wb') as target:
                    if not response.geturl().startswith('https://deb.debian.org/debian/'):
                        raise ValueError('unexpected download redirect')
                    count = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > MAX_PACKAGE_BYTES:
                            raise ValueError('package exceeds 256 MiB download limit')
                        target.write(chunk)
            if package.stat().st_size > MAX_PACKAGE_BYTES or sha256(package) != info['package_sha256']:
                raise ValueError('Debian package hash mismatch or size exceeds limit')
            extract_image(package, args.output, info)
        print('PASS: verified kernel written to ' + str(args.output))
        return 0
    except (OSError, ValueError, tarfile.TarError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
