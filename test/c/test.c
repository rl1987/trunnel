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
  END_OF_GROUPS,
};

int main(int argc, const char **argv)
{
  return tinytest_main(argc,argv,test_groups);
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
  static uint8_t buf[1024];
  ssize_t sz;

  sz = unhex(buf, sizeof(buf), in);
  assert(sz >= 0);
  return buf;
}
