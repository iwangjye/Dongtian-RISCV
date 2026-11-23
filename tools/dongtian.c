/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Dongtian control tool: a freestanding RV64 Linux userspace program.
 *
 * It uses only direct Linux syscalls and the fixed Dongtian UAPI, so it can
 * be linked without a C library or a Linux UAPI sysroot.  It controls only
 * /dev/dongtian; the optional "load" command opens a user-supplied module
 * file and calls finit_module (SYS_finit_module = 273).
 */

#include <stddef.h>
#include <stdint.h>

#include "dongtian_abi.h"

#define SYS_ioctl 29
#define SYS_openat 56
#define SYS_close 57
#define SYS_write 64
#define SYS_exit 93
#define SYS_finit_module 273

#define AT_FDCWD (-100)
#define O_RDONLY 0

static long syscall3(long nr, long a0, long a1, long a2)
{
	register long r_a0 __asm__("a0") = a0;
	register long r_a1 __asm__("a1") = a1;
	register long r_a2 __asm__("a2") = a2;
	register long r_a7 __asm__("a7") = nr;

	__asm__ volatile("ecall"
			 : "+r"(r_a0)
			 : "r"(r_a1), "r"(r_a2), "r"(r_a7)
			 : "memory");
	return r_a0;
}

static long syscall4(long nr, long a0, long a1, long a2, long a3)
{
	register long r_a0 __asm__("a0") = a0;
	register long r_a1 __asm__("a1") = a1;
	register long r_a2 __asm__("a2") = a2;
	register long r_a3 __asm__("a3") = a3;
	register long r_a7 __asm__("a7") = nr;

	__asm__ volatile("ecall"
			 : "+r"(r_a0)
			 : "r"(r_a1), "r"(r_a2), "r"(r_a3), "r"(r_a7)
			 : "memory");
	return r_a0;
}

static __attribute__((noreturn)) void sys_exit(int status)
{
	register long r_a0 __asm__("a0") = status;
	register long r_a7 __asm__("a7") = SYS_exit;

	__asm__ volatile("ecall" : : "r"(r_a0), "r"(r_a7) : "memory");
	__builtin_unreachable();
}

void *memset(void *dst, int c, size_t n)
{
	unsigned char *p = (unsigned char *)dst;

	while (n--)
		*p++ = (unsigned char)c;
	return dst;
}

void *memcpy(void *dst, const void *src, size_t n)
{
	unsigned char *d = (unsigned char *)dst;
	const unsigned char *s = (const unsigned char *)src;

	while (n--)
		*d++ = *s++;
	return dst;
}

static size_t str_len(const char *s)
{
	size_t n = 0;

	while (s[n])
		n++;
	return n;
}

static int str_eq(const char *a, const char *b)
{
	while (*a && *a == *b) {
		a++;
		b++;
	}
	return *a == *b;
}

static int write_all(int fd, const char *buf, size_t len)
{
	while (len) {
		long n = syscall3(SYS_write, fd, (long)buf, (long)len);

		if (n == -4) /* EINTR */
			continue;
		if (n <= 0)
			return -1;
		buf += n;
		len -= (size_t)n;
	}
	return 0;
}

static void out_str(int fd, const char *s)
{
	(void)write_all(fd, s, str_len(s));
}

static void out_char(int fd, char c)
{
	(void)write_all(fd, &c, 1);
}

static void out_u64(int fd, uint64_t v)
{
	char buf[20];
	int n = 0;
	int i;

	if (v == 0)
		buf[n++] = '0';
	while (v) {
		buf[n++] = (char)('0' + (v % 10));
		v /= 10;
	}
	for (i = 0; i < n / 2; i++) {
		char t = buf[i];

		buf[i] = buf[n - 1 - i];
		buf[n - 1 - i] = t;
	}
	(void)write_all(fd, buf, (size_t)n);
}

