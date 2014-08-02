#include "test.h"

static void
test_fixed_truncated(void *arg)
{
  uint8_t buf[128] = { 0 };
  fixed_t *out = NULL;
  unsigned i;
  (void)arg;

  for (i = 0; i < 66; ++i) {
    tt_int_op(-2, ==, fixed_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(66, ==, fixed_parse(&out, buf, 66));

  /* Truncated on encode */
  for (i = 0; i < 66; ++i) {
    tt_int_op(-2, ==, fixed_encode(buf, i, out));
  }

  /* Success */
  tt_int_op(66, ==, fixed_encode(buf, 66, out));
  tt_int_op(66, ==, fixed_encode(buf, sizeof(buf), out));

 end:
  fixed_free(out);
}

static void
test_fixed_invalid(void *arg)
{
  uint8_t buf[128];
  fixed_t *fixed=NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, fixed_encode(buf, sizeof(buf), NULL));

  /* The structs in the array need to be set. */
  fixed = fixed_new();
  tt_int_op(-1, ==, fixed_encode(buf, sizeof(buf), fixed));
  fixed->nums[0] = numbers_new();
  tt_int_op(-1, ==, fixed_encode(buf, sizeof(buf), fixed));

  /* Okay now. */
  fixed->nums[1] = numbers_new();
  tt_int_op(66, ==, fixed_encode(buf, sizeof(buf), fixed));

  /* Make the check fail. */
  fixed->nums[1]->i32 = 0xbadbeef;
  tt_int_op(-1, ==, fixed_encode(buf, sizeof(buf), fixed));

 end:
  fixed_free(fixed);
}

static void
test_fixed_encdec(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128] = {0};
  fixed_t *out = NULL;
  (void)arg;

  inp = ux( "01020408"
            "0010""0020""0040""0080""0100""0200"
            "00000400""00000800""00001000"
            "0000000000002000"
            "01" "0002" "00000003"
            "0000000000000004"
            "50" "6000" "70000000"
            "8000000000000000" );

  tt_int_op(66, ==, fixed_parse(&out, inp, 66));
  tt_int_op(out->a8[0], ==, 1);
  tt_int_op(out->a8[1], ==, 2);
  tt_int_op(out->a8[2], ==, 4);
  tt_int_op(out->a8[3], ==, 8);
  tt_int_op(out->a16[0], ==, 16);
  tt_int_op(out->a16[1], ==, 32);
  tt_int_op(out->a16[2], ==, 64);
  tt_int_op(out->a16[3], ==, 128);
  tt_int_op(out->a16[4], ==, 256);
  tt_int_op(out->a16[5], ==, 512);
  tt_int_op(out->a32[0], ==, 1024);
  tt_int_op(out->a32[1], ==, 2048);
  tt_int_op(out->a32[2], ==, 4096);
  tt_assert(out->a64[0] == 8192);
  tt_int_op(out->nums[0]->i8, ==, 1);
  tt_int_op(out->nums[0]->i16, ==, 2);
  tt_int_op(out->nums[0]->i32, ==, 3);
  tt_assert(out->nums[0]->i64 == 4);
  tt_int_op(out->nums[1]->i8, ==, 0x50);
  tt_int_op(out->nums[1]->i16, ==, 0x6000);
  tt_int_op(out->nums[1]->i32, ==, 0x70000000);
  tt_assert(out->nums[1]->i64 == ((uint64_t)1)<<63 );

  tt_int_op(66, ==, fixed_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, 66);

  fixed_free(out); out = NULL;

 end:
  fixed_free(out);
}

struct testcase_t fixedarray_tests[] = {
  { "truncated", test_fixed_truncated, 0, NULL, NULL },
  { "invalid", test_fixed_invalid, 0, NULL, NULL },
  { "encode-decode", test_fixed_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
