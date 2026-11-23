// SPDX-License-Identifier: GPL-2.0-only
/*
 * Dongtian control driver
 *
 * Small single-hart userspace control surface for the Dongtian
 * OpenSBI/HS-monitor prototype.  It exposes exactly three ioctls on
 * /dev/dongtian and forwards the fixed local SBI extension EID 0x0800D07A.
 *
 * This driver intentionally does not map arbitrary physical memory, load
 * guest images, accept an SBI extension/function ID from userspace, or
 * perform DMA.  The initial host and the preloaded guest images are trusted
 * inputs of the prototype.
 */

#include <linux/capability.h>
#include <linux/cpumask.h>
#include <linux/errno.h>
#include <linux/fs.h>
#include <linux/irqflags.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/sched.h>
#include <linux/smp.h>
#include <linux/types.h>
#include <linux/uaccess.h>
#include <asm/sbi.h>

#include "dongtian_abi.h"

#define DONGTIAN_DEVICE_NAME "dongtian"
#define DONGTIAN_DEVICE_MODE 0600

/*
 * Cached firmware view.  All userspace entries are serialized by
 * dongtian_lock, and the firmware remains authoritative for INFO.
 */
static DEFINE_MUTEX(dongtian_lock);
static unsigned int dongtian_state = DONGTIAN_STATE_NATIVE;
static u64 dongtian_guest_runs;

static int dongtian_sbi_errno(long error)
{
	switch (error) {
	case 0:
		return 0;
	case SBI_ERR_FAILURE:
		return -EIO;
	case SBI_ERR_NOT_SUPPORTED:
		return -EOPNOTSUPP;
	case SBI_ERR_INVALID_PARAM:
		return -EINVAL;
	case SBI_ERR_DENIED:
		return -EPERM;
	case SBI_ERR_INVALID_ADDRESS:
		return -EFAULT;
	case SBI_ERR_ALREADY_AVAILABLE:
	case SBI_ERR_ALREADY_STARTED:
	case SBI_ERR_ALREADY_STOPPED:
		return -EALREADY;
	default:
		/*
		 * A negative SBI error must never be returned as a successful
		 * positive value or leak through as an unrelated errno.
		 */
		return -EIO;
	}
}

/*
 * Run one fixed SBI call on CPU 0 with preemption and interrupts disabled.
 *
 * The prototype is single-hart: this deliberately does not migrate the task
 * to CPU 0 and does not perform an SMP rendezvous.  If the caller is not
 * already on CPU 0, fail instead of issuing the call on the wrong hart.
 */
static int dongtian_ecall_on_cpu0(unsigned long fid, struct sbiret *ret)
{
	unsigned long flags;

	if (!cpu_online(0))
		return -ENODEV;

	get_cpu();
	if (smp_processor_id() != 0) {
		put_cpu();
		return -ENODEV;
	}

	local_irq_save(flags);
	*ret = sbi_ecall(DONGTIAN_SBI_EID, fid, 0, 0, 0, 0, 0, 0);
	local_irq_restore(flags);
	put_cpu();

	return 0;
}

static int dongtian_query(unsigned int *state, u64 *guest_runs)
{
	struct sbiret ret;
	int rc;

	rc = dongtian_ecall_on_cpu0(DONGTIAN_SBI_FID_QUERY, &ret);
	if (rc)
		return rc;
	if (ret.error)
		return dongtian_sbi_errno(ret.error);
	if (ret.value < 0 || ret.value > DONGTIAN_STATE_GUEST_DONE)
		return -EIO;

	*state = (unsigned int)ret.value;

	rc = dongtian_ecall_on_cpu0(DONGTIAN_SBI_FID_RUN_COUNT, &ret);
	if (rc)
		return rc;
	if (ret.error)
		return dongtian_sbi_errno(ret.error);
	if (ret.value < 0)
		return -EIO;

	*guest_runs = (u64)ret.value;
	return 0;
}

static int dongtian_info(struct dongtian_info __user *uinfo)
{
	struct dongtian_info info;
	unsigned int state;
	u64 guest_runs;
	int rc;

	if (!uinfo)
		return -EFAULT;

	mutex_lock(&dongtian_lock);
	rc = dongtian_query(&state, &guest_runs);
	if (rc)
		goto out_unlock;

	dongtian_state = state;
	dongtian_guest_runs = guest_runs;

	info.abi_version = DONGTIAN_ABI_VERSION;
	info.state = state;
	info.guest_runs = guest_runs;

	if (copy_to_user(uinfo, &info, sizeof(info))) {
		rc = -EFAULT;
		goto out_unlock;
	}
out_unlock:
	mutex_unlock(&dongtian_lock);
	return rc;
}

