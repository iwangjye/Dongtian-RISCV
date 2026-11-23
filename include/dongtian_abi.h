/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Dongtian control UAPI
 *
 * This header is shared by the small Linux control driver, the freestanding
 * /dev/dongtian management tool, and the OpenSBI/HS side.  It deliberately
 * contains no Linux UAPI header dependency so that a no-libc RV64 tool can
 * include it directly.
 *
 * The SBI extension is a local experimental extension in the SBI-defined
 * experimental range (0x08000000..0x08ffffff):
 *
 *   EID 0x0800D07A
 *     FID 0 = QUERY      a0 = 0, a1 = state
 *     FID 1 = DEMOTE     native HS -> monitor, returns to the same kernel
 *                        continuation; on success a0 = 0, a1 = 0
 *     FID 2 = RUN        enter the independently preloaded guest from the
 *                        VS host; returns after guest shutdown; on success
 *                        a0 = 0, a1 = 0
 *     FID 3 = RUN_COUNT  a0 = 0, a1 = number of completed guest runs
 *
 * The prototype is single-hart and permits at most one guest run.
 */
#ifndef DONGTIAN_ABI_H
#define DONGTIAN_ABI_H

#define DONGTIAN_ABI_VERSION 1U

#define DONGTIAN_DEVICE_PATH "/dev/dongtian"

#define DONGTIAN_SBI_EID 0x0800D07AUL
#define DONGTIAN_SBI_FID_QUERY 0UL
#define DONGTIAN_SBI_FID_DEMOTE 1UL
#define DONGTIAN_SBI_FID_RUN 2UL
#define DONGTIAN_SBI_FID_RUN_COUNT 3UL

#define DONGTIAN_STATE_NATIVE 0U
#define DONGTIAN_STATE_DEMOTED 1U
#define DONGTIAN_STATE_GUEST_DONE 2U

/*
 * Fixed Linux generic ioctl numbers.  These are written as literal values so
 * that the freestanding tool does not need a kernel UAPI sysroot:
 *
 *   INFO   = _IOR('D', 0, struct dongtian_info) = 0x80104400
 *   DEMOTE = _IO('D', 1)                        = 0x00004401
 *   RUN    = _IO('D', 2)                        = 0x00004402
 */
#define DONGTIAN_IOCTL_INFO 0x80104400U
#define DONGTIAN_IOCTL_DEMOTE 0x00004401U
#define DONGTIAN_IOCTL_RUN 0x00004402U

struct dongtian_info {
	unsigned int abi_version;
	unsigned int state;
	unsigned long long guest_runs;
};

#if defined(__cplusplus)
static_assert(sizeof(struct dongtian_info) == 16,
	      "struct dongtian_info must remain 16 bytes");
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
_Static_assert(sizeof(struct dongtian_info) == 16,
	       "struct dongtian_info must remain 16 bytes");
#endif

#endif /* DONGTIAN_ABI_H */
