#!/usr/bin/env python3
"""Prepare pinned OpenSBI and matching Linux module headers (Linux x86_64)."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, help='cache of the pinned archives; missing files are explicitly downloaded')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error('expanded runtime preparation requires Python 3.12+ for filtered tar extraction')
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if out.exists() or out == root or root in out.parents:
        parser.error('output must be new and outside the repository')
    out.mkdir(parents=True)
    cache = args.downloads.resolve() if args.downloads else out / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / 'dependencies/manifest.json').read_text())
    spec = importlib.util.spec_from_file_location('kernel_fetch', root / 'scripts/fetch-kernel.py')
    fetch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch)
    for item in manifest['packages']:
        path = cache / item['file']
        if not path.exists():
            temporary = path.with_suffix(path.suffix + '.part')
            try:
                with urllib.request.urlopen(item['url'], timeout=30) as response, temporary.open('wb') as target:
                    shutil.copyfileobj(response, target, 1024 * 1024)
                if temporary.stat().st_size != item['bytes'] or digest(temporary) != item['sha256']:
                    raise ValueError('download identity mismatch: ' + item['file'])
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('cached archive identity mismatch: ' + item['file'])
        if item['file'].endswith('.deb'):
            destination = out / 'headers'
            destination.mkdir(exist_ok=True)
            with tarfile.open(fileobj=fetch.data_archive(path), mode='r:*') as archive:
                archive.extractall(destination, filter='data')
        else:
            destination = out / 'opensbi'
            destination.mkdir()
            with tarfile.open(path) as archive:
                members = archive.getmembers()
                for member in members:
                    parts = Path(member.name).parts
                    member.name = str(Path(*parts[1:])) if len(parts) > 1 else '.'
                    archive.extract(member, destination, filter='data')
    source = out / 'opensbi'
    shutil.copyfile(root / 'opensbi/sbi_ecall_dongtian.c', source / 'lib/sbi/sbi_ecall_dongtian.c')
    objects = source / 'lib/sbi/objects.mk'
    objects.write_text(objects.read_text() + '\n# Dongtian controlled handoff extension\ncarray-sbi_ecall_exts-y += ecall_dongtian\nlibsbi-objs-y += sbi_ecall_dongtian.o\n')
    common = out / 'headers/usr/src/linux-headers-6.12.117+deb13-common'
    headers = out / 'headers/usr/src/linux-headers-6.12.117+deb13-riscv64'
    (headers / 'Makefile').write_text('include ' + str(common / 'Makefile') + '\n')
    prepared = {'opensbi_source': str(source), 'kernel_headers': str(headers), 'opensbi_commit': manifest['opensbi_commit'], 'input_manifest_sha256': digest(root / 'dependencies/manifest.json')}
    (out / 'prepared.json').write_text(json.dumps(prepared, indent=2) + '\n')
    print('PASS: prepared OpenSBI and Linux module headers in ' + str(out))


if __name__ == '__main__':
    main()
