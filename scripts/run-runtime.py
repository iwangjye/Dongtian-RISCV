#!/usr/bin/env python3
"""Run the single-CVM Dongtian runtime in QEMU.

The build receipt is the trust boundary: only a PASS build with intact
artifacts and the pinned kernel is accepted.  Ordinary and negative runs are
fully automatic; --interactive hands the serial console to the user and never
performs automatic PASS acceptance.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CPU = ('rv64,h=true,sstc=false,f=false,d=false,v=false,zfh=false,'
       'zfhmin=false,zfa=false,zfbfmin=false,svpbmt=false,zicboz=false,'
       'zicbom=false')

COMMON_MARKERS = (
    'OpenSBI v1.7',
    'LINUX_USERSPACE_ROLE=host',
    'getpid=1',
    'DONGTIAN_KERNEL_DRIVER_LOADED',
    'HOST_REQUEST_DYNAMIC_HS_TO_VS',
    '[Dongtian/OpenSBI] handing native HS Linux to HS monitor',
    'HOST_AFTER_DEMOTION',
    'HOST_AFTER_DEMOTION_TIME_OK',
    'HOST_REQUEST_CVM_LINUX',
    '[HS] entering independent Linux CVM',
    'LINUX_USERSPACE_ROLE=guest',
    'getpid=1',
    'CVM_LINUX_USERSPACE_OK',
    '[HS] CVM requested shutdown; resuming demoted Linux host',
    'HOST_AFTER_CVM_RETURN',
)

POSITIVE_MARKERS = (
    'DONGTIAN_DRIVER_WORKFLOW_PASS',
    'MINIMAL_LINUX_CVM_PASS',
)

NEGATIVE_MARKER = 'HOST_PRIVATE_READ_ATTEMPT'

FORBIDDEN = (
    'Kernel panic',
    'Oops',
    'HOST_INIT_FAIL',
    'HOST_AFTER_DEMOTION_TIME_FAIL',
    'PRIVATE_READ_UNEXPECTED_RETURN',
)

PRIVATE_READ_FAULT = re.compile(
    r'FATAL unexpected VS trap domain=0+ cause=0*15 '
    r'pc=[0-9a-f]+ stval=[0-9a-f]+ htval=0*28080000')


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_markers(serial, markers):
    missing = []
    cursor = 0
    for marker in markers:
        offset = serial.find(marker, cursor)
        if offset < 0:
            missing.append(marker)
        else:
            cursor = offset + len(marker)
    return missing, cursor


def automatic_run(args, build, out, qemu, qemu_version, artifacts, kernel_sha,
                  mode, kernel):
    host = 'host-' + mode
    command = [
        qemu, '-machine', 'virt', '-accel', 'tcg', '-cpu', CPU,
        '-m', '1G', '-smp', '1',
        '-bios', str(build / 'fw_jump.bin'),
        '-dtb', str(build / (host + '.dtb')),
        '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
        '-nic', 'none', '-no-reboot',
    ]
    loads = [
        (build / 'monitor.bin', 0x80100000),
        (kernel, 0x80200000),
        (build / (host + '.cpio'), 0x85000000),
        (build / (host + '.dtb'), 0x9f000000),
        (kernel, 0xa0200000),
        (build / 'guest.cpio', 0xa5000000),
        (build / 'guest.dtb', 0xa7000000),
    ]
    for path, address in loads:
        if ',' in str(path):
            raise ValueError('QEMU loader paths cannot contain commas: ' + str(path))
        command += ['-device',
                    f'loader,file={path},addr={address:#x},force-raw=on']

    out.mkdir(parents=True)
    timed_out = False
    serial_path = out / 'serial.log'
    with serial_path.open('wb') as log:
        try:
            code = subprocess.run(command, stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT,
                                  timeout=90).returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, 124
    serial = serial_path.read_text(errors='replace')

    markers = list(COMMON_MARKERS)
    if args.private_read:
        markers.append(NEGATIVE_MARKER)
    else:
        markers.extend(POSITIVE_MARKERS)
    missing, _ = find_markers(serial, markers)
    getpid_count = len(re.findall(r'(?m)^getpid=1\r?$', serial))
    forbidden = [text for text in FORBIDDEN if text in serial]
    common = (
        not timed_out
        and code != 124
        and not missing
        and getpid_count == 2
        and 'Linux version 6.12.' in serial
        and serial.count('Linux version 6.12.') >= 2
        and not forbidden
    )

    fault = PRIVATE_READ_FAULT.search(serial)
    fatal_count = serial.count('[HS] FATAL')
    if args.private_read:
        attempt = serial.find(NEGATIVE_MARKER)
        fault_position = fault.start() if fault else -1
        normal_completion = any(text in serial for text in (
            'DONGTIAN_DRIVER_WORKFLOW_PASS',
            'MINIMAL_LINUX_CVM_PASS',
            'HOST_PRIVATE_MAP_DENIED_NOT_ISOLATION_EVIDENCE',
        ))
        passed = (
            common
            and code == 1
            and attempt >= 0
            and fault_position > attempt
            and fatal_count == 1
            and not normal_completion
        )
        status = 'PASS_EXPECTED_CPU_READ_DENIAL' if passed else 'FAIL'
    else:
        passed = (
            common
            and code == 0
            and '[HS] FATAL' not in serial
            and 'DONGTIAN_DRIVER_WORKFLOW_PASS' in serial
            and 'MINIMAL_LINUX_CVM_PASS' in serial
        )
        status = 'PASS_LINUX_HOST_AND_CVM' if passed else 'FAIL'

    record = {
        'status': status,
        'mode': mode,
        'interactive': False,
        'automatic_acceptance': True,
        'private_read_negative': args.private_read,
        'command': command,
        'qemu': qemu_version,
        'exit_code': code,
        'timed_out': timed_out,
        'missing_markers': missing,
        'getpid_count': getpid_count,
        'forbidden_markers': forbidden,
        'fatal_count': fatal_count,
        'serial_sha256': sha256_file(serial_path),
        'build_artifact_hashes': artifacts,
        'kernel_sha256': kernel_sha,
        'build_receipt': str(build / 'receipt.json'),
        'physical_board_executed': False,
    }
    if args.private_read:
        record['fault_matched'] = bool(fault)
    (out / 'receipt.json').write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print(serial[-6000:], end='')
    print(status)
    return 0 if passed else 1


def interactive_run(args, build, out, qemu, qemu_version, artifacts, kernel_sha,
                    mode, kernel):
    host = 'host-' + mode
    command = [
        qemu, '-machine', 'virt', '-accel', 'tcg', '-cpu', CPU,
        '-m', '1G', '-smp', '1',
        '-bios', str(build / 'fw_jump.bin'),
        '-dtb', str(build / (host + '.dtb')),
        '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
        '-nic', 'none', '-no-reboot',
    ]
    loads = [
        (build / 'monitor.bin', 0x80100000),
        (kernel, 0x80200000),
        (build / (host + '.cpio'), 0x85000000),
        (build / (host + '.dtb'), 0x9f000000),
        (kernel, 0xa0200000),
        (build / 'guest.cpio', 0xa5000000),
        (build / 'guest.dtb', 0xa7000000),
    ]
    for path, address in loads:
        if ',' in str(path):
            raise ValueError('QEMU loader paths cannot contain commas: ' + str(path))
        command += ['-device',
                    f'loader,file={path},addr={address:#x},force-raw=on']

    out.mkdir(parents=True)
    try:
        code = subprocess.run(command).returncode
    except KeyboardInterrupt:
        code = 130
    status = 'INTERACTIVE_SESSION_ENDED' if code == 0 else 'ERROR'
    record = {
        'status': status,
        'mode': mode,
        'interactive': True,
        'automatic_acceptance': False,
        'private_read_negative': False,
        'command': command,
        'qemu': qemu_version,
        'exit_code': code,
        'timed_out': False,
        'build_artifact_hashes': artifacts,
        'kernel_sha256': kernel_sha,
        'build_receipt': str(build / 'receipt.json'),
        'physical_board_executed': False,
    }
    (out / 'receipt.json').write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print(status)
    return 0 if code == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True,
                        help='directory containing a PASS build receipt')
    parser.add_argument('--output', type=Path, required=True,
                        help='new run directory outside the repository')
    parser.add_argument('--qemu', default='qemu-system-riscv64',
                        help='QEMU RISC-V system emulator')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--private-read', action='store_true',
                       help='expected-failure host CPU private-read experiment')
    group.add_argument('--interactive', action='store_true',
                       help='attach the serial console and never auto-accept')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    build = args.build.resolve()
    out = args.output.resolve()
    if out.exists() or out == root or root in out.parents:
        parser.error('output must be a new directory outside the repository')
    if out == build or build in out.parents:
        parser.error('output must be outside the build directory')
    if not build.is_dir():
        parser.error('build directory not found: ' + str(build))

    qemu = shutil.which(args.qemu)
    if not qemu:
        parser.error('QEMU not found: ' + args.qemu)
    qemu = str(Path(qemu).resolve())

    receipt_path = build / 'receipt.json'
    if not receipt_path.is_file():
        parser.error('build receipt not found: ' + str(receipt_path))
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        parser.error('cannot read build receipt: ' + str(error))
    if receipt.get('status') != 'PASS':
        parser.error('build receipt is not PASS')
    if receipt.get('profile') != 'opensbi-driver':
        parser.error('build receipt profile is not opensbi-driver')
    artifacts = receipt.get('artifacts')
    if not isinstance(artifacts, dict) or not artifacts:
        parser.error('build receipt has no artifact hashes')

    for name, digest in artifacts.items():
        path = build / name
        if not path.is_file():
            parser.error('build artifact missing: ' + name)
        if sha256_file(path) != digest:
            parser.error('build artifact hash mismatch: ' + name)

    mode = 'private-read' if args.private_read else \
        'interactive' if args.interactive else 'auto'
    required = (
        'fw_jump.bin', 'monitor.bin', 'host-' + mode + '.cpio',
        'host-' + mode + '.dtb', 'guest.cpio', 'guest.dtb',
    )
    for name in required:
        if name not in artifacts:
            parser.error('build receipt lacks required artifact: ' + name)

    fw = build / 'fw_jump.bin'
    if fw.stat().st_size <= 0 or fw.stat().st_size >= 0x100000:
        parser.error('fw_jump.bin size is incompatible with the monitor address')
    if (build / 'monitor.bin').stat().st_size == 0:
        parser.error('monitor.bin is empty')

    kernel = root / 'images/Image'
    if not kernel.is_file():
        parser.error('missing repo/images/Image')
    kernel_sha = sha256_file(kernel)
    if kernel_sha != receipt.get('kernel_sha256'):
        parser.error('kernel hash does not match the build receipt')
    kernel_info_path = root / 'images/kernel-info.json'
    if not kernel_info_path.is_file():
        parser.error('missing images/kernel-info.json')
    kernel_info = json.loads(kernel_info_path.read_text())
    if kernel_sha != kernel_info.get('image_sha256'):
        parser.error('kernel hash does not match images/kernel-info.json')

    try:
        qemu_version = subprocess.check_output(
            [qemu, '--version'], text=True, stderr=subprocess.STDOUT,
            timeout=10).strip()
    except (OSError, subprocess.SubprocessError) as error:
        parser.error('cannot query QEMU version: ' + str(error))

    try:
        if args.interactive:
            return interactive_run(args, build, out, qemu, qemu_version,
                                   artifacts, kernel_sha, mode, kernel)
        return automatic_run(args, build, out, qemu, qemu_version,
                             artifacts, kernel_sha, mode, kernel)
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    sys.exit(main())
