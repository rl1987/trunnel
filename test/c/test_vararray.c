#include "test.h"

static const char MINIMAL[] =
  "00""0000""00000000""0000000000000000";

static const char SOME_LEN1[] =
  "02""0000""00000000""0000000000000000"
  "5566""7788";

static const char SOME_LEN1_SOME_LEN2[] =
  "02""0002""00000000""0000000000000000"
  "5566""7788"
  "13371337"
  "01" "0002" "00000003"
  "0000000000000004"
  "05" "0006" "00000007"
  "0000000000000008";

static const char SOME_LEN3[] =
  "00""0000""00000004""0000000000000000"
  "00000606"
  "00000842"
  "00000867"
  "00005309";

static const char SOME_LEN4[] =
  "00""0000""00000000""0000000000000002"
  "00000606"
  "00000842"
  "00000867"
  "00005309";

static void
test_varlen_truncated(void *arg)
{
  const uint8_t *inp;
  const char **str;
  unsigned i;
  varlen_t *out = NULL;
  uint8_t buf[128];

  const char *strings[] = {
    MINIMAL,
    SOME_LEN1,
    SOME_LEN1_SOME_LEN2,
    SOME_LEN3,
    SOME_LEN4,
    NULL
  };

  (void) arg;
  for (str = &strings[0]; *str; ++str) {
    size_t outlen = strlen(*str) / 2;
    inp = ux(*str);
    /* Truncated on parse */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, varlen_parse(&out, inp, i));
      tt_ptr_op(NULL, ==, out);
    }
    /* Success */
    tt_int_op(outlen, ==, varlen_parse(&out, inp, outlen));

    /* Truncated on encode */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, varlen_encode(buf, i, out));
    }
    memset(buf, 0x7e, sizeof(buf));
    tt_int_op(outlen, ==, varlen_encode(buf, outlen, out));
    tt_mem_op(buf, ==, inp, outlen);
    varlen_free(out);
    out = NULL;
  }

 end:
  varlen_free(out);
}

static void
test_varlen_invalid(void *arg)
{
  uint8_t buf[128];
  varlen_t *varlen=NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), NULL));

  varlen = varlen_new();

  /* The array lengths need to really match. */
  varlen_setstr_str(varlen, "X");
  varlen->len1 = 1;
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len1 = 0;
  varlen->len2 = 1;
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len2 = 0;
  varlen->len3 = 1;
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len3 = 0;
  varlen->len4 = 1;
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len4 = 0;

  /* Structures need to be present and correct. */
  varlen->len1 = 1;
  varlen->len2 = 1;
  varlen->len3 = 1;
  varlen->len4 = 1;

  tt_int_op(0, ==, varlen_add_a8(varlen, 5));
  tt_int_op(0, ==, varlen_add_a16(varlen, 5));
  tt_int_op(0, ==, varlen_add_a32(varlen, 5));
  tt_int_op(0, ==, varlen_add_a64(varlen, 5));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));

  tt_int_op(0, ==, varlen_add_nums(varlen, NULL));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));

  /* Now make sure it's good */
  varlen_set_nums(varlen, 0, numbers_new());
  tt_int_op(-1, !=, varlen_encode(buf, sizeof(buf), varlen));

 end:
  varlen_free(varlen);
}

