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

  /* Mismatched len1. */
  tt_int_op(0, ==, varlen_add_a8(varlen, 5));
  tt_int_op(0, ==, varlen_add_str(varlen, 'x'));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len1++;
  tt_int_op(-1, !=, varlen_encode(buf, sizeof(buf), varlen));

  /* Mismatched len2. */
  tt_int_op(0, ==, varlen_add_a16(varlen, 5));
  tt_int_op(0, ==, varlen_add_nums(varlen, numbers_new()));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len2++;
  tt_int_op(-1, !=, varlen_encode(buf, sizeof(buf), varlen));

  /* Mismatched len3. */
  tt_int_op(0, ==, varlen_add_a32(varlen, 5));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len3++;
  tt_int_op(-1, !=, varlen_encode(buf, sizeof(buf), varlen));

  /* Mismatched len4. */
  tt_int_op(0, ==, varlen_add_a64(varlen, 5));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), varlen));
  varlen->len4++;
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
  tt_int_op(0, ==, varlen_getlen_a8(out));
  tt_int_op(0, ==, varlen_getlen_a16(out));
  tt_int_op(0, ==, varlen_getlen_a32(out));
  tt_int_op(0, ==, varlen_getlen_a64(out));
  tt_int_op(0, ==, varlen_getlen_nums(out));
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
  tt_int_op(2, ==, varlen_getlen_a8(out));
  tt_int_op(0, ==, varlen_getlen_a16(out));
  tt_int_op(0, ==, varlen_getlen_a32(out));
  tt_int_op(0, ==, varlen_getlen_a64(out));
  tt_int_op(0, ==, varlen_getlen_nums(out));
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
  tt_int_op(2, ==, varlen_getlen_a8(out));
  tt_int_op(2, ==, varlen_getlen_a16(out));
  tt_int_op(0, ==, varlen_getlen_a32(out));
  tt_int_op(0, ==, varlen_getlen_a64(out));
  tt_int_op(2, ==, varlen_getlen_nums(out));
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
  tt_assert(varlen_get_nums(out, 1) == varlen_getarray_nums(out)[1]);
  tt_assert(varlen_get_str(out, 1) == varlen_getarray_str(out)[1]);
  tt_assert(varlen_get_a8(out, 1) == varlen_getarray_a8(out)[1]);
  tt_assert(varlen_get_a16(out, 1) == varlen_getarray_a16(out)[1]);
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
  tt_int_op(0, ==, varlen_getlen_a8(out));
  tt_int_op(0, ==, varlen_getlen_a16(out));
  tt_int_op(4, ==, varlen_getlen_a32(out));
  tt_int_op(0, ==, varlen_getlen_a64(out));
  tt_int_op(0, ==, varlen_getlen_nums(out));
  tt_int_op(0x606, ==, varlen_get_a32(out, 0));
  tt_int_op(0x0842, ==, varlen_get_a32(out, 1));
  tt_int_op(0x867, ==, varlen_get_a32(out, 2));
  tt_int_op(0x5309, ==, varlen_get_a32(out, 3));
  tt_assert(varlen_get_a32(out, 1) == varlen_getarray_a32(out)[1]);
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
  tt_int_op(0, ==, varlen_getlen_a8(out));
  tt_int_op(0, ==, varlen_getlen_a16(out));
  tt_int_op(0, ==, varlen_getlen_a32(out));
  tt_int_op(2, ==, varlen_getlen_a64(out));
  tt_int_op(0, ==, varlen_getlen_nums(out));
  u64 = varlen_get_a64(out, 0);
  tt_int_op(0x606, ==, (uint32_t)(u64 >> 32));
  tt_int_op(0x842, ==, (uint32_t)u64);
  u64 = varlen_get_a64(out, 1);
  tt_int_op(0x867, ==, (uint32_t)(u64 >> 32));
  tt_int_op(0x5309, ==, (uint32_t)u64);
  tt_assert(varlen_get_a64(out, 1) == varlen_getarray_a64(out)[1]);
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

