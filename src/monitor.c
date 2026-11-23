/* Standalone one-hart RV64 HS scheduler for a demoted Linux host and a Linux
 * CVM. Firmware occupies [0x80000000,0x80200000); not mapped to either VS
 * domain. Host RAM: [0x80200000,0xa0000000). Guest GPA [0x80000000,0x88000000)
 * maps to private physical [0xa0000000,0xa8000000). No shared RAM mappings.
 * UART and PLIC MMIO are shared for synchronous guest entry, not isolated.
 * No external project runtime modules. */
#include "monitor.h"
#define READ(c)                                                                \
  ({                                                                           \
    uint64_t v;                                                                \
    __asm__ volatile("csrr %0," #c : "=r"(v));                                 \
    v;                                                                         \
  })
#define WRITE(c, v)                                                            \
  __asm__ volatile("csrw " #c ",%0" ::"r"((uint64_t)(v)) : "memory")
#define VSTIP (1UL << 6)
#define VSIP (1UL << 2)
#define VSEIP (1UL << 10)
#define TICK 10000UL /* QEMU virt timebase 10MHz: one millisecond. */
static struct context domain[2];
static uint64_t roots[2][2048] __attribute__((aligned(16384)));
static uint64_t ram[2][512] __attribute__((aligned(4096)));
static uint64_t host_mmio[512] __attribute__((aligned(4096)));
static uint64_t guest_mmio[512] __attribute__((aligned(4096)));
static uint64_t deadlines[2] = {~0UL, ~0UL};
static unsigned active, timer_ticks, guest_started, guest_done;
static uint64_t pte(uint64_t pa, uint64_t f) { return ((pa >> 12) << 10) | f; }
static void putc(char c) {
  volatile unsigned char *u = (void *)0x10000000UL;
  while (!(u[5] & 32)) {
  }
  u[0] = c;
}
static void puts(const char *s) {
  while (*s)
    putc(*s++);
}
static void hex(uint64_t n) {
  for (int i = 60; i >= 0; i -= 4)
    putc("0123456789abcdef"[(n >> i) & 15]);
}
static void fatal(const char *why, struct context *c) {
  puts("[HS] FATAL ");
  puts(why);
  puts(" domain=");
  hex(active);
  puts(" cause=");
  hex(READ(scause));
  puts(" pc=");
  hex(c->pc);
  puts(" stval=");
  hex(READ(stval));
  puts(" htval=");
  hex(READ(htval));
  puts("\n");
  *(volatile unsigned *)0x100000 = 0x13333;
  for (;;)
    __asm__ volatile("wfi");
}
static struct {
  long error, value;
} sbi(uint64_t ext, uint64_t fid, uint64_t p0, uint64_t p1) {
  register uint64_t a0 __asm__("a0") = p0, a1 __asm__("a1") = p1;
  register uint64_t a6 __asm__("a6") = fid, a7 __asm__("a7") = ext;
  __asm__ volatile("ecall" : "+r"(a0), "+r"(a1) : "r"(a6), "r"(a7) : "memory");
  return (typeof(sbi(0, 0, 0, 0))){a0, a1};
}
static void arm_tick(void) { sbi(0x54494d45, 0, READ(time) + TICK, 0); }
static void sample_external(void) {
  /* HS SEIP remains disabled in sie: a level IRQ must not cause an HS storm.
   * The 1 ms timer polls physical PLIC output and drives the current VS IRQ.
   * UART/PLIC are shared and the host is suspended throughout guest entry. */
  domain[active].hvip =
      (domain[active].hvip & ~VSEIP) | ((READ(sip) & (1UL << 9)) ? VSEIP : 0);
}
static void configure(void) {
  sample_external();
  WRITE(satp, 0);
  WRITE(stvec, (uint64_t)hs_trap);
  WRITE(hgatp, (8UL << 60) | ((uint64_t)roots[active] >> 12));
  __asm__ volatile("hfence.gvma zero,zero; hfence.vvma zero,zero" ::: "memory");
  /* Ordinary exceptions go directly to VS, all SBI and guest faults stay HS. */
  WRITE(hedeleg, 0xb1ff);
  WRITE(hideleg, (1UL << 2) | (1UL << 6) | (1UL << 10));
  WRITE(hcounteren, 7);
  WRITE(scounteren, 7);
  WRITE(htimedelta, 0);
  WRITE(sie, (1UL << 5));
}
void monitor_main(const struct context *initial) {
  /* Parent firmware has already copied every S CSR to the VS namespace and
   * entered this function in HS with bare satp. */
  domain[0] = *initial;
  /* Carry the pre-demotion SBI timer deadline into the VS host. */
  deadlines[0] = *(volatile uint64_t *)0x2004000;
  if (READ(sip) & (1UL << 5))
    domain[0].hvip |= VSTIP;
  domain[0].return_status = (initial->return_status | (1UL << 5)) & ~(1UL << 1);
  domain[0].return_hstatus = initial->return_hstatus;
  /* Host identity map excludes firmware; only UART and PLIC MMIO are mapped. */
  roots[0][0] = pte((uint64_t)host_mmio, 1);
  host_mmio[0x10000000UL >> 21] = pte(0x10000000, 0xdf);
  for (unsigned i = 0x0c000000UL >> 21; i < 0x0c600000UL >> 21; i++)
    host_mmio[i] = pte((uint64_t)i * 0x200000, 0xdf);
  roots[0][2] = pte((uint64_t)ram[0], 1);
  for (unsigned i = 1; i < 256; i++)
    ram[0][i] = pte(0x80000000UL + (uint64_t)i * 0x200000, 0xdf);
  roots[1][0] = pte((uint64_t)guest_mmio, 1);
  /* Shared NS16550 and the 6 MiB virt PLIC aperture. This local Linux boot
   * demonstration provides private RAM but explicitly not device isolation. */
  guest_mmio[0x10000000UL >> 21] = pte(0x10000000, 0xdf);
  for (uint64_t pa = 0x0c000000; pa < 0x0c600000; pa += 0x200000)
    guest_mmio[pa >> 21] = pte(pa, 0xdf);
  roots[1][2] = pte((uint64_t)ram[1], 1);
  for (unsigned i = 0; i < 64; i++)
    ram[1][i] = pte(0xa0000000UL + (uint64_t)i * 0x200000, 0xdf);
  domain[1].pc = 0x80200000;
  domain[1].x[10] = 0;
  domain[1].x[11] = 0x87000000;
  domain[1].vsstatus = (2UL << 32); /* UXL=64, interrupts initially disabled. */
  domain[1].return_status = (2UL << 32) | (1UL << 8) | (1UL << 5);
  domain[1].return_hstatus = (2UL << 32) | (1UL << 7) | (1UL << 8);
  puts("[HS] Linux host context captured; G-stage isolated guest configured\n");
  active = 0;
  configure();
  arm_tick();
  puts("[HS] demotion complete; resuming Linux host userspace\n");
  vs_restore(&domain[0]);
}
static int probe(uint64_t ext) {
  return ext == 0x10 || ext == 0x54494d45 || ext == 0x735049 ||
         ext == 0x52464e43 || ext == 0x48534d || ext == 0x53525354 ||
         ext == 0x4442434e;
}
static void handle_sbi(struct context *c) {
  uint64_t ext = c->x[17], fid = c->x[16], a0 = c->x[10], a1 = c->x[11];
  long err = 0, val = 0;
  c->pc += 4;
  if (ext == 0) {
    deadlines[active] = a0;
    c->hvip &= ~VSTIP;
    c->x[10] = 0;
    return;
  }
  if (ext == 1) {
    putc(a0);
    c->x[10] = 0;
    return;
  }
  if (ext == 2) {
    c->x[10] = (uint64_t)-1;
    return;
  }
  if (ext == 8) {
    puts("[HS] legacy guest shutdown\n");
    if (active) {
      active = 0;
      return;
    }
    sbi(0x53525354, 0, 0, 0);
  }
  switch (ext) {
  case 0x10:
    switch (fid) {
    case 0:
      val = 0x2000000;
      break;
    case 1:
      val = 0x4c43564d;
      break;
    case 2:
      val = 1;
      break;
    case 3:
      val = probe(a0);
      break;
    case 4:
    case 5:
    case 6:
      val = 0;
      break;
    default:
      err = -2;
    }
    break;
  case 0x54494d45:
    if (fid)
      err = -2;
    else {
      deadlines[active] = a0;
      c->hvip &= ~VSTIP;
    }
    break;
  case 0x735049:
    if (fid)
      err = -2;
    else if (a1 == ~0UL || a1 == 0)
      c->hvip |= VSIP;
    else
      err = -3;
    break;
  case 0x52464e43: /* A single virtual hart needs only local fences. */
    if (fid > 2)
      err = -2;
    else
      __asm__ volatile("fence.i; hfence.vvma zero,zero" ::: "memory");
    break;
  case 0x48534d:
    if (fid == 2)
      val = 0;
    else
      err = -3;
    break; /* hart 0 already started */
  case 0x4442434e:
    if (fid == 2) {
      putc(a0);
      break;
    }
    if (fid == 1) {
      val = 0;
      break;
    }
    if (fid != 0) {
      err = -2;
      break;
    }
    /* DBCN uses supervisor physical addresses, translated by G-stage only. */
    if (c->x[12] || a0 > 4096 || a1 < 0x80200000UL || a1 + a0 < a1 ||
        a1 + a0 > (active ? 0x88000000UL : 0xa0000000UL)) {
      err = -5;
      break;
    }
    {
      const char *buf = (void *)(a1 + (active ? 0x20000000UL : 0));
      for (uint64_t n = 0; n < a0; n++)
        putc(buf[n]);
      val = a0;
    }
    break;
  case 0x53525354:
    if (fid || a0 > 1) {
      err = -2;
      break;
    }
    if (active) {
      puts("[HS] CVM requested shutdown; resuming demoted Linux host\n");
      deadlines[1] = ~0UL;
      guest_done = 1;
      active = 0;
    } else if (guest_started && guest_done) {
      puts("MINIMAL_LINUX_CVM_PASS\n");
      sbi(ext, fid, a0, a1);
    } else {
      puts("MINIMAL_LINUX_CVM_FAIL\n");
      *(volatile unsigned *)0x100000 = 0x13333;
    }
    break;
  default:
    err = -2;
    break;
  }
  c->x[10] = err;
  c->x[11] = val;
}
struct context *monitor_trap(struct context *c) {
  uint64_t cause = READ(scause);
  if (!(READ(hstatus) & (1UL << 7)))
    fatal("unexpected HS trap", c);
  if (cause == (1UL << 63 | 5UL)) {
    uint64_t now = READ(time);
    for (unsigned i = 0; i < 2; i++)
      if (now >= deadlines[i])
        domain[i].hvip |= VSTIP;
    ++timer_ticks;
    arm_tick();
  } else if (cause == 23 && !active &&
             ((READ(htval) << 2) | (READ(stval) & 3)) == 0x11000000) {
    c->pc += 4;
    guest_started = 1;
    active = 1;
    puts("[HS] entering independent Linux CVM at GPA 0x80200000\n");
  } else if (cause == 10)
    handle_sbi(c);
  else if (cause == 22) { /* Linux idle wfi traps with VTW only when enabled. */
    uint64_t ins = READ(htinst);
    if (ins == 0x10500073) {
      c->pc += 4;
    } else
      fatal("virtual instruction", c);
  } else
    fatal("unexpected VS trap", c);
  configure();
  return &domain[active];
}
