#include "test.h"

static void
test_extends_varlength(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[16] = { 0 };
  extends_t *out = NULL;
  unsigned i;
  (void)arg;

  /* Too short, or truncated during string. */
  inp = ux("74657374696e6700010203");
  for (i = 0; i < 8; ++i) {
    tt_int_op(-2, ==, extends_parse(&out, inp, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  for (i = 8; i <= 11; ++i) {
    tt_int_op(i, ==, extends_parse(&out, inp, i));
    tt_ptr_op(out, !=, NULL);
    tt_str_op(out->a, ==, "testing");
    tt_int_op(extends_get_remainder_len(out), ==, i-8);
    tt_mem_op(out->remainder.elts_, ==, inp+8, i-8);

    memset(buf, 0xff, sizeof(buf));
    tt_int_op(i, ==, extends_encode(buf, i, out));
    tt_mem_op(inp, ==, buf, i);
    extends_free(out); out = NULL;
  }

  tt_int_op(11, ==, extends_parse(&out, inp, 11));

  /* Truncated on encode */
  for (i = 0; i < 11; ++i) {
    tt_int_op(-2, ==, extends_encode(buf, i, out));
  }
  
 end:
  extends_free(out);
}

static void
test_extends_invalid(void *arg)
{
  uint8_t buf[16];
  extends_t extends;
  (void)arg;

  tt_int_op(-1, ==, extends_encode(buf, 16, NULL));

  /* no nul-terminated string */
  memset(&extends, 0, sizeof(extends));
  tt_int_op(-1, ==, extends_encode(buf, 16, &extends));
  /* Fill things in. */
  extends.a = strdup("XYZZY");
  extends.remainder.elts_ = calloc(3, 1);
  extends.remainder.allocated_ = extends.remainder.n_ = 3;
  tt_int_op(9, ==, extends_encode(buf, 16, &extends));

 end:
  if (extends.a) free(extends.a);
  if (extends.remainder.elts_) free(extends.remainder.elts_);
}

static void
test_extends_encdec(void *arg)
{
  uint8_t buf[32] = { 0 };
  uint8_t buf2[32] = { 0 };
  extends_t *out = NULL;
  (void)arg;

  memset(buf,0,32);
  memcpy(buf+1,"HelloWorld",10);
  tt_int_op(11, ==, extends_parse(&out, buf, 11));
  tt_ptr_op(out, !=, 0);
  tt_str_op(out->a, ==, "");
  tt_int_op(extends_get_remainder_len(out), ==, 10);
  tt_mem_op(out->remainder.elts_, ==, "HelloWorld", 10);
  tt_int_op(11, ==, extends_encode(buf2, 11, out));
  tt_mem_op(buf, ==, buf2, 11);
  extends_free(out); out = NULL;

 end:
  extends_free(out);
}

struct testcase_t extends_tests[] = {
  { "varlength", test_extends_varlength, 0, NULL, NULL },
  { "invalid", test_extends_invalid, 0, NULL, NULL },
  { "encode-decode", test_extends_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
