#include "test.h"

static void
test_eos_badlength(void *arg)
{
  uint8_t buf[12] = { 0 };
  uses_eos_t *out = NULL;
  unsigned i;
  (void)arg;

  /* Too short */
  for (i = 0; i < 4; ++i) {
    tt_int_op(-2, ==, uses_eos_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }
  /* Too long */
  for (i = 5; i <= 12; ++i) {
    tt_int_op(-1, ==, uses_eos_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(4, ==, uses_eos_parse(&out, buf, 4));

  /* Truncated on encode */
  for (i = 0; i < 4; ++i) {
    tt_int_op(-2, ==, uses_eos_encode(buf, i, out));
  }

  /* Success on encode: 1 */
  tt_int_op(4, ==, uses_eos_encode(buf, 4, out));
  tt_int_op(4, ==, uses_eos_encode(buf, 12, out));

 end:
  uses_eos_free(out);
}

static void
test_eos_invalid(void *arg)
{
  uint8_t buf[16];
  (void)arg;

  tt_int_op(-1, ==, uses_eos_encode(buf, 16, NULL));
 end:
  ;
}

static void
test_eos_encdec(void *arg)
{
  /* Not so necessary; we already tested integers. */
  const uint8_t *inp;
  uint8_t buf[32] = { 0 };
  uses_eos_t *out = NULL;
  (void)arg;

  inp = ux("01f40040");
  tt_int_op(4, ==, uses_eos_parse(&out, inp, 4));
  tt_ptr_op(out, !=, 0);
  tt_int_op(out->a, ==, 500);
  tt_int_op(out->b, ==, 64);
  tt_int_op(4, ==, uses_eos_encode(buf, 32, out));
  tt_mem_op(buf, ==, buf, 4);

  uses_eos_free(out); out = NULL;

 end:
  uses_eos_free(out);
}

struct testcase_t eos_tests[] = {
  { "bad-length", test_eos_badlength, 0, NULL, NULL },
  { "invalid", test_eos_invalid, 0, NULL, NULL },
  { "encode-decode", test_eos_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
