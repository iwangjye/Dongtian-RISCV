#!/usr/bin/env python3
"""Build the single-CVM Dongtian runtime on Linux x86_64.

Inputs are prepared by scripts/prepare-runtime.py (OpenSBI source tree plus
the matching Linux 6.12.117 module headers).  This script never downloads or
installs anything: the pinned archives and the kernel Image must already be
present in the repository.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
from pathlib import Path

MONITOR_ADDR = 0x80100000
FW_JUMP_MAX_BYTES = 0x100000
INITRD_GPA = 0x85000000

HOST_MODES = (
    ('host-auto', ()),
    ('host-interactive', ('-DDONGTIAN_INTERACTIVE',)),
    ('host-private-read', ('-DDONGTIAN_PRIVATE_READ',)),
)

SOURCE_PATHS = (
    'src/monitor-entry.S',
    'src/monitor.c',
    'src/trap.S',
    'src/lib.c',
    'src/host-init.c',
    'src/init.c',
    'src/dts/host.dts',
    'src/dts/guest.dts',
    'tools/dongtian.c',
    'tools/start.S',
    'driver/dongtian.c',
    'driver/Makefile',
    'include/dongtian_abi.h',
    'include/monitor.h',
    'opensbi/sbi_ecall_dongtian.c',
    'dependencies/manifest.json',
    'images/kernel-info.json',
)

ARTIFACT_NAMES = (
    'fw_jump.bin',
    'monitor.elf',
    'monitor.bin',
    'dongtian',
    'dongtian.ko',
    'host-auto.cpio',
    'host-interactive.cpio',
    'host-private-read.cpio',
    'guest.cpio',
    'host-auto.dtb',
    'host-interactive.dtb',
    'host-private-read.dtb',
    'guest.dtb',
)


class ConfigError(RuntimeError):
    """Invalid command line, prepared directory, or repository input."""


class BuildError(RuntimeError):
    """A build step failed; the receipt and its log must be kept."""


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return value


def locate_tool(explicit, names):
    candidates = [explicit] if explicit else list(names)
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return str(Path(found).resolve())
    raise ConfigError('tool not found; tried: ' + ', '.join(candidates))


def resolve_cross_compile(explicit):
    """Return (CROSS_COMPILE prefix, gcc path, objcopy path)."""
    if explicit:
        prefix = explicit
        if '/' in prefix or os.sep in prefix:
            trailing_separator = prefix.endswith('/') or prefix.endswith(os.sep)
            base = prefix.rstrip('/' + os.sep)
            prefix = str(Path(base).resolve())
            if trailing_separator:
                prefix += '/'
        cc = shutil.which(prefix + 'gcc')
        if not cc:
            raise ConfigError('cross compiler not found: ' + prefix + 'gcc')
        objcopy = shutil.which(prefix + 'objcopy')
        if not objcopy:
            raise ConfigError('cross objcopy not found: ' + prefix + 'objcopy')
        return prefix, os.path.abspath(cc), str(Path(objcopy).resolve())

    cc = shutil.which('riscv64-linux-gnu-gcc') or shutil.which('riscv64-unknown-elf-gcc')
    if not cc:
        raise ConfigError('riscv64-unknown-elf-gcc not found; pass --cross-compile <prefix>')
    # Do not resolve the symlink: the default prefix is "which ...gcc" minus
    # the literal "gcc" suffix, as documented by the task interface.
    cc = os.path.abspath(cc)
    if not cc.endswith('gcc'):
        raise ConfigError('unexpected default compiler path: ' + cc)
    prefix = cc[:-3]
    objcopy = shutil.which(prefix + 'objcopy')
    if not objcopy:
        raise ConfigError('cross objcopy not found: ' + prefix + 'objcopy')
    return prefix, cc, str(Path(objcopy).resolve())


def write_log(path, text):
    path.write_text(text, encoding='utf-8', errors='replace')


def newc_archive(entries):
    """Deterministic newc writer, copied from the repository's build.py."""
    data = bytearray()
    ino = 0

    def add(name, mode, payload=b'', major=0, minor=0):
        nonlocal ino
        ino += 1
        name_bytes = name.encode() + b'\0'
        fields = [ino, mode, 0, 0, 1, 0, len(payload), 0, 0,
                  major, minor, len(name_bytes), 0]
        data.extend(b'070701')
        data.extend(b''.join(f'{value:08x}'.encode() for value in fields))
        data.extend(name_bytes)
        data.extend(bytes((-len(data)) % 4))
        data.extend(payload)
        data.extend(bytes((-len(data)) % 4))

    for entry in entries:
        add(*entry)
    add('TRAILER!!!', 0)
    return bytes(data)


