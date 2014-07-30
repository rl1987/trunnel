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

  /* The array lengths need to really match. */
  varlen = varlen_new();
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

  varlen->str = strdup("X");

  TRUNNEL_DYNARRAY_ADD(uint8_t, &varlen->a8, 5);
  TRUNNEL_DYNARRAY_ADD(uint16_t, &varlen->a16, 5);
  TRUNNEL_DYNARRAY_ADD(uint32_t, &varlen->a32, 5);
  TRUNNEL_DYNARRAY_ADD(uint64_t, &varlen->a64, 5);

  TRUNNEL_DYNARRAY_ADD(numbers_t *, &varlen->nums, NULL);
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));

  /* Now make sure it's good */
  TRUNNEL_DYNARRAY_SET(&varlen->nums, 0, numbers_new());
  tt_int_op(-1, !=, varlen_encode(buf, sizeof(buf), varlen));

 trunnel_alloc_failed:
 end:
  varlen_free(varlen);
}

#if 0
static void
test_varlen_encdec(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128] = {0};
  varlen_t *out = NULL;
  (void)arg;

  inp = ux( "01020408"
            "0010""0020""0040""0080""0100""0200"
            "00000400""00000800""00001000"
            "0000000000002000"
            "01" "0002" "00000003"
            "0000000000000004"
            "50" "6000" "70000000"
            "8000000000000000" );

  tt_int_op(66, ==, varlen_parse(&out, inp, 66));
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

  tt_int_op(66, ==, varlen_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, 66);

 end:
  varlen_free(out);
}
#endif

struct testcase_t vararray_tests[] = {
  { "truncated", test_varlen_truncated, 0, NULL, NULL },
  { "invalid", test_varlen_invalid, 0, NULL, NULL },
#if 0
 { "encode-decode", test_varlen_encdec, 0, NULL, NULL },
#endif
  END_OF_TESTCASES
};
