#include "test.h"

static const char CASE1[] =
  "02""06";

static const char CASE2[] =
  "03""0001""0000000000010000";

static const char CASE3[] =
  "05""2e70757265206d616368696e6572792e";

static const char CASE4[] =
  "06""41736863616e7320616e6420756e6f627461696e61626c6520646f6c6c6172732100";

static const char CASE5[] =
  "07""05" "0004" "00000003" "00000000""00000002";

static const char CASE6[] =
  "08";

static const char CASE7[] =
  "09""0A""0102030405060708090A";

static void
test_union1_truncated(void *arg)
{
  const uint8_t *inp;
  const char **str;
  unsigned i;
  union1_t *out = NULL;
  uint8_t buf[128];

  const char *strings[] = {
    CASE1,
    CASE2,
    CASE3,
    CASE4,
    CASE5,
    CASE6,
    CASE7,
    NULL
  };

  (void) arg;
  for (str = &strings[0]; *str; ++str) {
    size_t outlen = strlen(*str) / 2;
    inp = ux(*str);
    /* Truncated on parse */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, union1_parse(&out, inp, i));
      tt_ptr_op(NULL, ==, out);
    }
    /* Success */
    tt_int_op(outlen, ==, union1_parse(&out, inp, outlen));

    /* Truncated on encode */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, union1_encode(buf, i, out));
    }
    memset(buf, 0x7e, sizeof(buf));
    tt_int_op(outlen, ==, union1_encode(buf, outlen, out));
    tt_mem_op(buf, ==, inp, outlen);
    union1_free(out);
    out = NULL;
  }

 end:
  union1_free(out);
}

static void
test_union1_invalid(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128];
  union1_t *union1=NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, union1_encode(buf, sizeof(buf), NULL));

  union1 = union1_new();
  /* Invalid tag means invalid object */
  tt_int_op(-1, ==, union1_encode(buf, sizeof(buf), union1));

  /* Invalid item means invalid object */
  union1->tag = 6;
  tt_int_op(-1, ==, union1_encode(buf, sizeof(buf), union1));

  /* Success! */
  union1->un_d = strdup("Hi there");
  tt_int_op(10, ==, union1_encode(buf, sizeof(buf), union1));
  union1_free(union1); union1 = NULL;

  /* Length mismatch. */
  union1 = union1_new();
  union1->tag = 9;
  union1->un_x = 3;
  tt_int_op(-1, ==, union1_encode(buf, sizeof(buf), union1));
  tt_int_op(0, ==, union1_get_un_xs_len(union1));
  union1_add_un_xs(union1, 1);
  union1_add_un_xs(union1, 2);
  tt_int_op(2, ==, union1_get_un_xs_len(union1));
  tt_int_op(-1, ==, union1_encode(buf, sizeof(buf), union1));
  union1_add_un_xs(union1, 3);
  /* Success! */
  tt_int_op(5, ==, union1_encode(buf, sizeof(buf), union1));
  inp = ux("0903010203");
  tt_mem_op(buf, ==, inp, 5);
  union1_set_un_xs(union1, 0, 3);
  union1_set_un_xs(union1, 1, 3);
  tt_int_op(3, ==, union1_get_un_xs(union1, 2));
  tt_int_op(5, ==, union1_encode(buf, sizeof(buf), union1));
  inp = ux("0903030303");
  tt_mem_op(buf, ==, inp, 5);

  /* Check for a bad struct */
  union1->tag = 7;
  union1->un_e.i32 = 0xbadbeef;
  tt_int_op(-1, ==, union1_encode(buf, sizeof(buf), union1));

  union1_free(union1); union1 = NULL;

  /* Try parsing a bad tag */
  inp = ux("FF");
  tt_int_op(-1, ==, union1_parse(&union1, inp, 1));
 end:
  union1_free(union1);
}

static void
test_union1_encdec(void *arg)
{
  const uint8_t *inp;
  union1_t *out = NULL;
  //  uint8_t buf[128];
  size_t len;
  (void)arg;

  /* (We already round-tripped these in truncated.) */

  /* CASE1 */
  inp = ux(CASE1);
  len = strlen(CASE1)/2;
  tt_int_op(len, ==, union1_parse(&out, inp, len));
  tt_int_op(2, ==, out->tag);
  tt_int_op(6, ==, out->un_a);
  union1_free(out); out = NULL;

  /* CASE2 */
  inp = ux(CASE2);
  len = strlen(CASE2)/2;
  tt_int_op(len, ==, union1_parse(&out, inp, len));
  tt_int_op(3, ==, out->tag);
  tt_int_op(1, ==, out->un_b);
  tt_int_op(65536, ==, out->un_b2);
  union1_free(out); out = NULL;

  /* CASE3 */
  inp = ux(CASE3);
  len = strlen(CASE3)/2;
  tt_int_op(len, ==, union1_parse(&out, inp, len));
  tt_int_op(5, ==, out->tag);
  tt_mem_op(".pure machinery.", ==, out->un_c, 16);
  union1_free(out); out = NULL;

  /* CASE4 */
  inp = ux(CASE4);
  len = strlen(CASE4)/2;
  tt_int_op(len, ==, union1_parse(&out, inp, len));
  tt_int_op(6, ==, out->tag);
  tt_str_op("Ashcans and unobtainable dollars!", ==, out->un_d);
  union1_free(out); out = NULL;

  /* CASE5 */
  inp = ux(CASE5);
  len = strlen(CASE5)/2;
  tt_int_op(len, ==, union1_parse(&out, inp, len));
  tt_int_op(7, ==, out->tag);
  tt_int_op(5, ==, out->un_e.i8);
  tt_int_op(4, ==, out->un_e.i16);
  tt_int_op(3, ==, out->un_e.i32);
  tt_int_op(2, ==, out->un_e.i64);
  union1_free(out); out = NULL;

 end:
  union1_free(out);
}


struct testcase_t union_nolen_tests[] = {
  { "truncated", test_union1_truncated, 0, NULL, NULL },
  { "invalid", test_union1_invalid, 0, NULL, NULL },
  { "encode-decode", test_union1_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
