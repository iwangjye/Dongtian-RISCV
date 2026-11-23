#!/usr/bin/env python3
"""Execute the actual two-Linux dynamic-demotion experiment in local QEMU."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

CPU = 'rv64,h=true,sstc=false,f=false,d=false,v=false,zfh=false,zfhmin=false,zfa=false,zfbfmin=false,svpbmt=false,zicboz=false,zicbom=false'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qemu', default='qemu-system-riscv64')
    parser.add_argument('--private-read', action='store_true', help='expected-failure host CPU private-read experiment')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    build, out = args.build.resolve(), args.output.resolve()
    if out.exists() or out == root or root in out.parents:
        parser.error('output must be a new directory outside the package')
    qemu = shutil.which(args.qemu)
    if not qemu:
        parser.error('qemu-system-riscv64 not found')
    sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
    receipt = json.loads((build / 'receipt.json').read_text())
    if receipt.get('status') != 'PASS':
        parser.error('build receipt is not PASS')
    for name, digest in receipt['artifacts'].items():
        if sha(build / name) != digest:
            parser.error('build artifact hash mismatch: ' + name)
    kernel = root / 'images/Image'
    if sha(kernel) != receipt['kernel_sha256']:
        parser.error('kernel hash mismatch')
    out.mkdir(parents=True)
    host = 'host-private-read' if args.private_read else 'host'
    cmd = [qemu, '-machine', 'virt', '-accel', 'tcg', '-cpu', CPU, '-m', '1G', '-smp', '1', '-bios', str(build / 'firmware.elf'), '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none', '-no-reboot']
    loads = [(kernel, 0x80200000), (build / (host + '.cpio'), 0x85000000), (build / (host + '.dtb'), 0x9f000000), (kernel, 0xa0200000), (build / 'guest.cpio', 0xa5000000), (build / 'guest.dtb', 0xa7000000)]
    for filename, address in loads:
        if ',' in str(filename):
            parser.error('QEMU loader paths cannot contain commas')
        cmd += ['-device', f'loader,file={filename},addr={address:#x},force-raw=on']
    version = subprocess.check_output([qemu, '--version'], text=True, timeout=10).strip()
    timed_out = False
    with (out / 'serial.log').open('wb') as log:
        try:
            code = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=60).returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, 124
    serial = (out / 'serial.log').read_text(errors='replace')
    markers = ['LINUX_USERSPACE_ROLE=host', 'uname.sysname=Linux', 'getpid=1', 'HOST_REQUEST_DYNAMIC_HS_TO_VS', '[HS] demotion complete; resuming Linux host userspace', 'HOST_AFTER_DEMOTION', 'HOST_AFTER_DEMOTION_TIME_OK', 'HOST_REQUEST_CVM_LINUX', '[HS] entering independent Linux CVM', 'LINUX_USERSPACE_ROLE=guest', 'uname.sysname=Linux', 'getpid=1', 'CVM_LINUX_USERSPACE_OK', '[HS] CVM requested shutdown; resuming demoted Linux host', 'HOST_AFTER_CVM_RETURN']
    missing, cursor = [], 0
    for marker in markers:
        offset = serial.find(marker, cursor)
        if offset < 0:
            missing.append(marker)
        else:
            cursor = offset + len(marker)
    ordinary_errors = ['Kernel panic', 'Oops:', 'HOST_INIT_FAIL_', 'HOST_AFTER_DEMOTION_TIME_FAIL', 'PRIVATE_READ_UNEXPECTED_RETURN']
    common = not timed_out and not missing and serial.count('Linux version 6.12.') >= 2 and not any(error in serial for error in ordinary_errors)
    if args.private_read:
        fault = re.search(r'FATAL unexpected VS trap domain=0+ cause=0*15 pc=[0-9a-f]+ stval=[0-9a-f]+ htval=0*28080000', serial)
        passed = common and code == 1 and 'HOST_PRIVATE_READ_ATTEMPT' in serial and bool(fault) and 'HOST_PRIVATE_MAP_DENIED_NOT_ISOLATION_EVIDENCE' not in serial and 'MINIMAL_LINUX_CVM_PASS' not in serial
        status = 'PASS_EXPECTED_CPU_READ_DENIAL' if passed else 'FAIL'
    else:
        passed = common and code == 0 and 'MINIMAL_LINUX_CVM_PASS' in serial[cursor:] and '[HS] FATAL' not in serial
        status = 'PASS_LINUX_HOST_AND_CVM' if passed else 'FAIL'
    record = {'status': status, 'command': cmd, 'qemu': version, 'exit_code': code, 'timed_out': timed_out, 'missing_markers': missing, 'serial_sha256': sha(out / 'serial.log'), 'build_artifact_hashes': receipt['artifacts'], 'kernel_sha256': sha(kernel), 'physical_board_executed': False, 'private_read_negative': args.private_read}
    (out / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')
    print(serial[-6000:], end='')
    print(status)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
