#!/usr/bin/env python3
"""Build the self-contained RV64 integer-only Linux demotion/CVM firmware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


def find_tool(explicit, names):
    if explicit:
        found = shutil.which(explicit)
        if found:
            return str(Path(found).absolute())
        raise RuntimeError('tool not found: ' + explicit)
    for name in names:
        found = shutil.which(name)
        if found:
            return str(Path(found).absolute())
    raise RuntimeError('tool not found; tried: ' + ', '.join(names))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory outside package')
    parser.add_argument('--cc', help='RISC-V capable Clang or riscv64 GCC executable')
    parser.add_argument('--ld', help='ld.lld executable for Clang builds')
    parser.add_argument('--dtc', default='dtc', help='device tree compiler executable')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if out.exists() or out == root or root in out.parents:
        parser.error('output must be a new directory outside the package')
    try:
        cc = find_tool(args.cc, ['riscv64-unknown-elf-gcc', 'riscv64-linux-gnu-gcc', '/opt/homebrew/opt/llvm@22/bin/clang', 'clang'])
        clang = 'clang' in Path(cc).name
        ld = find_tool(args.ld, ['ld.lld', '/opt/homebrew/opt/lld@22/bin/ld.lld']) if clang else None
        dtc = find_tool(args.dtc, ['dtc'])
    except RuntimeError as error:
        parser.error(str(error))
    out.mkdir(parents=True)
    receipt = {'scope': 'minimal Linux HS-to-VS/CVM firmware', 'steps': [], 'source_hashes': {}, 'status': 'FAIL', 'hardware_executed': False}
    paths = sorted((root / 'src').rglob('*')) + sorted((root / 'include').glob('*')) + sorted((root / 'tests').glob('*'))
    receipt['source_hashes'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    def command(name, cmd):
        result = subprocess.run(cmd, cwd=out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (out / (name + '.log')).write_text(result.stdout)
        receipt['steps'].append({'name': name, 'command': cmd, 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError(name + ' failed; see ' + str(out / (name + '.log')))
        return result.stdout
    try:
        receipt['compiler'] = command('compiler-version', [cc, '--version']).strip()
        flags = ['-march=rv64imah_zicsr_zifencei', '-mabi=lp64', '-mcmodel=medany', '-msmall-data-limit=0', '-mno-relax', '-fno-pic', '-fno-pie', '-fno-stack-protector', '-ffreestanding', '-fno-builtin', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-I' + str(root / 'include')]
        if clang:
            flags.insert(0, '--target=riscv64-unknown-elf')
        objects = []
        for filename in ('boot.S', 'firmware.c', 'trap.S', 'monitor.c', 'lib.c'):
            target = out / (filename + '.o')
            command('compile-' + filename.replace('.', '-'), [cc, *flags, '-c', str(root / 'src' / filename), '-o', str(target)])
            objects.append(str(target))
        elf = out / 'firmware.elf'
        if clang:
            command('link', [ld, '-m', 'elf64lriscv', '--no-relax', '--build-id=none', '-T', str(root / 'src/linker.ld'), '-o', str(elf), *objects])
        else:
            command('link', [cc, *flags, '-nostdlib', '-static', '-Wl,--no-relax,--build-id=none', '-T', str(root / 'src/linker.ld'), '-o', str(elf), *objects])
        receipt['elf_sha256'] = hashlib.sha256(elf.read_bytes()).hexdigest()
        # Build actual Linux /init programs without libc, and deterministic newc archives.
        def initramfs(binary, target):
            data = bytearray()
            ino = 0
            def add(name, payload, mode, major=0, minor=0):
                nonlocal ino
                ino += 1
                nb = name.encode() + b'\0'
                fields = [ino, mode, 0, 0, 1, 0, len(payload), 0, 0, major, minor, len(nb), 0]
                data.extend(b'070701' + b''.join(f'{x:08x}'.encode() for x in fields) + nb)
                data.extend(bytes((-len(data)) % 4))
                data.extend(payload)
                data.extend(bytes((-len(data)) % 4))
            add('dev', b'', stat.S_IFDIR | 0o755)
            add('proc', b'', stat.S_IFDIR | 0o755)
            add('dev/console', b'', stat.S_IFCHR | 0o600, 5, 1)
            add('dev/mem', b'', stat.S_IFCHR | 0o600, 1, 1)
            add('init', binary.read_bytes(), stat.S_IFREG | 0o755)
            add('TRAILER!!!', b'', 0)
            target.write_bytes(data)
        for role in ('host', 'guest', 'host-private-read'):
            source = root / ('tests/init-private-read.c' if role == 'host-private-read' else 'src/init.c')
            target = out / (role + '-init')
            initflags = ['-march=rv64imac_zicsr_zifencei', '-mabi=lp64', '-O2', '-ffreestanding', '-fno-builtin', '-msmall-data-limit=0', '-mno-relax', '-fno-pic', '-fno-pie', '-nostdlib', '-static', '-Wl,-e,_start,--build-id=none,--no-relax', '-DROLE="' + role + '"']
            if clang:
                initflags = ['--target=riscv64-linux-gnu', '-fuse-ld=' + ld] + initflags
            if role.startswith('host'):
                initflags += ['-DHOST']
            command('compile-init-' + role, [cc, *initflags, str(source), '-o', str(target)])
            initramfs(target, out / (role + '.cpio'))
        for role in ('host', 'guest', 'host-private-read'):
            template = root / 'src/dts' / ('guest.dts' if role == 'guest' else 'host.dts')
            text = template.read_text()
            end = 0x85000000 + (out / (role + '.cpio')).stat().st_size
            text, count = re.subn(r'linux,initrd-end\s*=\s*<[^>]*>;', f'linux,initrd-end = <0x0 0x{end:x}>;', text)
            if count != 1:
                raise RuntimeError('expected one initrd-end in ' + str(template))
            dts = out / (role + '.dts')
            dts.write_text(text)
            command('dtc-' + role, [dtc, '-I', 'dts', '-O', 'dtb', '-o', str(out / (role + '.dtb')), str(dts)])
        receipt['artifacts'] = {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in ('firmware.elf', 'host.cpio', 'guest.cpio', 'host-private-read.cpio', 'host.dtb', 'guest.dtb', 'host-private-read.dtb')}
        receipt['kernel_sha256'] = hashlib.sha256((root / 'images/Image').read_bytes()).hexdigest()
        receipt['status'] = 'PASS'
        print('PASS: built ' + str(elf))
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        receipt['error'] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
