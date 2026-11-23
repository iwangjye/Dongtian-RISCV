/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Dongtian contributors.
 * Local experimental SBI extension for a controlled one-hart HS handoff.
 */
#include <libfdt.h>
#include <sbi/sbi_scratch.h>
#include <sbi/riscv_asm.h>
#include <sbi/sbi_console.h>
#include <sbi/sbi_ecall.h>
#include <sbi/sbi_error.h>
#include <sbi/sbi_string.h>
#include <sbi/sbi_trap.h>

#define DT_EXT 0x0800d07aUL
#define DT_ENTRY 0x80100000UL
#define DT_HANDOFF 0x801f0000UL
struct dt_context {
    unsigned long x[32];
    unsigned long pc, vsstatus, vsatp, vstvec, vsscratch, vsie;
    unsigned long vsepc, vscause, vstval, return_status, return_hstatus, hvip;
};
struct dt_handoff {
    struct dt_context context;
    unsigned long timer_deadline;
    unsigned long timer_pending;
};
_Static_assert(sizeof(struct dt_context) == 352, "RV64 context layout");
static bool handed_off;

static int dt_handle(unsigned long extid, unsigned long fid,
                     struct sbi_trap_regs *regs,
                     struct sbi_ecall_return *out)
{
    struct dt_handoff *h = (void *)DT_HANDOFF;
    struct dt_context *c = &h->context;
    unsigned long mstatus = regs->mstatus;
    (void)extid;
    if (fid == 0 || fid == 3) { out->value = 0; return 0; }
    if (fid != 1) return SBI_ENOTSUPP;
    if (handed_off || (mstatus & MSTATUS_MPV) ||
        (mstatus & MSTATUS_MPP) != (PRV_S << MSTATUS_MPP_SHIFT))
        return SBI_EDENIED;
    sbi_memset(h, 0, sizeof(*h));
    sbi_memcpy(c->x, regs, sizeof(c->x));
    c->x[0] = 0;
    c->x[10] = 0;
    c->x[11] = 0;
    c->pc = regs->mepc + 4;
    c->vsstatus = csr_read(CSR_SSTATUS);
    c->vsatp = csr_read(CSR_SATP);
    c->vstvec = csr_read(CSR_STVEC);
    c->vsscratch = csr_read(CSR_SSCRATCH);
    c->vsie = csr_read(CSR_SIE);
    c->vsepc = csr_read(CSR_SEPC);
    c->vscause = csr_read(CSR_SCAUSE);
    c->vstval = csr_read(CSR_STVAL);
    c->return_status = c->vsstatus | (1UL << 8);
    c->return_hstatus = (2UL << 32) | (1UL << 7) | (1UL << 8);
    h->timer_deadline = *(volatile unsigned long *)0x2004000UL;
    h->timer_pending = !!(csr_read(CSR_SIP) & (1UL << 5));
    handed_off = true;
    csr_write(CSR_SATP, 0);
    __asm__ volatile("sfence.vma" ::: "memory");
    regs->mepc = DT_ENTRY;
    regs->a0 = DT_HANDOFF;
    regs->mstatus = (mstatus & ~(MSTATUS_MPV | MSTATUS_MPP | MSTATUS_MPRV)) |
                     (PRV_S << MSTATUS_MPP_SHIFT);
    out->skip_regs_update = true;
    sbi_printf("[Dongtian/OpenSBI] handing native HS Linux to HS monitor\n");
    return 0;
}
struct sbi_ecall_extension ecall_dongtian;
static int dt_register(void)
{
    if (!misa_extension('H')) return 0;
    /* The initial FDT lets OpenSBI discover its M-mode devices. Hide their
     * Linux platform drivers in the next-stage copy: Linux must use SBI
     * for timers/reset both before and after the controlled handoff. */
    void *fdt = (void *)sbi_scratch_thishart_ptr()->next_arg1;
    static const char *paths[] = { "/poweroff", "/reboot",
                                  "/soc/clint@2000000", "/soc/test@100000" };
    unsigned int i;
    if (fdt_check_header(fdt) ||
        fdt_open_into(fdt, fdt, fdt_totalsize(fdt) + 256)) return SBI_EINVAL;
    for (i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        int node = fdt_path_offset(fdt, paths[i]);
        if (node < 0 || fdt_setprop_string(fdt, node, "status", "disabled"))
            return SBI_EINVAL;
    }
    return sbi_ecall_register_extension(&ecall_dongtian);
}
struct sbi_ecall_extension ecall_dongtian = {
    .name = "dt",
    .extid_start = DT_EXT,
    .extid_end = DT_EXT,
    .experimental = true,
    .register_extensions = dt_register,
    .handle = dt_handle,
};