static const char *state_name(unsigned int state)
{
	switch (state) {
	case DONGTIAN_STATE_NATIVE:
		return "NATIVE";
	case DONGTIAN_STATE_DEMOTED:
		return "DEMOTED";
	case DONGTIAN_STATE_GUEST_DONE:
		return "GUEST_DONE";
	default:
		return "UNKNOWN";
	}
}

static const char *errno_name(long e)
{
	switch (e) {
	case 1:
		return "EPERM";
	case 2:
		return "ENOENT";
	case 5:
		return "EIO";
	case 6:
		return "ENXIO";
	case 9:
		return "EBADF";
	case 12:
		return "ENOMEM";
	case 13:
		return "EACCES";
	case 14:
		return "EFAULT";
	case 16:
		return "EBUSY";
	case 19:
		return "ENODEV";
	case 20:
		return "ENOTDIR";
	case 21:
		return "EISDIR";
	case 22:
		return "EINVAL";
	case 25:
		return "ENOTTY";
	case 28:
		return "ENOSPC";
	case 30:
		return "EROFS";
	case 38:
		return "ENOSYS";
	case 95:
		return "EOPNOTSUPP";
	case 114:
		return "EALREADY";
	default:
		return "UNKNOWN";
	}
}

static void print_error(const char *op, const char *detail, long err)
{
	long e = -err;

	if (e < 0)
		e = -e;

	out_str(2, "DONGTIAN_ERROR op=");
	out_str(2, op);
	if (detail) {
		out_str(2, " detail=");
		out_str(2, detail);
	}
	out_str(2, " errno=");
	out_u64(2, (uint64_t)e);
	out_str(2, " name=");
	out_str(2, errno_name(e));
	out_char(2, '\n');
}

static void print_info(const struct dongtian_info *info)
{
	out_str(1, "DONGTIAN_INFO abi=");
	out_u64(1, info->abi_version);
	out_str(1, " state=");
	out_u64(1, info->state);
	out_str(1, " state_name=");
	out_str(1, state_name(info->state));
	out_str(1, " guest_runs=");
	out_u64(1, info->guest_runs);
	out_char(1, '\n');
}

static int open_device(void)
{
	long fd = syscall4(SYS_openat, AT_FDCWD, (long)DONGTIAN_DEVICE_PATH,
			   O_RDONLY, 0);

	if (fd < 0) {
		print_error("open", DONGTIAN_DEVICE_PATH, fd);
		return -1;
	}
	return (int)fd;
}

static int read_info(struct dongtian_info *info)
{
	int fd = open_device();
	long ret;

	if (fd < 0)
		return -1;

	ret = syscall3(SYS_ioctl, fd, DONGTIAN_IOCTL_INFO, (long)info);
	(void)syscall3(SYS_close, fd, 0, 0);
	if (ret < 0) {
		print_error("ioctl:INFO", NULL, ret);
		return -1;
	}
	return 0;
}

static int run_ioctl(unsigned int cmd, const char *op)
{
	int fd = open_device();
	long ret;

	if (fd < 0)
		return -1;

	ret = syscall3(SYS_ioctl, fd, cmd, 0);
	(void)syscall3(SYS_close, fd, 0, 0);
	if (ret < 0) {
		print_error(op, NULL, ret);
		return -1;
	}
	return 0;
}

static int demo_fail(const char *reason)
{
	out_str(2, "DONGTIAN_CONTROL_DEMO_FAIL reason=");
	out_str(2, reason);
	out_char(2, '\n');
	return 4;
}

static int cmd_info(void)
{
	struct dongtian_info info;

	if (read_info(&info))
		return 3;
	print_info(&info);
	return 0;
}

static int cmd_demote(void)
{
	struct dongtian_info info;

	if (run_ioctl(DONGTIAN_IOCTL_DEMOTE, "ioctl:DEMOTE"))
		return 3;
	if (read_info(&info))
		return 3;
	print_info(&info);
	if (info.state != DONGTIAN_STATE_DEMOTED) {
		print_error("verify", "state is not DEMOTED", -22);
		return 4;
	}
	return 0;
}