static void
test_varlen_accessors_str(void *arg)
{
  varlen_t *var = NULL;
  char *s = NULL;
  int i;
  (void)arg;

  var = varlen_new();
  tt_int_op(0, ==, varlen_get_len1(var));
  tt_int_op(0, ==, varlen_get_len2(var));
  tt_int_op(0, ==, varlen_get_len3(var));
  tt_int_op(0, ==, varlen_get_len4(var));

  tt_int_op(0, ==, varlen_set_len1(var, 5));
  tt_int_op(0, ==, varlen_set_len2(var, 2));
  tt_int_op(0, ==, varlen_set_len3(var, 1));
  tt_int_op(0, ==, varlen_set_len4(var, 1));

  tt_int_op(0, ==, varlen_add_str(var, 'a'));
  tt_int_op(0, ==, varlen_add_str(var, 'b'));
  tt_int_op(0, ==, varlen_add_str(var, 'c'));
  tt_int_op('c', ==, varlen_get_str(var, 2));
  tt_str_op("abc", ==, varlen_getstr_str(var));
  tt_int_op(0, ==, varlen_set_str(var, 2, 'd'));
  tt_str_op("abd", ==, varlen_getstr_str(var));
  tt_int_op(3, ==, varlen_getlen_str(var));
  tt_int_op(0, ==, varlen_setstr_str(var, "Plugh"));
  tt_int_op(5, ==, varlen_getlen_str(var));
  tt_str_op("Plugh", ==, varlen_getstr_str(var));
  tt_mem_op("Plugh", ==, varlen_getarray_str(var), 6);

  tt_int_op(0, ==, varlen_setstr_str(var, "abcdefgh"));
  for (i = 0; i < 30; ++i)
    tt_int_op(0, ==, varlen_add_str(var, 'x'));

  tt_str_op("abcdefghxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", ==,
            varlen_getstr_str(var));

  /* Adding a 256th character to the string should fail. */
  while (0 == varlen_add_str(var, 'x'))
    ;
  tt_int_op(255, ==, varlen_getlen_str(var));
  tt_str_op("abcdefghxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", ==,
            varlen_getstr_str(var));
  tt_int_op(1, ==, varlen_clear_errors(var));

  tt_int_op(0, ==, varlen_setlen_str(var, 20));
  tt_int_op(20, ==, varlen_getlen_str(var));

  /* Setting the string to a 256-character thing should fail. */
  s = calloc(1,256);
  tt_int_op(-1, ==, varlen_setstr0_str(var, s, 256));
  tt_int_op(1, ==, varlen_clear_errors(var));
  tt_int_op(0, ==, varlen_setstr0_str(var, s, 255));
  tt_int_op(0, ==, varlen_clear_errors(var));


  /* Be tricky: getstr when there is no room for a NUL. */
  /* (we need to set up the array by hand to make sure this happens) */
  var->str.allocated_ = 8;
  var->str.n_ = 8;
  free(var->str.elts_);
  var->str.elts_ = malloc(8);
  memcpy(var->str.elts_, "abcdefgh", 8);
  tt_str_op("abcdefgh", ==, varlen_getstr_str(var));

  /* Some setlen_str tests */
  tt_int_op(0, ==, varlen_setlen_str(var, 4));
  tt_str_op("abcd", ==, varlen_getstr_str(var));

  tt_int_op(-1, ==, varlen_setlen_str(var, 256));
  tt_str_op("abcd", ==, varlen_getstr_str(var));
  tt_int_op(1, ==, varlen_clear_errors(var));

 end:
  if (s)
    free(s);
  varlen_free(var);
}

static void
test_varlen_accessors_oob(void *arg)
{
  varlen_t *var = NULL;
  uint8_t buf[20];
  const uint8_t *inp;
  (void) arg;

  var = varlen_new();
  tt_int_op(-1, ==, varlen_setlen_a8(var, 256));
  tt_int_op(1, ==, varlen_clear_errors(var));
  tt_int_op(-1, ==, varlen_setlen_a16(var, 1<<16));
  tt_int_op(1, ==, varlen_clear_errors(var));
#if UINT32_MAX < SIZE_MAX
  tt_int_op(-1, ==, varlen_setlen_a32(var, ((uint64_t)1)<<32));
  tt_int_op(1, ==, varlen_clear_errors(var));
#endif
  tt_int_op(-1, ==, varlen_setlen_nums(var, 1<<16));
  tt_int_op(-1, ==, varlen_encode(buf, sizeof(buf), var));
  tt_int_op(1, ==, varlen_clear_errors(var));
  tt_int_op(strlen(MINIMAL)/2, ==, varlen_encode(buf, sizeof(buf), var));
  inp = ux(MINIMAL);
  tt_mem_op(buf, ==, inp, strlen(MINIMAL)/2)

 end:
  varlen_free(var);
}

static void
test_varlen_allocfail(void *arg)
{
  varlen_t *varlen = NULL;
  const uint8_t *inp;
  (void) arg;
#ifdef ALLOCFAIL
  {
    int fail_at, i;
    const struct { const char *s; int n_fails; } item[] = {
      { MINIMAL, 7 },
      { SOME_LEN1, 7 },
      { SOME_LEN1_SOME_LEN2, 9 },
      { SOME_LEN3, 7 },
      { SOME_LEN4, 7 },
      { NULL, 0 },
    };
    for (i = 0; item[i].s; ++i) {
      size_t len = strlen(item[i].s)/2;
      inp = ux(item[i].s);
      for (fail_at = 1; fail_at <= item[i].n_fails; ++fail_at) {
        set_alloc_fail(fail_at);
        tt_int_op(-1, ==, varlen_parse(&varlen, inp, len));
        tt_ptr_op(varlen, ==, NULL);
      }
    }
  }

  varlen = varlen_new();
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_setlen_str(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_setlen_a8(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_setlen_a16(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_setlen_a32(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_setlen_a64(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_setlen_nums(varlen,2));

  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_add_str(varlen,'x'));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_add_a8(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_add_a16(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_add_a32(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_add_a64(varlen,2));
  set_alloc_fail(1);
  tt_int_op(-1, ==, varlen_add_nums(varlen,NULL));

#else
  (void) inp;
  tt_skip();
#endif
 end:
  varlen_free(varlen);
}

struct testcase_t vararray_tests[] = {
  { "truncated", test_varlen_truncated, 0, NULL, NULL },
  { "invalid", test_varlen_invalid, 0, NULL, NULL },
  { "encode-decode", test_varlen_encdec, 0, NULL, NULL },
  { "accessors-str", test_varlen_accessors_str, 0, NULL, NULL },
  { "accessors-oob", test_varlen_accessors_oob, 0, NULL, NULL },
  { "allocfail", test_varlen_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
