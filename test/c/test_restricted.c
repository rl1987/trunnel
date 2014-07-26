#include "test.h"

static void
test_rst_truncated(void *arg)
{
  const uint8_t *buf = ux("00000001""00000001""00000002");
  uint8_t buf2[12];
  restricted_t *out = NULL;
  unsigned i;
  (void)arg;

  /* Truncated on parse */
  for (i = 0; i < 12; ++i) {
    tt_int_op(-2, ==, restricted_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(12, ==, restricted_parse(&out, buf, 12));

  /* Truncated on encode */
  for (i = 0; i < 12; ++i) {
    tt_int_op(-2, ==, restricted_encode(buf2, i, out));
  }

  /* Success */
  tt_int_op(12, ==, restricted_encode(buf2, 12, out));
  tt_mem_op(buf, ==, buf2, 12);

 end:
  restricted_free(out);
}

static void
test_rst_invalid(void *arg)
{
  uint8_t buf[16];
  restricted_t *rst = NULL;
  (void)arg;

  /* Can't parse */
  tt_int_op(-1, ==, restricted_parse(&rst,
                                     ux("00000101""00000001""00000002"),12));
  tt_int_op(-1, ==, restricted_parse(&rst,
                                     ux("00000001""00000101""00000002"),12));
  tt_int_op(-1, ==, restricted_parse(&rst,
                                     ux("00000001""00000001""0000000A"),12));

  /* Can't encode */
  tt_int_op(-1, ==, restricted_encode(buf, 16, NULL));

  rst = restricted_new();
  rst->i1 = 100;
  rst->i2 = 100;
  rst->i3 = 100;
  tt_int_op(-1, ==, restricted_encode(buf, 16, rst));
  rst->i1 = 1;
  tt_int_op(-1, ==, restricted_encode(buf, 16, rst));
  rst->i2 = 1;
  tt_int_op(-1, ==, restricted_encode(buf, 16, rst));
  rst->i3 = 1;
  tt_int_op(12, ==, restricted_encode(buf, 16, rst));

 end:
  restricted_free(rst);
}

static void
test_rst_encdec(void *arg)
{
  const uint8_t *inp;
  uint8_t buf2[16] = { 0 };
  restricted_t *out = NULL;
  (void)arg;

  inp = ux("00000001""00000005""00000003");
  tt_int_op(12, ==, restricted_parse(&out, inp, 12));
  tt_ptr_op(out, !=, 0);
  tt_uint_op(out->i1, ==, 1);
  tt_uint_op(out->i2, ==, 5);
  tt_uint_op(out->i3, ==, 3);
  tt_int_op(12, ==, restricted_encode(buf2, 16, out));
  tt_mem_op(inp, ==, buf2, 12);
  restricted_free(out); out = NULL;

  inp = ux("00000001""0000000A""00000002");
  tt_int_op(12, ==, restricted_parse(&out, inp, 12));
  tt_ptr_op(out, !=, 0);
  tt_uint_op(out->i1, ==, 1);
  tt_uint_op(out->i2, ==, 10);
  tt_uint_op(out->i3, ==, 2);
  tt_int_op(12, ==, restricted_encode(buf2, 16, out));
  tt_mem_op(inp, ==, buf2, 12);
  restricted_free(out); out = NULL;

 end:
  restricted_free(out);
}


struct testcase_t restricted_tests[] = {
  { "truncated", test_rst_truncated, 0, NULL, NULL },
  { "invalid", test_rst_invalid, 0, NULL, NULL },
  { "encode-decode", test_rst_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