static int cmd_run(void)
{
	struct dongtian_info info;

	if (run_ioctl(DONGTIAN_IOCTL_RUN, "ioctl:RUN"))
		return 3;
	if (read_info(&info))
		return 3;
	print_info(&info);
	if (info.state != DONGTIAN_STATE_GUEST_DONE ||
	    info.guest_runs != 1) {
		print_error("verify", "state/guest_runs after RUN", -22);
		return 4;
	}
	return 0;
}

static int cmd_demo(void)
{
	struct dongtian_info before;
	struct dongtian_info demoted;
	struct dongtian_info done;

	if (read_info(&before))
		return demo_fail("info_before");
	print_info(&before);
	if (before.abi_version != DONGTIAN_ABI_VERSION)
		return demo_fail("abi_version");
	if (before.state != DONGTIAN_STATE_NATIVE)
		return demo_fail("initial_state");
	if (before.guest_runs != 0)
		return demo_fail("initial_guest_runs");

	if (run_ioctl(DONGTIAN_IOCTL_DEMOTE, "ioctl:DEMOTE"))
		return demo_fail("demote_ioctl");
	if (read_info(&demoted))
		return demo_fail("info_after_demote");
	print_info(&demoted);
	if (demoted.state != DONGTIAN_STATE_DEMOTED)
		return demo_fail("demoted_state");
	if (demoted.guest_runs != 0)
		return demo_fail("demoted_guest_runs");

	if (run_ioctl(DONGTIAN_IOCTL_RUN, "ioctl:RUN"))
		return demo_fail("run_ioctl");
	if (read_info(&done))
		return demo_fail("info_after_run");
	print_info(&done);
	if (done.state != DONGTIAN_STATE_GUEST_DONE)
		return demo_fail("final_state");
	if (done.guest_runs != 1)
		return demo_fail("final_guest_runs");

	out_str(1, "DONGTIAN_CONTROL_DEMO_PASS\n");
	return 0;
}

static int cmd_load(const char *path)
{
	long fd;
	long ret;

	fd = syscall4(SYS_openat, AT_FDCWD, (long)path, O_RDONLY, 0);
	if (fd < 0) {
		print_error("open:module", path, fd);
		return 3;
	}

	ret = syscall3(SYS_finit_module, fd, (long)"", 0);
	(void)syscall3(SYS_close, fd, 0, 0);
	if (ret < 0) {
		print_error("finit_module", path, ret);
		return 3;
	}

	out_str(1, "DONGTIAN_LOAD ok path=");
	out_str(1, path);
	out_char(1, '\n');
	return 0;
}

static void usage(void)
{
	out_str(2, "usage: dongtian info|demote|run|demo\n");
	out_str(2, "       dongtian load <path-to-dongtian.ko>\n");
	out_str(2, "Control operations use only " DONGTIAN_DEVICE_PATH ".\n");
}

int main(int argc, char **argv)
{
	if (argc < 2) {
		usage();
		return 2;
	}

	if (str_eq(argv[1], "info"))
		return cmd_info();
	if (str_eq(argv[1], "demote"))
		return cmd_demote();
	if (str_eq(argv[1], "run"))
		return cmd_run();
	if (str_eq(argv[1], "demo"))
		return cmd_demo();
	if (str_eq(argv[1], "load")) {
		if (argc != 3) {
			usage();
			return 2;
		}
		return cmd_load(argv[2]);
	}

	usage();
	return 2;
}

void tool_main(unsigned long *initial_stack)
{
	int argc = 0;
	char **argv = NULL;

	if (initial_stack) {
		argc = (int)initial_stack[0];
		argv = (char **)&initial_stack[1];
	}

	sys_exit(main(argc, argv));
}
