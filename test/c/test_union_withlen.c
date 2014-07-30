#include "test.h"

static const char CASE1[] =
  "02""0001""06""6600";

static const char CASE2[] =
  "03""0002""0001""00";

static const char CASE2b[] =
  "03""0004""00012255""00";

static const char CASE3[] =
  "05""0010""2e70757265206d616368696e6572792e""00";

static const char CASE4[] =
  "05""0022"
  "41736863616e7320616e6420756e6f627461696e61626c6520646f6c6c6172732100"
  "7700";

static const char TOOSHORT1[] =
  "02""0000""06""6600";

static const char EXTRA1[] =
  "02""0002""0655""6600";

static const char TOOSHORT2[] =
  "03""0001""0001""00";

static const char TOOSHORT3[] =
  "05""0005""2e70757265206d616368696e6572792e""00";

static const char TOOSHORT4[] =
  "05""0005"
  "41736863616e7320616e6420756e6f627461696e61626c6520646f6c6c6172732100"
  "7700";

struct item {
  const char *pre;
  const char *post;
  unsigned badafter;
};

static void
test_union2_truncated(void *arg)
{
  const uint8_t *inp;
  const struct item *item;
  unsigned i;
  union2_t *out = NULL;
  uint8_t buf[128];

  const struct item strings[] = {
    { CASE1, CASE1, 0},
    { CASE2, CASE2, 0 },
    { CASE2b, CASE2, 0 },
    { CASE3, CASE3, 0 },
    { CASE4, CASE4, 0 },
    { NULL, NULL, 0 }
  };

  const struct item impossible_strings[] = {
    { TOOSHORT1, NULL, 3 },
    { TOOSHORT2, NULL, 4 },
    { TOOSHORT3, NULL, 8 },
    { TOOSHORT4, NULL, 8 },
    { EXTRA1, NULL, 5 },
    { NULL, NULL, 0 }
  };

  (void) arg;
  for (item = &strings[0]; item->pre != NULL; ++item) {
    size_t outlen = strlen(item->pre) / 2;
    size_t outlen2 = strlen(item->post) / 2;
    inp = ux(item->pre);
    /* Truncated on parse */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, union2_parse(&out, inp, i));
      tt_ptr_op(NULL, ==, out);
    }
    /* Success */
    tt_int_op(outlen, ==, union2_parse(&out, inp, outlen));

    /* Truncated on encode */
    for (i = 0; i < outlen2; ++i) {
      tt_int_op(-2, ==, union2_encode(buf, i, out));
    }
    memset(buf, 0x7e, sizeof(buf));
    tt_int_op(outlen2, ==, union2_encode(buf, outlen2, out));

    inp = ux(item->post);
    tt_mem_op(buf, ==, inp, outlen2);
    union2_free(out);
    out = NULL;
  }

  for (item = &impossible_strings[0]; item->pre != NULL; ++item) {
    size_t outlen = strlen(item->pre) / 2;
    inp = ux(item->pre);
    /* At no length can these be parsed. They look truncated at first,
     * and then look impossible. */
    for (i = 0; i < outlen; ++i) {
      int errcode = (i < item->badafter) ? -2 : -1;
      tt_int_op(errcode, ==, union2_parse(&out, inp, i));
      tt_ptr_op(NULL, ==, out);
    }
    tt_int_op(-1, ==, union2_parse(&out, inp, i));
  }

 end:
  union2_free(out);
}

#if 0
static void
test_union2_invalid(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128];
  union2_t *union2=NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), NULL));

  union2 = union2_new();
  /* Invalid tag means invalid object */
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));

  /* Invalid item means invalid object */
  union2->tag = 6;
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));

  /* Success! */
  union2->un_d = strdup("Hi there");
  tt_int_op(10, ==, union2_encode(buf, sizeof(buf), union2));
  union2_free(union2); union2 = NULL;

  /* Try parsing a bad tag */
  inp = ux("FF");
  tt_int_op(-1, ==, union2_parse(&union2, inp, 1));

 end:
  union2_free(union2);
}

static void
test_union2_encdec(void *arg)
{
  const uint8_t *inp;
  union2_t *out = NULL;
  //  uint8_t buf[128];
  size_t len;
  (void)arg;

  /* (We already round-tripped these in truncated.) */

  /* CASE1 */
  inp = ux(CASE1);
  len = strlen(CASE1)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(2, ==, out->tag);
  tt_int_op(6, ==, out->un_a);
  union2_free(out); out = NULL;

  /* CASE2 */
  inp = ux(CASE2);
  len = strlen(CASE2)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(3, ==, out->tag);
  tt_int_op(1, ==, out->un_b);
  tt_int_op(65536, ==, out->un_b2);
  union2_free(out); out = NULL;

  /* CASE3 */
  inp = ux(CASE3);
  len = strlen(CASE3)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(5, ==, out->tag);
  tt_mem_op(".pure machinery.", ==, out->un_c, 16);
  union2_free(out); out = NULL;

  /* CASE4 */
  inp = ux(CASE4);
  len = strlen(CASE4)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(6, ==, out->tag);
  tt_str_op("Ashcans and unobtainable dollars!", ==, out->un_d);
  union2_free(out); out = NULL;

  /* CASE5 */
  inp = ux(CASE5);
  len = strlen(CASE5)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(7, ==, out->tag);
  tt_int_op(5, ==, out->un_e.i8);
  tt_int_op(4, ==, out->un_e.i16);
  tt_int_op(3, ==, out->un_e.i32);
  tt_int_op(2, ==, out->un_e.i64);
  union2_free(out); out = NULL;

 end:
  union2_free(out);
}
#endif

struct testcase_t union_withlen_tests[] = {
  { "truncated", test_union2_truncated, 0, NULL, NULL },
#if 0
  { "invalid", test_union2_invalid, 0, NULL, NULL },
  { "encode-decode", test_union2_encdec, 0, NULL, NULL },
#endif
  END_OF_TESTCASES
};