static void
test_varlen_encdec(void *arg)
{
  const uint8_t *inp;
  varlen_t *out = NULL;
  uint8_t buf[128];
  size_t len;
  uint64_t u64;
  numbers_t *nums;
  (void)arg;

  /* (We already round-tripped these in truncated.) */

  /* MINIMAL. */
  inp = ux(MINIMAL);
  len = strlen(MINIMAL)/2;
  tt_int_op(len, ==, varlen_parse(&out, inp, len));
  tt_int_op(0, ==, out->len1);
  tt_int_op(0, ==, out->len2);
  tt_int_op(0, ==, out->len3);
  tt_int_op(0, ==, out->len4);
  tt_str_op("", ==, varlen_getstr_str(out));
  tt_int_op(0, ==, varlen_get_a8_len(out));
  tt_int_op(0, ==, varlen_get_a16_len(out));
  tt_int_op(0, ==, varlen_get_a32_len(out));
  tt_int_op(0, ==, varlen_get_a64_len(out));
  tt_int_op(0, ==, varlen_get_nums_len(out));
  varlen_free(out); out = NULL;

  /* SOME_LEN1. */
  inp = ux(SOME_LEN1);
  len = strlen(SOME_LEN1)/2;
  tt_int_op(len, ==, varlen_parse(&out, inp, len));
  tt_int_op(2, ==, out->len1);
  tt_int_op(0, ==, out->len2);
  tt_int_op(0, ==, out->len3);
  tt_int_op(0, ==, out->len4);
  tt_str_op("Uf", ==, varlen_getstr_str(out));
  tt_int_op(2, ==, varlen_get_a8_len(out));
  tt_int_op(0, ==, varlen_get_a16_len(out));
  tt_int_op(0, ==, varlen_get_a32_len(out));
  tt_int_op(0, ==, varlen_get_a64_len(out));
  tt_int_op(0, ==, varlen_get_nums_len(out));
  tt_int_op(0x77, ==, varlen_get_a8(out, 0));
  tt_int_op(0x88, ==, varlen_get_a8(out, 1));
  varlen_free(out); out = NULL;

  /* SOME_LEN1_SOME_LEN2. */
  inp = ux(SOME_LEN1_SOME_LEN2);
  len = strlen(SOME_LEN1_SOME_LEN2)/2;
  tt_int_op(len, ==, varlen_parse(&out, inp, len));
  tt_int_op(2, ==, out->len1);
  tt_int_op(2, ==, out->len2);
  tt_int_op(0, ==, out->len3);
  tt_int_op(0, ==, out->len4);
  tt_str_op("Uf", ==, varlen_getstr_str(out));
  tt_int_op(2, ==, varlen_get_a8_len(out));
  tt_int_op(2, ==, varlen_get_a16_len(out));
  tt_int_op(0, ==, varlen_get_a32_len(out));
  tt_int_op(0, ==, varlen_get_a64_len(out));
  tt_int_op(2, ==, varlen_get_nums_len(out));
  tt_int_op(0x77, ==, varlen_get_a8(out, 0));
  tt_int_op(0x88, ==, varlen_get_a8(out, 1));
  tt_int_op(0x1337, ==, varlen_get_a16(out, 0));
  tt_int_op(0x1337, ==, varlen_get_a16(out, 1));
  tt_int_op(1, ==, varlen_get_nums(out, 0)->i8);
  tt_int_op(2, ==, varlen_get_nums(out, 0)->i16);
  tt_int_op(3, ==, varlen_get_nums(out, 0)->i32);
  tt_int_op(4, ==, varlen_get_nums(out, 0)->i64);
  tt_int_op(5, ==, varlen_get_nums(out, 1)->i8);
  tt_int_op(6, ==, varlen_get_nums(out, 1)->i16);
  tt_int_op(7, ==, varlen_get_nums(out, 1)->i32);
  tt_int_op(8, ==, varlen_get_nums(out, 1)->i64);
  varlen_free(out); out = NULL;

  /* SOME_LEN3. */
  inp = ux(SOME_LEN3);
  len = strlen(SOME_LEN3)/2;
  tt_int_op(len, ==, varlen_parse(&out, inp, len));
  tt_int_op(0, ==, out->len1);
  tt_int_op(0, ==, out->len2);
  tt_int_op(4, ==, out->len3);
  tt_int_op(0, ==, out->len4);
  tt_str_op("", ==, varlen_getstr_str(out));
  tt_int_op(0, ==, varlen_get_a8_len(out));
  tt_int_op(0, ==, varlen_get_a16_len(out));
  tt_int_op(4, ==, varlen_get_a32_len(out));
  tt_int_op(0, ==, varlen_get_a64_len(out));
  tt_int_op(0, ==, varlen_get_nums_len(out));
  tt_int_op(0x606, ==, varlen_get_a32(out, 0));
  tt_int_op(0x0842, ==, varlen_get_a32(out, 1));
  tt_int_op(0x867, ==, varlen_get_a32(out, 2));
  tt_int_op(0x5309, ==, varlen_get_a32(out, 3));
  varlen_free(out); out = NULL;

  /* SOME_LEN4. */
  inp = ux(SOME_LEN4);
  len = strlen(SOME_LEN4)/2;
  tt_int_op(len, ==, varlen_parse(&out, inp, len));
  tt_int_op(0, ==, out->len1);
  tt_int_op(0, ==, out->len2);
  tt_int_op(0, ==, out->len3);
  tt_int_op(2, ==, out->len4);
  tt_str_op("", ==, varlen_getstr_str(out));
  tt_int_op(0, ==, varlen_get_a8_len(out));
  tt_int_op(0, ==, varlen_get_a16_len(out));
  tt_int_op(0, ==, varlen_get_a32_len(out));
  tt_int_op(2, ==, varlen_get_a64_len(out));
  tt_int_op(0, ==, varlen_get_nums_len(out));
  u64 = varlen_get_a64(out, 0);
  tt_int_op(0x606, ==, (uint32_t)(u64 >> 32));
  tt_int_op(0x842, ==, (uint32_t)u64);
  u64 = varlen_get_a64(out, 1);
  tt_int_op(0x867, ==, (uint32_t)(u64 >> 32));
  tt_int_op(0x5309, ==, (uint32_t)u64);
  varlen_free(out); out = NULL;

  /* Now make a purely synthetic one, mainly to execute *_set() */
  out = varlen_new();
  out->len1 = 1;
  out->len2 = 1;
  out->len3 = 1;
  out->len4 = 1;
  varlen_setstr_str(out, "Y");
  varlen_add_a8(out, 0);
  varlen_add_a16(out, 0);
  varlen_add_a32(out, 0);
  varlen_add_a64(out, 0);
  varlen_add_nums(out, NULL);
  varlen_set_a8(out, 0, 0x12);
  varlen_set_a16(out, 0, 0x1234);
  varlen_set_a32(out, 0, 0x12345678);
  varlen_set_a64(out, 0, (((uint64_t)0x12345678)<<32)|0x9abcdef0);
  nums = numbers_new();
  varlen_set_nums(out, 0, nums);
  memset(buf, 99, sizeof(buf));
  tt_int_op(46, ==, varlen_encode(buf, sizeof(buf), out));
  inp = ux( "01""0001""00000001""0000000000000001"
            "59""12""1234""12345678"
            "123456789abcdef0"
            "00""0000""00000000""0000000000000000");
  tt_mem_op(buf, ==, inp, 46);

 end:
  varlen_free(out);
}

struct testcase_t vararray_tests[] = {
  { "truncated", test_varlen_truncated, 0, NULL, NULL },
  { "invalid", test_varlen_invalid, 0, NULL, NULL },
  { "encode-decode", test_varlen_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
