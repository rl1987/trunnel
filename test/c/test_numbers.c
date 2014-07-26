#include "test.h"

static void
test_num_truncated(void *arg)
{
  uint8_t buf[16] = { 0 };
  numbers_t *out = NULL;
  unsigned i;
  (void)arg;

  /* Truncated on parse */
  for (i = 0; i < 15; ++i) {
    tt_int_op(-2, ==, numbers_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }
  tt_int_op(-1, ==, numbers_parse(&out, buf, 16));
  tt_ptr_op(NULL, ==, out);

  /* Success */
  tt_int_op(15, ==, numbers_parse(&out, buf, 15));

  /* Truncated on encode */
  for (i = 0; i < 15; ++i) {
    tt_int_op(-2, ==, numbers_encode(buf, i, out));
  }

  /* Success */
  tt_int_op(15, ==, numbers_parse(&out, buf, 15));

 end:
  numbers_free(out);
}

static void
test_num_invalid(void *arg)
{
  uint8_t buf[16];
  (void)arg;

  tt_int_op(-1, ==, numbers_encode(buf, 16, NULL));
 end:
  ;
}

static void
test_num_encdec(void *arg)
{
  uint8_t buf[16] = { 0 };
  uint8_t buf2[16] = { 0 };
  numbers_t *out = NULL;
  (void)arg;

  tt_int_op(15, ==, numbers_parse(&out, buf, 15));
  tt_ptr_op(out, !=, 0);
  tt_uint_op(out->i8, ==, 0);
  tt_uint_op(out->i16, ==, 0);
  tt_uint_op(out->i32, ==, 0);
  tt_uint_op(out->i64, ==, 0);
  tt_int_op(15, ==, numbers_encode(buf2, 16, out));
  tt_mem_op(buf, ==, buf2, 15);

  numbers_free(out); out = NULL;

  tt_int_op(15, ==, unhex(buf, sizeof(buf),
                          "05" "0004" "00000003" "00000000""00000002"));
  tt_int_op(15, ==, numbers_parse(&out, buf, 15));
  tt_ptr_op(out, !=, 0);
  tt_uint_op(out->i8, ==, 5);
  tt_uint_op(out->i16, ==, 4);
  tt_uint_op(out->i32, ==, 3);
  tt_assert(out->i64 == 2);
  tt_int_op(15, ==, numbers_encode(buf2, 16, out));
  tt_mem_op(buf, ==, buf2, 15);

  tt_int_op(15, ==, unhex(buf, sizeof(buf),
                          "12" "3456" "789abcde" "01234567""89abcdef"));
  tt_int_op(15, ==, numbers_parse(&out, buf, 15));
  tt_ptr_op(out, !=, 0);
  tt_uint_op(out->i8, ==, 18);
  tt_uint_op(out->i16, ==, 0x3456);
  tt_uint_op(out->i32, ==, 0x789abcde);
  tt_uint_op((out->i64 >>32), ==, 0x01234567);
  tt_uint_op((uint32_t)out->i64, ==, 0x089abcdef);
  tt_int_op(15, ==, numbers_encode(buf2, 16, out));
  tt_mem_op(buf, ==, buf2, 15);

  tt_int_op(15, ==, unhex(buf, sizeof(buf),
                          "ff" "ffff" "ffffffff" "ffffffffffffffff"));
  tt_int_op(15, ==, numbers_parse(&out, buf, 15));
  tt_ptr_op(out, !=, 0);
  tt_uint_op(out->i8, ==, 0xff);
  tt_uint_op(out->i16, ==, 0xffff);
  tt_uint_op(out->i32, ==, 0xffffffff);
  tt_assert(out->i64 == (uint64_t)-1);
  tt_int_op(15, ==, numbers_encode(buf2, 16, out));
  tt_mem_op(buf, ==, buf2, 15);

 end:
  numbers_free(out);
}


struct testcase_t numbers_tests[] = {
  { "truncated", test_num_truncated, 0, NULL, NULL },
  { "invalid", test_num_invalid, 0, NULL, NULL },
  { "encode-decode", test_num_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
