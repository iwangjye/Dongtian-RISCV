#!/usr/bin/env python3
"""Check local runtime or build prerequisites; never install or boot a guest."""
import argparse
import importlib.util
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-only', action='store_true', help='check Python and QEMU only (prebuilt runtime)')
    parser.add_argument('--cross-compile', help='GNU RISC-V compiler/binutils prefix')
    parser.add_argument('--dtc', default='dtc')
    parser.add_argument('--qemu', default='qemu-system-riscv64')
    args = parser.parse_args()
    if args.runtime_only and (args.cross_compile is not None or args.dtc != 'dtc'):
        parser.error('--runtime-only does not check --cross-compile or --dtc')
    errors = []
    print('Scope: ' + ('Python and QEMU only' if args.runtime_only else 'Linux x86_64 build dependencies and RISC-V PIE link probe') + '; not a full-system acceptance test.', flush=True)
    print('Python: ' + platform.python_version())
    if sys.version_info < ((3, 9) if args.runtime_only else (3, 12)):
        errors.append('Python 3.9+ is required for runtime-only checks' if args.runtime_only else 'Python 3.12+ is required for a full build')

    def tool(name):
        path = shutil.which(name)
        if not path:
            errors.append('tool not found: ' + name)
            return None
        try:
            result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode:
                errors.append(f'{name} --version exited {result.returncode}: {result.stderr.strip()}')
            else:
                print(name + ': ' + (result.stdout.strip() or result.stderr.strip()).split('\n')[0])
        except (OSError, subprocess.TimeoutExpired) as error:
            errors.append(name + ': ' + str(error))
        return path

    tool(args.qemu)
    if not args.runtime_only:
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            errors.append('full build requires Linux x86_64; found ' + platform.system() + ' ' + platform.machine())
        for name in ('gcc', 'make', args.dtc):
            tool(name)
        spec = importlib.util.spec_from_file_location('runtime_build', Path(__file__).with_name('build-runtime.py'))
        build = importlib.util.module_from_spec(spec)
        sys.dont_write_bytecode = True
        spec.loader.exec_module(build)
        try:
            prefix, cc, _ = build.resolve_cross_compile(args.cross_compile)
            for suffix in ('gcc', 'ld', 'ar', 'ranlib', 'objcopy', 'nm', 'objdump', 'readelf', 'as'):
                tool(prefix + suffix)
            with tempfile.TemporaryDirectory(prefix='dongtian-pie-') as directory:
                target = Path(directory) / 'probe.elf'
                command = [cc, '-fPIE', '-nostdlib', '-Wl,-pie', '-x', 'c', '-', '-o', str(target)]
                result = subprocess.run(command, input='void _start(void) {}\n', text=True, capture_output=True, timeout=10)
                if result.returncode:
                    errors.append(f'RISC-V PIE link probe exited {result.returncode}: {result.stderr.strip()}')
                else:
                    header = target.read_bytes()[:20]
                    endian = '<' if len(header) >= 20 and header[5] == 1 else '>'
                    if len(header) < 20 or header[:4] != b'\x7fELF' or header[4] != 2 or header[5] not in (1, 2) or struct.unpack(endian + 'HH', header[16:20]) != (3, 243):
                        errors.append('PIE probe must produce RV64 ELF64 ET_DYN (type 3, machine 243)')
                    else:
                        print('PASS: real RISC-V PIE link probe (ET_DYN, EM_RISCV)')
        except (build.ConfigError, OSError, subprocess.TimeoutExpired) as error:
            errors.append(str(error))
    if errors:
        for error in errors:
            print('FAIL: ' + error, file=sys.stderr)
        return 1
    print('PASS: selected prerequisite checks completed; no guest was run')
    return 0


if __name__ == '__main__':
    sys.exit(main())
