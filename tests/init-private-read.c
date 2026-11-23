void *memset(void *p, int c, unsigned long n) {
  volatile char *q = p;
  while (n--)
    *q++ = c;
  return p;
}
typedef unsigned long U;
static long sc(long n, long x, long y, long z, long p, long q, long r) {
  register long a0 __asm__("a0") = x;
  register long a1 __asm__("a1") = y;
  register long a2 __asm__("a2") = z;
  register long a3 __asm__("a3") = p;
  register long a4 __asm__("a4") = q;
  register long a5 __asm__("a5") = r;
  register long a7 __asm__("a7") = n;
  __asm__ volatile("ecall"
                   : "+r"(a0)
                   : "r"(a1), "r"(a2), "r"(a3), "r"(a4), "r"(a5), "r"(a7)
                   : "memory");
  return a0;
}
static void out(char *s) {
  U n = 0;
  while (s[n])
    n++;
  sc(64, 1, (long)s, n, 0, 0, 0);
  sc(29, 1, 0x5409, 1, 0, 0, 0);
}
static void num(long v) {
  char s[32];
  int i = 30;
  s[31] = 0;
  s[i--] = '\n';
  do {
    s[i--] = '0' + v % 10;
    v /= 10;
  } while (v);
  out(s + i + 1);
}
void _start(void) {
  char u[390] = {0};
  sc(160, (long)u, 0, 0, 0, 0, 0);
  out("LINUX_USERSPACE_ROLE=" ROLE "\n");
  out("uname.sysname=");
  out(u);
  out("\nuname.release=");
  out(u + 130);
  out("\nuname.machine=");
  out(u + 260);
  out("\ngetpid=");
  num(sc(172, 0, 0, 0, 0, 0, 0));
#ifdef HOST
  sc(34, -100, (long)"/dev", 0755, 0, 0, 0);
  sc(40, (long)"devtmpfs", (long)"/dev", (long)"devtmpfs", 0, 0, 0);
  long fd = sc(56, -100, (long)"/dev/mem", 2 | 0x101000, 0, 0, 0);
  out("host.devmem.fd=");
  num(fd);
  if (fd >= 0) {
    long p = sc(222, 0, 4096, 3, 1, fd, 0x11000000);
    if ((U)p < (U)-4095) {
      out("HOST_REQUEST_DYNAMIC_HS_TO_VS\n");
      __asm__ volatile(
          ".option push\n.option norvc\nli t0, 1\nsw t0, 0(%0)\n.option pop" ::
              "r"(p)
          : "t0", "memory");
      out("HOST_AFTER_DEMOTION\n");
      long delay[2] = {0, 10000000};
      long sleep_rc = sc(101, (long)delay, 0, 0, 0, 0, 0);
      if (sleep_rc == 0)
        out("HOST_AFTER_DEMOTION_TIME_OK\n");
      else
        out("HOST_AFTER_DEMOTION_TIME_FAIL\n");
      out("HOST_REQUEST_CVM_LINUX\n");
      __asm__ volatile(
          ".option push\n.option norvc\nli t0, 2\nsw t0, 0(%0)\n.option pop" ::
              "r"(p)
          : "t0", "memory");
      out("HOST_AFTER_CVM_RETURN\n");
      long private_map = sc(222, 0, 4096, 1, 1, fd, 0xa0200000UL);
      if ((U)private_map >= (U)-4095) {
        out("HOST_PRIVATE_MAP_DENIED_NOT_ISOLATION_EVIDENCE\n");
        num(-private_map);
      } else {
        out("HOST_PRIVATE_READ_ATTEMPT\n");
        long private_value;
        __asm__ volatile(
            ".option push\n.option norvc\nld %0, 0(%1)\n.option pop"
            : "=r"(private_value)
            : "r"(private_map)
            : "memory");
        out("PRIVATE_READ_UNEXPECTED_RETURN\nHOST_PRIVATE_READ_FAIL\n");
        num(private_value & 0xffff);
      }
    } else {
      out("HOST_INIT_FAIL_MMAP\n");
      num(-p);
    }
  } else {
    out("HOST_INIT_FAIL_DEVMEM\n");
  }
#else
  out("CVM_LINUX_USERSPACE_OK\n");
#endif
  out("LINUX_REQUEST_POWER_OFF\n");
  sc(142, 0xfee1dead, 672274793, 0x4321fedc, 0, 0, 0);
  for (;;) {
  }
}
