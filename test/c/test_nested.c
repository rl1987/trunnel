#include "test.h"

static void
test_nest_parsing(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[80];
  nested_t *out = NULL;
  unsigned i;
  (void)arg;

  inp = ux("05" "0004" "00000003" "00000000""00000002"
           "09" "0008" "00000007" "00000000""00000006"
           "70696361706963610000""6d616770696500"
           "00000001""0000000A""00000002"
           "ffffffffffffffffff");

  /* Truncated on parse */
  for (i = 0; i < 59; ++i) {
    tt_int_op(-2, ==, nested_parse(&out, inp, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(59, ==, nested_parse(&out, inp, 59));
  tt_int_op(out->num1.i8, ==, 5);
  tt_int_op(out->num1.i16, ==, 4);
  tt_int_op(out->num1.i32, ==, 3);
  tt_int_op(out->num1.i64, ==, 2);
  tt_int_op(out->num2.i8, ==, 9);
  tt_int_op(out->num2.i16, ==, 8);
  tt_int_op(out->num2.i32, ==, 7);
  tt_int_op(out->num2.i64, ==, 6);
  tt_str_op(out->strs.f, ==, "picapica");
  tt_str_op(out->strs.nt, ==, "magpie");
  tt_int_op(out->res.i1, ==, 1);
  tt_int_op(out->res.i2, ==, 10);
  tt_int_op(out->res.i3, ==, 2);

  /* Truncated on encode */
  for (i = 0; i < 59; ++i) {
    tt_int_op(-2, ==, nested_encode(buf, i, out));
  }

  /* Success */
  memset(buf, 0x7f, sizeof(buf));
  tt_int_op(59, ==, nested_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, 59);

 end:
  nested_free(out);
}

static void
test_nest_invalid(void *arg)
{
  nested_t *nest = nested_new();
  uint8_t buf[128];
  (void)arg;

  /* NULL fails */
  tt_int_op(-1, ==, nested_encode(buf, 128, NULL));

  /* Number failures. */
  nest->num1.i32 = 0xbadbeef;
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));
  nest->num1.i32 = 0;
  nest->num2.i32 = 0xbadbeef;
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));
  nest->num2.i32 = 0;

  /* Strings fails */
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));

  /* Restricted fails */
  nest->strs.nt = strdup("xyz");
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));

  nested_free(nest); nest = NULL;

 end:
  nested_free(nest);
}

struct testcase_t nested_tests[] = {
  { "parsing", test_nest_parsing, 0, NULL, NULL },
  { "invalid", test_nest_invalid, 0, NULL, NULL },
  END_OF_TESTCASES
};