static int dongtian_demote(void)
{
	struct sbiret ret;
	int rc;

	mutex_lock(&dongtian_lock);
	if (dongtian_state != DONGTIAN_STATE_NATIVE) {
		rc = -EALREADY;
		goto out_unlock;
	}

	rc = dongtian_ecall_on_cpu0(DONGTIAN_SBI_FID_DEMOTE, &ret);
	if (rc)
		goto out_unlock;
	if (ret.error) {
		rc = dongtian_sbi_errno(ret.error);
		goto out_unlock;
	}
	if (ret.value != 0) {
		/* FID 1 must return a0=0/a1=0; do not claim success otherwise. */
		pr_err("dongtian: DEMOTE returned unexpected value %ld\n",
		       ret.value);
		rc = -EIO;
		goto out_unlock;
	}

	dongtian_state = DONGTIAN_STATE_DEMOTED;
	rc = 0;
out_unlock:
	mutex_unlock(&dongtian_lock);
	return rc;
}

static int dongtian_run(void)
{
	struct sbiret ret;
	int rc;

	mutex_lock(&dongtian_lock);
	if (dongtian_state != DONGTIAN_STATE_DEMOTED) {
		rc = -EINVAL;
		goto out_unlock;
	}

	rc = dongtian_ecall_on_cpu0(DONGTIAN_SBI_FID_RUN, &ret);
	if (rc)
		goto out_unlock;
	if (ret.error) {
		rc = dongtian_sbi_errno(ret.error);
		goto out_unlock;
	}
	if (ret.value != 0) {
		/* FID 2 must return a0=0/a1=0 after guest shutdown. */
		pr_err("dongtian: RUN returned unexpected value %ld\n",
		       ret.value);
		rc = -EIO;
		goto out_unlock;
	}

	dongtian_state = DONGTIAN_STATE_GUEST_DONE;
	dongtian_guest_runs = 1;
	rc = 0;
out_unlock:
	mutex_unlock(&dongtian_lock);
	return rc;
}

static int dongtian_open(struct inode *inode, struct file *file)
{
	(void)inode;
	(void)file;

	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	return 0;
}

static long dongtian_ioctl(struct file *file, unsigned int cmd,
			   unsigned long arg)
{
	(void)file;

	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;

	switch (cmd) {
	case DONGTIAN_IOCTL_INFO:
		return dongtian_info((struct dongtian_info __user *)arg);
	case DONGTIAN_IOCTL_DEMOTE:
		return dongtian_demote();
	case DONGTIAN_IOCTL_RUN:
		return dongtian_run();
	default:
		return -ENOTTY;
	}
}

static const struct file_operations dongtian_fops = {
	.owner = THIS_MODULE,
	.open = dongtian_open,
	.unlocked_ioctl = dongtian_ioctl,
};

static struct miscdevice dongtian_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = DONGTIAN_DEVICE_NAME,
	.fops = &dongtian_fops,
	.mode = DONGTIAN_DEVICE_MODE,
};

static int __init dongtian_probe(void)
{
	struct sbiret ret;
	int rc;

	rc = dongtian_ecall_on_cpu0(DONGTIAN_SBI_FID_QUERY, &ret);
	if (rc) {
		pr_err("dongtian: CPU 0 is not available for SBI probe: %d\n",
		       rc);
		return rc;
	}
	if (ret.error) {
		pr_err("dongtian: SBI EID 0x%08lx probe failed (error %ld)\n",
		       DONGTIAN_SBI_EID, ret.error);
		if (ret.error == SBI_ERR_NOT_SUPPORTED)
			return -ENODEV;
		return dongtian_sbi_errno(ret.error);
	}
	if (ret.value < 0 || ret.value > DONGTIAN_STATE_GUEST_DONE) {
		pr_err("dongtian: QUERY returned invalid state %ld\n",
		       ret.value);
		return -ENODEV;
	}
	dongtian_state = (unsigned int)ret.value;

	rc = dongtian_ecall_on_cpu0(DONGTIAN_SBI_FID_RUN_COUNT, &ret);
	if (rc) {
		pr_err("dongtian: RUN_COUNT probe failed: %d\n", rc);
		return rc;
	}
	if (ret.error) {
		pr_err("dongtian: RUN_COUNT probe failed (error %ld)\n",
		       ret.error);
		if (ret.error == SBI_ERR_NOT_SUPPORTED)
			return -ENODEV;
		return dongtian_sbi_errno(ret.error);
	}
	if (ret.value < 0) {
		pr_err("dongtian: RUN_COUNT returned invalid value %ld\n",
		       ret.value);
		return -ENODEV;
	}
	dongtian_guest_runs = (u64)ret.value;

	return 0;
}

static int __init dongtian_init(void)
{
	int rc;

	rc = dongtian_probe();
	if (rc)
		return rc;

	rc = misc_register(&dongtian_misc);
	if (rc) {
		pr_err("dongtian: misc_register failed: %d\n", rc);
		return rc;
	}

	pr_info("dongtian: /dev/%s ready (ABI %u, state %u, guest_runs %llu)\n",
		DONGTIAN_DEVICE_NAME, DONGTIAN_ABI_VERSION, dongtian_state,
		(unsigned long long)dongtian_guest_runs);
	return 0;
}

static void __exit dongtian_exit(void)
{
	misc_deregister(&dongtian_misc);
	pr_info("dongtian: control driver removed\n");
}

module_init(dongtian_init);
module_exit(dongtian_exit);

MODULE_DESCRIPTION("Dongtian single-hart CVM control driver");
MODULE_AUTHOR("Dongtian project");
MODULE_LICENSE("GPL");
