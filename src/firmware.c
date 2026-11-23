typedef unsigned long u64;
#define CSR(n)                                                                 \
  ({                                                                           \
    u64 x;                                                                     \
    __asm__ volatile("csrr %0," #n : "=r"(x));                                 \
    x;                                                                         \
  })
#define SET(n, x) __asm__ volatile("csrw " #n ",%0" ::"r"((u64)(x)) : "memory")
struct frame {
  u64 x[32], pc, vsstatus, vsatp, vstvec, vsscratch, vsie, vsepc, vscause,
      vstval, return_status, return_hstatus, hvip, mstatus;
};
extern void monitor_main(void *);
static void putc(int c) {
  volatile unsigned char *u = (void *)0x10000000;
  while (!(u[5] & 32)) {
  }
  u[0] = c;
}
static void timer(u64 t) {
  *(volatile u64 *)0x2004000 = t;
  __asm__ volatile("csrc mip,%0" ::"r"(32UL));
}
static u64 translate(u64 va, u64 satp) {
  if (!(satp >> 60))
    return va;
  u64 mode = satp >> 60;
  if (mode < 8 || mode > 10)
    return ~0UL;
  u64 table = (satp & ((1UL << 44) - 1)) << 12;
  for (int level = (int)mode - 6; level >= 0; --level) {
    u64 pte = *(volatile u64 *)(table + ((va >> (12 + 9 * level)) & 511) * 8);
    if (!(pte & 1))
      return ~0UL;
    if (pte & 14) {
      u64 bits = 12 + 9 * level;
      return ((pte >> 10) << 12 & ~((1UL << bits) - 1)) |
             (va & ((1UL << bits) - 1));
    }
    table = (pte >> 10) << 12;
  }
  return ~0UL;
}
int firmware_trap(struct frame *f) {
  u64 cause = CSR(mcause), eid = f->x[17], fid = f->x[16];
  if (cause == (1UL << 63 | 7)) {
    timer(~0UL);
    __asm__ volatile("csrs mip,%0" ::"r"(32UL));
    return 0;
  }
  if (cause == 7 && translate(CSR(mtval), CSR(satp)) == 0x11000000) {
    f->pc += 4;
    f->vsstatus = CSR(sstatus);
    f->return_status = (f->vsstatus & ~0x100UL) |
                       (((f->mstatus >> 11) & 3) == 1 ? 0x100UL : 0);
    f->return_hstatus =
        (2UL << 32) | 128UL | ((((f->mstatus >> 11) & 3) == 1) ? 256UL : 0);
    f->hvip = 0;
    f->vsatp = CSR(satp);
    f->vstvec = CSR(stvec);
    f->vsscratch = CSR(sscratch);
    f->vsie = CSR(sie);
    f->vsepc = CSR(sepc);
    f->vscause = CSR(scause);
    f->vstval = CSR(stval);
    SET(satp, 0);
    __asm__ volatile("sfence.vma" ::: "memory");
    return 1;
  }
  if (cause == 9) {
    long error = 0;
    u64 value = 0;
    if (eid == 0 || eid == 0x54494d45)
      timer(f->x[10]);
    else if (eid == 1)
      putc(f->x[10]);
    else if (eid == 2) {
      volatile unsigned char *u = (void *)0x10000000;
      f->x[10] = (u[5] & 1) ? u[0] : ~0UL;
      f->pc += 4;
      return 0;
    } else if (eid == 0x10) {
      if (fid == 0)
        value = 0x2000000;
      else if (fid == 1)
        value = 0x4d494e;
      else if (fid == 2)
        value = 1;
      else if (fid == 3) {
        u64 q = f->x[10];
        value = q == 0x10 || q == 0x54494d45 || q == 0x53525354;
      } else if (fid >= 4 && fid <= 6)
        value = 0;
      else
        error = -2;
    } else if (eid == 8 || eid == 0x53525354) {
      *(volatile unsigned *)0x100000 = 0x5555;
      for (;;)
        __asm__ volatile("wfi");
    } else
      error = -2;
    f->x[10] = error;
    f->x[11] = value;
    f->pc += 4;
    return 0;
  }
  putc('M');
  putc('!');
  putc('0' + (cause & 15));
  putc('\n');
  *(volatile unsigned *)0x100000 = 0x13333;
  for (;;)
    __asm__ volatile("wfi");
}
