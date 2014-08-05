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
  tt_int_op(out->num1->i8, ==, 5);
  tt_int_op(out->num1->i16, ==, 4);
  tt_int_op(out->num1->i32, ==, 3);
  tt_int_op(out->num1->i64, ==, 2);
  tt_int_op(out->num2->i8, ==, 9);
  tt_int_op(out->num2->i16, ==, 8);
  tt_int_op(out->num2->i32, ==, 7);
  tt_int_op(out->num2->i64, ==, 6);
  tt_str_op(out->strs->f, ==, "picapica");
  tt_str_op(out->strs->nt, ==, "magpie");
  tt_int_op(out->res->i1, ==, 1);
  tt_int_op(out->res->i2, ==, 10);
  tt_int_op(out->res->i3, ==, 2);

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

  nest->num1 = numbers_new();
  nest->num2 = numbers_new();
  nest->strs = strings_new();
  nest->res = restricted_new();

  /* Number failures. */
  nest->num1->i32 = 0xbadbeef;
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));
  nest->num1->i32 = 0;
  nest->num2->i32 = 0xbadbeef;
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));
  nest->num2->i32 = 0;

  /* Strings fails */
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));

  /* Restricted fails */
  nest->strs->nt = strdup("xyz");
  tt_int_op(-1, ==, nested_encode(buf, 128, nest));

  nested_free(nest); nest = NULL;

 end:
  nested_free(nest);
}

static void
test_nest_accessors(void *arg)
{
  nested_t *nest = NULL, *nest2 = NULL;
  numbers_t *nums = NULL;
  strings_t *strs = NULL;
  restricted_t *rst = NULL;
  uint8_t buf[128];
  const uint8_t *inp;
  (void) arg;

  nest = nested_new();
  nums = numbers_new();
  tt_int_op(0, ==, nested_set_num1(nest, nums));
  tt_ptr_op(nums, ==, nested_get_num1(nest));
  nums = numbers_new();
  numbers_set_i32(nums, 64);
  tt_int_op(0, ==, nested_set_num2(nest, nums));
  tt_ptr_op(nums, ==, nested_get_num2(nest));
  nums = numbers_new();
  numbers_set_i8(nums, 64);
  tt_int_op(0, ==, nested_set_num1(nest, nums));
  tt_ptr_op(nums, ==, nested_get_num1(nest));
  nums = NULL;

  strs = strings_new();
  tt_int_op(0, ==, strings_set_nt(strs, "\xff\xff"));
  tt_int_op(0, ==, nested_set_strs(nest, strs));
  tt_ptr_op(strs, ==, nested_get_strs(nest));
  strs = NULL;

  rst = restricted_new();
  tt_int_op(0, ==, restricted_set_i1(rst, 1));
  tt_int_op(0, ==, restricted_set_i2(rst, 1));
  tt_int_op(0, ==, restricted_set_i3(rst, 1));
  tt_int_op(0, ==, nested_set_res(nest, rst));
  tt_ptr_op(rst, ==, nested_get_res(nest));
  rst = NULL;

  tt_int_op(55, ==, nested_encode(buf, sizeof(buf), nest));
  inp = ux("40" "0000" "00000000" "0000000000000000"
           "00" "0000" "00000040" "0000000000000000"
           "00000000000000000000" "FFFF00"
           "00000001" "00000001" "00000001");
  tt_mem_op(inp, ==, buf, 55);

  tt_int_op(55, ==, nested_parse(&nest2, buf, sizeof(buf)));

  tt_int_op(0, ==, nested_set_num2(nest, numbers_new()));
  tt_int_op(0, ==, nested_set_strs(nest, strings_new()));
  tt_int_op(0, ==, strings_set_nt(nested_get_strs(nest), "Trunnel"));
  tt_int_op(0, ==, nested_set_res(nest, restricted_new()));
  tt_int_op(0, ==, restricted_set_i1(nested_get_res(nest), 1));
  tt_int_op(0, ==, restricted_set_i2(nested_get_res(nest), 2));
  tt_int_op(0, ==, restricted_set_i3(nested_get_res(nest), 3));

  tt_int_op(60, ==, nested_encode(buf, sizeof(buf), nest));
  inp = ux("40" "0000" "00000000" "0000000000000000"
           "00" "0000" "00000000" "0000000000000000"
           "00000000000000000000" "5472756e6e656c00"
           "00000001" "00000002" "00000003");
  tt_mem_op(inp, ==, buf, 60);

  /* No way to get this set */
  nest->trunnel_error_code_ = 1;
  tt_int_op(-1, ==, nested_encode(buf, sizeof(buf), nest));
  nested_clear_errors(nest);
  tt_int_op(60, ==, nested_encode(buf, sizeof(buf), nest));
  tt_mem_op(inp, ==, buf, 60);

 end:
  strings_free(strs);
  numbers_free(nums);
  nested_free(nest);
  nested_free(nest2);
  restricted_free(rst);
}

struct testcase_t nested_tests[] = {
  { "parsing", test_nest_parsing, 0, NULL, NULL },
  { "invalid", test_nest_invalid, 0, NULL, NULL },
  { "accessors", test_nest_accessors, 0, NULL, NULL },
  END_OF_TESTCASES
};
