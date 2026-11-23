/* SPDX-License-Identifier: Apache-2.0 */
#include <stdint.h>
typedef unsigned long U;
static long sc(long n, long x, long y, long z, long p, long q, long r) {
 register long a0 __asm__("a0")=x, a1 __asm__("a1")=y, a2 __asm__("a2")=z;
 register long a3 __asm__("a3")=p, a4 __asm__("a4")=q, a5 __asm__("a5")=r;
 register long a7 __asm__("a7")=n;
 __asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a5),"r"(a7):"memory");
 return a0;
}
static void out(const char *s) { U n=0; while(s[n])++n;sc(64,1,(long)s,n,0,0,0);sc(29,1,0x5409,1,0,0,0); }
static __attribute__((unused)) int eq(const char *a,const char *b) { while(*a&&*a==*b){++a;++b;}return *a==*b; }
static void shutdown(void) {sc(142,0xfee1dead,672274793,0x4321fedc,0,0,0);for(;;){} }
static void fail(const char *s) {out("HOST_INIT_FAIL_");out(s);out("\n");shutdown();}
static int command(const char *name) {
 long pid=sc(220,17,0,0,0,0,0);
 if(pid==0) {
   char *args[]={(char *)"dongtian",(char *)name,0};char *env[]={0};
   sc(221,(long)"/sbin/dongtian",(long)args,(long)env,0,0,0);
   sc(93,127,0,0,0,0,0);for(;;){}
 }
 if(pid<0)return -1;
 int status=0;if(sc(260,pid,(long)&status,0,0,0,0)!=pid)return -1;
 return status;
}
static __attribute__((unused)) void automatic(void) {
 if(command("info"))fail("NATIVE_INFO");
 out("HOST_REQUEST_DYNAMIC_HS_TO_VS\n");
 if(command("demote"))fail("DRIVER_DEMOTE");
 out("HOST_AFTER_DEMOTION\n");
 long delay[2]={0,10000000};
 if(sc(101,(long)delay,0,0,0,0,0))fail("TIMER");
 out("HOST_AFTER_DEMOTION_TIME_OK\n");
 if(command("info"))fail("VIRTUAL_INFO");
 out("HOST_REQUEST_CVM_LINUX\n");
 if(command("run"))fail("DRIVER_RUN");
 out("HOST_AFTER_CVM_RETURN\n");
 if(command("info"))fail("FINAL_INFO");
#ifdef DONGTIAN_PRIVATE_READ
 long fd=sc(56,-100,(long)"/dev/mem",2|0x101000,0,0,0);
 if(fd<0)fail("PRIVATE_OPEN");
 long p=sc(222,0,4096,3,1,fd,0xa0200000);
 if((U)p>=(U)-4095)fail("PRIVATE_MAP_NOT_ISOLATION_EVIDENCE");
 out("HOST_PRIVATE_READ_ATTEMPT\n");
 U value;__asm__ volatile("ld %0,0(%1)":"=r"(value):"r"(p):"memory");
 (void)value;fail("PRIVATE_READ_UNEXPECTED_RETURN");
#endif
 out("DONGTIAN_DRIVER_WORKFLOW_PASS\n");
 shutdown();
}
#ifdef DONGTIAN_INTERACTIVE
static void interactive(void) {
 out("Dongtian control console: info, demote, run, quit\n");
 for(;;) {
   char line[64];U used=0;out("dongtian> ");
   while(used<sizeof(line)-1) {
     char c;long n=sc(63,0,(long)&c,1,0,0,0);if(n<0)fail("CONSOLE_READ");if(!n)continue;
     if(c=='\r'||c=='\n')break;line[used++]=c;
   }
   line[used]=0;
   if(eq(line,"quit"))shutdown();
   else if(eq(line,"info")||eq(line,"demote")||eq(line,"run")) {
     if(command(line))out("Command failed; check state with info.\n");
   } else if(used)out("Commands: info, demote, run, quit\n");
 }
}
#endif
void _start(void) {
 char u[390]={0};sc(160,(long)u,0,0,0,0,0);
 out("LINUX_USERSPACE_ROLE=host\nuname.sysname=");out(u);out("\n");
 if(sc(172,0,0,0,0,0,0)!=1)fail("NOT_PID1");out("getpid=1\n");
 sc(34,-100,(long)"/dev",0755,0,0,0);
 if(sc(40,(long)"devtmpfs",(long)"/dev",(long)"devtmpfs",0,0,0))fail("DEVTMPFS");
 long fd=sc(56,-100,(long)"/lib/modules/dongtian.ko",0,0,0,0);if(fd<0)fail("MODULE_OPEN");
 long rc=sc(273,fd,(long)"",0,0,0,0);sc(57,fd,0,0,0,0,0);
 if(rc)fail("FINIT_MODULE");out("DONGTIAN_KERNEL_DRIVER_LOADED\n");
#ifdef DONGTIAN_INTERACTIVE
 interactive();
#else
 automatic();
#endif
}