def host_entries(init_path, module_path, tool_path):
    directory = stat.S_IFDIR | 0o755
    return [
        ('dev', directory),
        ('dev/console', stat.S_IFCHR | 0o600, b'', 5, 1),
        ('lib', directory),
        ('lib/modules', directory),
        ('proc', directory),
        ('sbin', directory),
        ('sys', directory),
        ('tmp', stat.S_IFDIR | 0o1777),
        ('init', stat.S_IFREG | 0o755, init_path.read_bytes()),
        ('lib/modules/dongtian.ko', stat.S_IFREG | 0o644,
         module_path.read_bytes()),
        ('sbin/dongtian', stat.S_IFREG | 0o755, tool_path.read_bytes()),
    ]


def guest_entries(init_path):
    return [('init', stat.S_IFREG | 0o755, init_path.read_bytes())]


def elf_entry(path):
    data = path.read_bytes()
    if len(data) < 64 or data[:4] != b'\x7fELF' or data[4] != 2 or data[5] != 1:
        raise BuildError('not a little-endian ELF64 file: ' + str(path))
    return struct.unpack_from('<Q', data, 24)[0]


def module_metadata(path):
    data = path.read_bytes()
    result = {}
    for key in ('vermagic', 'srcversion', 'version'):
        match = re.search(rb'(?:^|\x00)' + key.encode() + rb'=([^\x00\n]+)', data)
        if match:
            result[key] = match.group(1).decode('utf-8', errors='replace')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deps', type=Path, required=True,
                        help='directory produced by scripts/prepare-runtime.py')
    parser.add_argument('--output', type=Path, required=True,
                        help='new build directory outside the repository')
    parser.add_argument('--cross-compile',
                        help='RISC-V toolchain prefix (default: riscv64-unknown-elf-)')
    parser.add_argument('--dtc', help='device tree compiler (default: dtc from PATH)')
    parser.add_argument('--jobs', type=positive_int, default=2,
                        help='parallel make jobs (default: 2)')
    args = parser.parse_args()

    if sys.version_info < (3, 12):
        parser.error('Python 3.12+ is required')

    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    deps = args.deps.resolve()

    try:
        if out.exists() or out == root or root in out.parents:
            raise ConfigError('output must be a new directory outside the repository')
        if not deps.is_dir():
            raise ConfigError('prepared dependency directory not found: ' + str(deps))
        prepared_path = deps / 'prepared.json'
        if not prepared_path.is_file():
            raise ConfigError('prepared.json not found in ' + str(deps))
        try:
            prepared = json.loads(prepared_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigError('cannot read prepared.json: ' + str(error))

        for key in ('opensbi_source', 'kernel_headers', 'input_manifest_sha256'):
            if not isinstance(prepared.get(key), str) or not prepared[key]:
                raise ConfigError('prepared.json lacks ' + key)
        source = Path(prepared['opensbi_source'])
        headers = Path(prepared['kernel_headers'])
        if not source.is_absolute() or not headers.is_absolute():
            raise ConfigError('prepared OpenSBI/header paths must be absolute')

        manifest_path = root / 'dependencies/manifest.json'
        if not manifest_path.is_file():
            raise ConfigError('missing ' + str(manifest_path))
        manifest_sha = sha256_file(manifest_path)
        if prepared['input_manifest_sha256'] != manifest_sha:
            raise ConfigError('prepared.json input_manifest_sha256 does not match '
                              'dependencies/manifest.json')
        manifest = json.loads(manifest_path.read_text())
        if prepared.get('opensbi_commit') != manifest.get('opensbi_commit'):
            raise ConfigError('prepared OpenSBI commit does not match the dependency manifest')

        if not (source / 'Makefile').is_file():
            raise ConfigError('OpenSBI source tree not found: ' + str(source))
        extension = source / 'lib/sbi/sbi_ecall_dongtian.c'
        objects = source / 'lib/sbi/objects.mk'
        if not extension.is_file() or not objects.is_file():
            raise ConfigError('prepared OpenSBI tree lacks the Dongtian extension source')
        if sha256_file(extension) != sha256_file(root / 'opensbi/sbi_ecall_dongtian.c'):
            raise ConfigError('prepared OpenSBI extension is stale; prepare a new dependency directory')
        if 'sbi_ecall_dongtian' not in objects.read_text(errors='replace'):
            raise ConfigError('prepared OpenSBI objects.mk lacks sbi_ecall_dongtian')
        if not (headers / 'Makefile').is_file():
            raise ConfigError('prepared kernel headers not found: ' + str(headers))

        missing = [name for name in SOURCE_PATHS if not (root / name).is_file()]
        if missing:
            raise ConfigError('missing required source/input files: ' + ', '.join(missing))

        kernel_info_path = root / 'images/kernel-info.json'
        if not kernel_info_path.is_file():
            raise ConfigError('missing ' + str(kernel_info_path))
        kernel_info = json.loads(kernel_info_path.read_text())
        kernel = root / 'images/Image'
        if not kernel.is_file():
            raise ConfigError('missing repo/images/Image; this script does not download it')
        kernel_sha = sha256_file(kernel)
        expected_kernel_sha = kernel_info.get('image_sha256')
        if not expected_kernel_sha or kernel_sha != expected_kernel_sha:
            raise ConfigError('repo/images/Image sha256 does not match images/kernel-info.json')
        expected_bytes = kernel_info.get('image_bytes')
        if expected_bytes and kernel.stat().st_size != expected_bytes:
            raise ConfigError('repo/images/Image size does not match images/kernel-info.json')

        if not sys.platform.startswith('linux') or \
                platform.machine().lower() not in ('x86_64', 'amd64'):
            raise ConfigError('build-runtime.py must run on Linux x86_64')

        make = locate_tool(None, ('make',))
        if not shutil.which('gcc'):
            raise ConfigError('system gcc not found; OpenSBI host tools need it')
        dtc = locate_tool(args.dtc, ('dtc',))
        prefix, cc, objcopy = resolve_cross_compile(args.cross_compile)
    except ConfigError as error:
        parser.error(str(error))

    try:
        out.mkdir(parents=True)
    except OSError as error:
        parser.error('cannot create output directory: ' + str(error))

    receipt = {
        'scope': 'OpenSBI fw_jump + HS monitor + Dongtian module + Linux host/CVM initramfs',
        'profile': 'opensbi-driver',
        'status': 'FAIL',
        'hardware_executed': False,
        'steps': [],
        'source_hashes': {},
        'compiler': None,
        'cross_compile': prefix,
        'opensbi_commit': manifest.get('opensbi_commit'),
        'opensbi_version': manifest.get('opensbi_version'),
        'linux_version': manifest.get('linux_version'),
        'input_manifest_sha256': manifest_sha,
        'prepared_sha256': sha256_file(prepared_path),
        'opensbi_source': str(source),
        'kernel_headers': str(headers),
        'kernel_sha256': kernel_sha,
        'module': None,
    }

    def run_step(name, command, cwd=None, timeout=120):
        command = [str(item) for item in command]
        log_path = out / (name + '.log')
        try:
            result = subprocess.run(command, cwd=cwd, text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    timeout=timeout)
            write_log(log_path, result.stdout or '')
            code = result.returncode
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ''
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='replace')
            write_log(log_path, output + f'\n[timeout after {timeout}s]\n')
            receipt['steps'].append({'name': name, 'command': command,
                                     'exit_code': 124})
            raise BuildError(f'{name} timed out after {timeout}s; see {log_path}')
        except OSError as error:
            write_log(log_path, str(error) + '\n')
            receipt['steps'].append({'name': name, 'command': command,
                                     'exit_code': 127})
            raise BuildError(f'{name} could not start: {error}; see {log_path}')

        receipt['steps'].append({'name': name, 'command': command,
                                 'exit_code': code})
        if code:
            raise BuildError(f'{name} failed with exit {code}; see {log_path}')
        return result.stdout or ''

    try:
        receipt['source_hashes'] = {
            name: sha256_file(root / name) for name in SOURCE_PATHS
        }
        receipt['compiler'] = run_step(
            'compiler-version', [cc, '--version'], timeout=120).strip()

        opensbi_build = out / 'opensbi'
        run_step(
            'opensbi-build',
            [make, '-j' + str(args.jobs), 'O=' + str(opensbi_build),
             'PLATFORM=generic', 'CROSS_COMPILE=' + prefix,
             'FW_DYNAMIC=n', 'FW_PAYLOAD=n', 'FW_JUMP=y',
             'FW_JUMP_ADDR=0x80200000', 'FW_JUMP_FDT_ADDR=0x9f000000'],
            cwd=str(source), timeout=180)

        fw_candidates = (
            opensbi_build / 'platform/generic/firmware/fw_jump.bin',
            opensbi_build / 'build/platform/generic/firmware/fw_jump.bin',
        )
        fw_source = next((path for path in fw_candidates if path.is_file()), None)
        if fw_source is None:
            raise BuildError('OpenSBI build did not produce fw_jump.bin')
        fw_bytes = fw_source.stat().st_size
        if fw_bytes <= 0 or fw_bytes >= FW_JUMP_MAX_BYTES:
            raise BuildError(f'fw_jump.bin size {fw_bytes:#x} is outside '
                             f'(0, {FW_JUMP_MAX_BYTES:#x}); it would overlap the monitor')
        shutil.copyfile(fw_source, out / 'fw_jump.bin')
        write_log(out / 'fw-jump.log',
                  f'source={fw_source}\nbytes={fw_bytes}\n'
                  f'sha256={sha256_file(out / "fw_jump.bin")}\n')
        receipt['fw_jump_bytes'] = fw_bytes
        receipt['fw_jump_source'] = str(fw_source)

        driver_out = out / 'driver'
        include_out = out / 'include'
        driver_out.mkdir()
        include_out.mkdir()
        shutil.copyfile(root / 'driver/dongtian.c', driver_out / 'dongtian.c')
        shutil.copyfile(root / 'driver/Makefile', driver_out / 'Makefile')
        shutil.copyfile(root / 'include/dongtian_abi.h',
                        include_out / 'dongtian_abi.h')
        run_step(
            'driver-build',
            [make, '-C', str(headers), 'M=' + str(driver_out),
             'ARCH=riscv', 'CROSS_COMPILE=' + prefix, 'CC=' + cc,
             'LD=' + prefix + 'ld', 'AR=' + prefix + 'ar',
             'NM=' + prefix + 'nm', 'OBJCOPY=' + prefix + 'objcopy',
             'CONFIG_DEBUG_INFO_BTF_MODULES=', 'modules'],
            timeout=180)
        module = driver_out / 'dongtian.ko'
        if not module.is_file():
            raise BuildError('driver build did not produce dongtian.ko')
        shutil.copyfile(module, out / 'dongtian.ko')
        metadata = module_metadata(out / 'dongtian.ko')
        receipt['module'] = {
            'name': 'dongtian',
            'module_btf_debug_info': False,
            'path': 'dongtian.ko',
            'bytes': (out / 'dongtian.ko').stat().st_size,
            'vermagic': metadata.get('vermagic'),
            'srcversion': metadata.get('srcversion'),
            'version': metadata.get('version'),
        }

        monitor_flags = [
            '-march=rv64imah_zicsr_zifencei', '-mabi=lp64',
            '-mcmodel=medany', '-msmall-data-limit=0', '-mno-relax',
            '-fno-pic', '-fno-pie', '-fno-stack-protector',
            '-ffreestanding', '-fno-builtin', '-O2', '-g',
            '-Wall', '-Wextra', '-Werror',
            '-I' + str(root / 'include'), '-DDONGTIAN_OPENSBI',
        ]
        monitor_objects = []
        for source_name, object_name, step_name in (
                ('monitor-entry.S', 'monitor-entry.o', 'compile-monitor-entry'),
                ('monitor.c', 'monitor.o', 'compile-monitor'),
                ('trap.S', 'trap.o', 'compile-monitor-trap'),
                ('lib.c', 'lib-monitor.o', 'compile-monitor-lib')):
            target = out / object_name
            run_step(step_name,
                     [cc, *monitor_flags, '-c', str(root / 'src' / source_name),
                      '-o', str(target)], timeout=120)
            monitor_objects.append(str(target))
        monitor_elf = out / 'monitor.elf'
        run_step('link-monitor',
                 [cc, *monitor_flags, '-nostdlib', '-static',
                  '-Wl,--no-relax,--build-id=none',
                  '-T', str(root / 'src/monitor-linker.ld'),
                  '-o', str(monitor_elf), *monitor_objects], timeout=120)
        entry = elf_entry(monitor_elf)
        if entry != MONITOR_ADDR:
            raise BuildError(f'monitor ELF entry is {entry:#x}, expected {MONITOR_ADDR:#x}')
        receipt['monitor_entry'] = f'{entry:#x}'
        monitor_bin = out / 'monitor.bin'
        run_step('objcopy-monitor',
                 [objcopy, '-O', 'binary', str(monitor_elf), str(monitor_bin)],
                 timeout=120)
        if monitor_bin.stat().st_size == 0:
            raise BuildError('monitor.bin is empty')
        receipt['monitor_bytes'] = monitor_bin.stat().st_size
        receipt['monitor_link_address'] = MONITOR_ADDR

        tool_flags = [
            '-march=rv64imac_zicsr_zifencei', '-mabi=lp64', '-O2',
            '-ffreestanding', '-fno-builtin', '-fno-pic', '-fno-pie',
            '-fno-stack-protector', '-msmall-data-limit=0', '-mno-relax',
            '-I' + str(root / 'include'),
        ]
        tool_objects = []
        for source_name, object_name, step_name in (
                ('tools/start.S', 'tool-start.o', 'compile-tool-start'),
                ('tools/dongtian.c', 'tool-dongtian.o', 'compile-tool')):
            target = out / object_name
            run_step(step_name,
                     [cc, *tool_flags, '-c', str(root / source_name),
                      '-o', str(target)], timeout=120)
            tool_objects.append(str(target))
        tool = out / 'dongtian'
        run_step('link-tool',
                 [cc, *tool_flags, '-nostdlib', '-static',
                  '-Wl,-e,_start,--build-id=none,--no-relax',
                  '-o', str(tool), *tool_objects], timeout=120)
        if not tool.is_file():
            raise BuildError('management tool was not produced')

        init_flags = [
            '-march=rv64imac_zicsr_zifencei', '-mabi=lp64', '-O2',
            '-ffreestanding', '-fno-builtin', '-fno-pic', '-fno-pie',
            '-fno-stack-protector', '-msmall-data-limit=0', '-mno-relax',
        ]
        init_link_flags = [
            '-nostdlib', '-static',
            '-Wl,-e,_start,--build-id=none,--no-relax',
        ]
        lib_object = out / 'init-lib.o'
        run_step('compile-init-lib',
                 [cc, *init_flags, '-c', str(root / 'src/lib.c'),
                  '-o', str(lib_object)], timeout=120)

        host_inits = {}
        for mode, macros in HOST_MODES:
            object_path = out / (mode + '-init.o')
            executable = out / (mode + '-init')
            run_step('compile-' + mode + '-init',
                     [cc, *init_flags, *macros, '-c',
                      str(root / 'src/host-init.c'), '-o', str(object_path)],
                     timeout=120)
            run_step('link-' + mode + '-init',
                     [cc, *init_flags, *init_link_flags, '-o', str(executable),
                      str(lib_object), str(object_path)], timeout=120)
            host_inits[mode] = executable

        guest_object = out / 'guest-init.o'
        guest_init = out / 'guest-init'
        run_step('compile-guest-init',
                 [cc, *init_flags, '-DROLE="guest"', '-c',
                  str(root / 'src/init.c'), '-o', str(guest_object)],
                 timeout=120)
        run_step('link-guest-init',
                 [cc, *init_flags, *init_link_flags, '-o', str(guest_init),
                  str(guest_object)], timeout=120)

        for mode, _ in HOST_MODES:
            payload = newc_archive(host_entries(host_inits[mode],
                                                out / 'dongtian.ko', tool))
            (out / (mode + '.cpio')).write_bytes(payload)
        (out / 'guest.cpio').write_bytes(newc_archive(guest_entries(guest_init)))

        dtb_inputs = [
            ('host-auto', root / 'src/dts/host.dts'),
            ('host-interactive', root / 'src/dts/host.dts'),
            ('host-private-read', root / 'src/dts/host.dts'),
            ('guest', root / 'src/dts/guest.dts'),
        ]
        for name, template in dtb_inputs:
            cpio = out / (name + '.cpio')
            text = template.read_text()
            if name.startswith('host-'):
                # OpenSBI probes these M-mode devices from the initial FDT.
                # Their addresses remain absent from post-handoff G-stage.
                for node in ('clint@2000000', 'test@100000', 'poweroff', 'reboot'):
                    pattern = r'(' + re.escape(node) + r'\s*\{)\s*status = "disabled";'
                    text, enabled = re.subn(pattern, r'\1\n status = "okay";', text)
                    if enabled != 1:
                        raise BuildError('missing firmware device node: ' + node)
            end = INITRD_GPA + cpio.stat().st_size
            text, count = re.subn(
                r'linux,initrd-end\s*=\s*<[^>]*>;',
                f'linux,initrd-end = <0x0 0x{end:x}>;', text)
            if count != 1:
                raise BuildError(f'expected exactly one linux,initrd-end in {template}')
            dts = out / (name + '.dts')
            dts.write_text(text)
            run_step('dtc-' + name,
                     [dtc, '-I', 'dts', '-O', 'dtb',
                      '-o', str(out / (name + '.dtb')), str(dts)],
                     timeout=120)

        for name in ARTIFACT_NAMES:
            if not (out / name).is_file():
                raise BuildError('expected artifact missing: ' + name)
        receipt['artifacts'] = {
            name: sha256_file(out / name) for name in ARTIFACT_NAMES
        }
        receipt['status'] = 'PASS'
        print('PASS: built ' + str(out))
    except (BuildError, OSError, ValueError) as error:
        receipt['error'] = str(error)
        print(str(error), file=sys.stderr)
    except Exception as error:  # keep a receipt even for an unexpected failure
        receipt['error'] = f'{type(error).__name__}: {error}'
        print(receipt['error'], file=sys.stderr)
    finally:
        (out / 'receipt.json').write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')

    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
