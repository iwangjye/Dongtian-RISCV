#!/usr/bin/env python3
"""Run the existing Dongtian preparation/build/runner scripts. Missing inputs may download; nothing is installed."""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory outside the repository')
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--build', type=Path, help='reuse an existing build; runner validates its receipt')
    inputs.add_argument('--deps', type=Path, help='reuse an existing prepared dependency directory')
    parser.add_argument('--downloads', type=Path)
    parser.add_argument('--kernel-deb', type=Path)
    parser.add_argument('--cross-compile')
    parser.add_argument('--dtc')
    parser.add_argument('--qemu', default='qemu-system-riscv64')
    parser.add_argument('--jobs', type=positive_int, default=2)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--interactive', action='store_true')
    mode.add_argument('--private-read', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    if out.exists() or overlaps(out, root):
        parser.error('--output must be new, outside the repository, and must not contain the repository')
    for name in ('build', 'deps', 'downloads', 'kernel_deb'):
        value = getattr(args, name)
        if value is not None:
            value = value.resolve()
            setattr(args, name, value)
            if overlaps(out, value):
                parser.error('--output must not overlap --' + name.replace('_', '-'))
    for name in ('build', 'deps'):
        value = getattr(args, name)
        if value is not None and not value.is_dir():
            parser.error('--' + name + ' must be an existing directory')
    if args.kernel_deb is not None and not args.kernel_deb.is_file():
        parser.error('--kernel-deb must be an existing file')
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'RUNNING', 'mode': 'interactive' if args.interactive else 'private-read' if args.private_read else 'automatic', 'steps': [], 'run_receipt': str(out / 'run/receipt.json')}
    receipt_path = out / 'demo-receipt.json'

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')

    def step(script, options=()):
        command = [sys.executable, str(root / 'scripts' / script), *map(str, options)]
        record = {'command': command, 'exit_code': None}
        receipt['steps'].append(record)
        save()
        print('+ ' + shlex.join(command), flush=True)
        result = subprocess.run(command, cwd=root)
        record['exit_code'] = result.returncode
        save()
        if result.returncode:
            raise RuntimeError(f'{script} exited {result.returncode}')

    try:
        env = ['--qemu', args.qemu]
        if args.build:
            env += ['--runtime-only']
        else:
            for option, value in (('--cross-compile', args.cross_compile), ('--dtc', args.dtc)):
                if value is not None:
                    env += [option, value]
        step('check-env.py', env)
        step('verify.py')
        if not (root / 'images/Image').is_file():
            print('Kernel preparation may download the pinned package unless --kernel-deb is supplied.', flush=True)
            step('fetch-kernel.py', ['--deb', args.kernel_deb] if args.kernel_deb else [])
        build = args.build or out / 'build'
        if not args.build:
            deps = args.deps or out / 'deps'
            if not args.deps:
                print('Dependency preparation may download pinned archives missing from the cache.', flush=True)
                options = ['--output', deps]
                if args.downloads:
                    options += ['--downloads', args.downloads]
                step('prepare-runtime.py', options)
            options = ['--deps', deps, '--output', build, '--jobs', args.jobs]
            for option, value in (('--cross-compile', args.cross_compile), ('--dtc', args.dtc)):
                if value is not None:
                    options += [option, value]
            step('build-runtime.py', options)
        options = ['--build', build, '--output', out / 'run', '--qemu', args.qemu]
        if args.interactive:
            options += ['--interactive']
        elif args.private_read:
            options += ['--private-read']
        step('run-runtime.py', options)
        receipt['status'] = 'INTERACTIVE_COMPLETED' if args.interactive else 'PASS'
        print('Interactive runner completed; no automatic PASS is claimed.' if args.interactive else 'PASS: existing runtime workflow completed', flush=True)
        return 0
    except (OSError, RuntimeError, KeyboardInterrupt) as error:
        receipt['status'] = 'FAIL'
        receipt['error'] = str(error) or 'interrupted'
        print('FAIL: ' + receipt['error'], file=sys.stderr)
        return 1
    finally:
        save()
        print('Demo receipt: ' + str(receipt_path), flush=True)


if __name__ == '__main__':
    sys.exit(main())
