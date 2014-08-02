#include "test.h"

struct testgroup_t test_groups[] = {
  { "numbers/", numbers_tests },
  { "restricted/", restricted_tests },
  { "strings/", strings_tests },
  { "uses-eos/", eos_tests },
  { "extends/", extends_tests },
  { "nested/", nested_tests },
  { "fixed-array/", fixedarray_tests },
  { "var-array/", vararray_tests },
  { "union-nolen/", union_nolen_tests },
  { "union-withlen/", union_withlen_tests },
  { "union-defaults/", union_defaults_tests },
  { "repeats-to-end/", repeats_tests },
  END_OF_GROUPS,
};

int main(int argc, const char **argv)
{
  int r = tinytest_main(argc,argv,test_groups);
  ux(NULL); /* free buffer */
  return r;
}

ssize_t
unhex(uint8_t *out, size_t outlen, const char *in)
{
  unsigned x;
  int n;
  ssize_t n_out = 0;
  if (outlen < strlen(in)/2)
    return -1;

  while (*in) {
    if (in[1] == 0)
      return -2;
    n = sscanf(in,"%2x",&x);
    if (n == 0)
      return -3;
    *out++ = (uint8_t) x;
    ++n_out;
    in += 2;
  }
  return n_out;
}

const uint8_t *
ux(const char *in)
{
  static uint8_t *buf = NULL;
  ssize_t sz;

  if (buf)
    free(buf);

  if (! in)
    return NULL;

  sz = strlen(in)+1; /* overkill */
  buf = malloc(sz);
  sz = unhex(buf, sz, in);
  assert(sz >= 0);
  return buf;
}
