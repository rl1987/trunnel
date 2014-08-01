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

static const char CASE5[] =
  "08""0000""4000";

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

static const char BADTAG[] =
  "99""000000";

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
    { CASE5, CASE5, 0 },
    { NULL, NULL, 0 }
  };

  const struct item impossible_strings[] = {
    { TOOSHORT1, NULL, 3 },
    { TOOSHORT2, NULL, 4 },
    { TOOSHORT3, NULL, 8 },
    { TOOSHORT4, NULL, 8 },
    { EXTRA1, NULL, 5 },
    { BADTAG, NULL, 3 },
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
    /* Successful encode. */
    memset(buf, 0x7e, sizeof(buf));
    tt_int_op(outlen2, ==, union2_encode(buf, outlen2, out));

    inp = ux(item->post);
    tt_mem_op(buf, ==, inp, outlen2);

    /* Successful encode with length field cleared. (Make sure it gets
       regenerated) */
    out->length = 0xffff;
    memset(buf, 0x7e, sizeof(buf));
    tt_int_op(outlen2, ==, union2_encode(buf, outlen2, out));
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

static void
test_union2_invalid(void *arg)
{
  uint8_t buf[128];
  uint8_t *buf2=NULL;
  union2_t *union2=NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), NULL));

  union2 = union2_new();
  /* Invalid tag means invalid object */
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));

  /* Invalid item means invalid object */
  union2->tag = 4;
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));

  /* Now add the last item for success */
  union2->more = strdup("Hi");
  tt_int_op(22, ==, union2_encode(buf, sizeof(buf), union2));
  union2_free(union2); union2 = NULL;

  /* Fail on encoding if the length would overflow the u16 length field. */
  union2 = union2_new();
  union2->tag = 4;
  union2->length = 0;
  union2->un_remainder.allocated_ = union2->un_remainder.n_ = 65520;
  union2->un_remainder.elts_ = calloc(1,65520);
  union2->more = strdup("");
  buf2 = malloc(100000);
  tt_int_op(-1, ==, union2_encode(buf2, 100000, union2));

 end:
  union2_free(union2);
  if (buf2)
    free(buf2);
}

static void
test_union2_encdec(void *arg)
{
  const uint8_t *inp;
  union2_t *out = NULL;
  size_t len;
  (void)arg;

  /* (We already round-tripped these in truncated.) */

  /* CASE1 */
  inp = ux(CASE1);
  len = strlen(CASE1)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 2);
  tt_int_op(out->length, ==, 1);
  tt_int_op(out->un_a, ==, 6);
  tt_str_op(out->more, ==, "f");
  union2_free(out); out = NULL;

  /* CASE2 */
  inp = ux(CASE2);
  len = strlen(CASE2)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 3);
  tt_int_op(out->length, ==, 2);
  tt_int_op(out->un_b, ==, 1);
  tt_str_op(out->more, ==, "");
  union2_free(out); out = NULL;

  /* CASE2b */
  inp = ux(CASE2);
  len = strlen(CASE2)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 3);
  tt_int_op(out->length, ==, 2);
  tt_int_op(out->un_b, ==, 1);
  tt_str_op(out->more, ==, "");
  union2_free(out); out = NULL;

  /* CASE3 */
  inp = ux(CASE3);
  len = strlen(CASE3)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 5);
  tt_int_op(out->length, ==, 16);
  tt_mem_op(out->un_c, ==, ".pure machinery.", 16);
  tt_int_op(union2_get_un_remainder_len(out), ==, 0);
  tt_str_op(out->more, ==, "");
  union2_free(out); out = NULL;

  /* CASE4 */
  inp = ux(CASE4);
  len = strlen(CASE4)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 5);
  tt_int_op(out->length, ==, 34);
  tt_mem_op(out->un_c, ==, "Ashcans and unob", 16);
  tt_int_op(union2_get_un_remainder_len(out), ==, 18);
  tt_mem_op(out->un_remainder.elts_, ==, "tainable dollars!", 18);
  tt_str_op(out->more, ==, "w");
  union2_free(out); out = NULL;

  /* CASE5 */
  inp = ux(CASE5);
  len = strlen(CASE5)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 8);
  tt_int_op(out->length, ==, 0);
  tt_str_op(out->more, ==, "@");
  union2_free(out); out = NULL;


 end:
  union2_free(out);
}

struct testcase_t union_withlen_tests[] = {
  { "truncated", test_union2_truncated, 0, NULL, NULL },
  { "invalid", test_union2_invalid, 0, NULL, NULL },
  { "encode-decode", test_union2_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
