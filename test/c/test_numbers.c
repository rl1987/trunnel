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

  /* Success */
  tt_int_op(15, ==, numbers_parse(&out, buf, 15));

  /* Truncated on encode */
  for (i = 0; i < 15; ++i) {
    tt_int_op(-2, ==, numbers_encode(buf, i, out));
  }

  /* Success */
  tt_int_op(15, ==, numbers_encode(buf, 15, out));

 end:
  numbers_free(out);
}

static void
test_num_invalid(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[16];
  numbers_t *numbers = NULL;
  (void)arg;

  tt_int_op(-1, ==, numbers_encode(buf, 16, NULL));

  numbers = numbers_new();
  numbers->i32 = 0xbadbeef;
  tt_int_op(-1, ==, numbers_encode(buf, 16, numbers));
  numbers->i32 = 0x0;
  tt_int_op(15, ==, numbers_encode(buf, 16, numbers));
  numbers_free(numbers); numbers = NULL;

  inp = ux("05" "0004" "0badbeef" "00000000""00000002");
  tt_int_op(-1, ==, numbers_parse(&numbers, inp, 15));

 end:
  numbers_free(numbers);
}

static void
test_num_encdec(void *arg)
{
  uint8_t buf[16] = { 0 };
  uint8_t buf2[16] = { 0 };
  numbers_t *out = NULL;
  (void)arg;

  tt_int_op(15, ==, numbers_parse(&out, buf, 16));
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
  numbers_free(out); out = NULL;

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
  numbers_free(out); out = NULL;

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

static void
test_num_accessors(void *arg)
{
  uint8_t buf[15];
  const uint8_t *inp;
  numbers_t *num = NULL, *num2 = NULL;
  (void)arg;

  num = numbers_new();
  tt_int_op(0, ==, numbers_get_i8(num));
  tt_int_op(0, ==, numbers_get_i16(num));
  tt_int_op(0, ==, numbers_get_i32(num));
  tt_assert(0  ==  numbers_get_i64(num));

  tt_int_op(0, ==, numbers_set_i8(num, 255));
  tt_int_op(0, ==, numbers_set_i16(num, 257));
  tt_int_op(0, ==, numbers_set_i32(num, 258));
  tt_assert(0  ==  numbers_set_i64(num, 259));

  tt_int_op(15, ==, numbers_encode(buf, sizeof(buf), num));
  inp = ux("ff" "0101" "00000102" "00000000" "00000103");
  tt_mem_op(buf, ==, inp, 15);

  tt_int_op(15, ==, numbers_parse(&num2, buf, 15));
  tt_int_op(255, ==, numbers_get_i8(num));
  tt_int_op(257, ==, numbers_get_i16(num));
  tt_int_op(258, ==, numbers_get_i32(num));
  tt_assert(259  ==  numbers_get_i64(num));

  tt_int_op(255, ==, numbers_get_i8(num2));
  tt_int_op(257, ==, numbers_get_i16(num2));
  tt_int_op(258, ==, numbers_get_i32(num2));
  tt_assert(259  ==  numbers_get_i64(num2));

  tt_int_op(-1, ==, numbers_set_i32(num, 0xbadbeef));
  tt_int_op(0, ==, numbers_set_i32(num, 258));
  tt_int_op(-1, ==, numbers_encode(buf, sizeof(buf), num));
  tt_int_op(1, ==, numbers_clear_errors(num));
  tt_int_op(15, ==, numbers_encode(buf, sizeof(buf), num));
  tt_mem_op(buf, ==, inp, 15);

 end:
  numbers_free(num);
  numbers_free(num2);
}

static void
test_num_allocfail(void *arg)
{
  numbers_t *num = NULL;
  const uint8_t *inp;
  (void) arg;
#ifdef ALLOCFAIL
  set_alloc_fail(1);
  inp = ux("ff" "0101" "00000102" "00000000" "00000103");
  tt_int_op(-1, ==, numbers_parse(&num, inp, 15));
  tt_ptr_op(num, ==, NULL);
#else
  (void) inp;
  tt_skip();
#endif
 end:
  numbers_free(num);
}

struct testcase_t numbers_tests[] = {
  { "truncated", test_num_truncated, 0, NULL, NULL },
  { "invalid", test_num_invalid, 0, NULL, NULL },
  { "encode-decode", test_num_encdec, 0, NULL, NULL },
  { "accessors", test_num_accessors, 0, NULL, NULL },
  { "allocfail", test_num_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
