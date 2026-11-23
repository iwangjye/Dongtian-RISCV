#include <stddef.h>
void *memcpy(void *d, const void *s, size_t n) {
  unsigned char *x = d;
  const unsigned char *y = s;
  while (n--)
    *x++ = *y++;
  return d;
}
void *memset(void *d, int c, size_t n) {
  unsigned char *x = d;
  while (n--)
    *x++ = (unsigned char)c;
  return d;
}
