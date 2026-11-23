#ifndef LINUX_CVM_MONITOR_H
#define LINUX_CVM_MONITOR_H
#include <stdint.h>
struct context {
  uint64_t x[32];
  uint64_t pc, vsstatus, vsatp, vstvec, vsscratch, vsie, vsepc, vscause, vstval;
  uint64_t return_status, return_hstatus, hvip;
};
void monitor_main(const struct context *) __attribute__((noreturn));
struct context *monitor_trap(struct context *);
void hs_trap(void);
void vs_restore(struct context *) __attribute__((noreturn));
#endif
