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

static const char CASE6[] =
  "09""000B""0A""0102030405060708090A""4000";

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

static const char TOOSHORT5[] =
  "09""0000";

static const char TOOSHORT6[] =
  "09""000B""09""0102030405060708090A""4000";

static const char TOOSHORT7[] =
  "09""000B""0B""0102030405060708090A""4000";

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
    { CASE6, CASE6, 0 },
    { NULL, NULL, 0 }
  };

  const struct item impossible_strings[] = {
    { TOOSHORT1, NULL, 3 },
    { TOOSHORT2, NULL, 4 },
    { TOOSHORT3, NULL, 8 },
    { TOOSHORT4, NULL, 8 },
    { TOOSHORT5, NULL, 3 },
    { TOOSHORT6, NULL, 14 },
    { TOOSHORT7, NULL, 14 },
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
  const uint8_t *inp;
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

  /* Length mismatch. */
  union2 = union2_new();
  union2->more = strdup("!");
  union2->tag = 9;
  union2->un_x = 3;
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));
  tt_int_op(0, ==, union2_getlen_un_xs(union2));
  union2_add_un_xs(union2, 1);
  union2_add_un_xs(union2, 2);
  tt_int_op(2, ==, union2_getlen_un_xs(union2));
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));
  union2_add_un_xs(union2, 3);
  /* Success! */
  tt_int_op(3, ==, union2_getlen_un_xs(union2));
  tt_int_op(9, ==, union2_encode(buf, sizeof(buf), union2));
  inp = ux("090004030102032100");
  tt_mem_op(buf, ==, inp, 5);
  union2_set_un_xs(union2, 0, 3);
  union2_set_un_xs(union2, 1, 3);
  tt_int_op(3, ==, union2_get_un_xs(union2, 2));
  tt_int_op(9, ==, union2_encode(buf, sizeof(buf), union2));
  inp = ux("090004030303032100");
  tt_mem_op(buf, ==, inp, 5);
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
  uint8_t buf[100];
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
  tt_int_op(union2_get_tag(out), ==, 2);
  tt_int_op(union2_get_length(out), ==, 1);
  tt_int_op(union2_get_un_a(out), ==, 6);
  tt_str_op(union2_get_more(out), ==, "f");
  union2_free(out); out = NULL;
  out = union2_new();
  union2_set_tag(out, 2);
  union2_set_length(out, 1);
  union2_set_un_a(out, 6);
  union2_set_more(out, "this is not the thing we set. The next one is.");
  union2_set_more(out, "f");
  tt_int_op(len, ==, union2_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, len);
  union2_free(out); out = NULL;

  /* CASE2 */
  inp = ux(CASE2);
  len = strlen(CASE2)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 3);
  tt_int_op(out->length, ==, 2);
  tt_int_op(out->un_b, ==, 1);
  tt_str_op(out->more, ==, "");
  tt_int_op(union2_get_tag(out), ==, 3);
  tt_int_op(union2_get_length(out), ==, 2);
  tt_int_op(union2_get_un_b(out), ==, 1);
  tt_str_op(union2_get_more(out), ==, "");
  union2_free(out); out = NULL;
  out = union2_new();
  union2_set_tag(out, 3);
  union2_set_un_b(out, 1);
  union2_set_more(out, "");
  tt_int_op(len, ==, union2_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, len);
  union2_free(out); out = NULL;

  /* CASE2b */
  inp = ux(CASE2b);
  len = strlen(CASE2b)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 3);
  tt_int_op(out->length, ==, 4);
  tt_int_op(out->un_b, ==, 1);
  tt_str_op(out->more, ==, "");
  tt_int_op(union2_get_tag(out), ==, 3);
  tt_int_op(union2_get_length(out), ==, 4);
  tt_int_op(union2_get_un_b(out), ==, 1);
  tt_str_op(union2_get_more(out), ==, "");
  union2_free(out); out = NULL;

  /* CASE3 */
  inp = ux(CASE3);
  len = strlen(CASE3)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 5);
  tt_int_op(out->length, ==, 16);
  tt_mem_op(out->un_c, ==, ".pure machinery.", 16);
  tt_int_op(union2_getlen_un_remainder(out), ==, 0);
  tt_str_op(out->more, ==, "");
  tt_int_op(union2_get_tag(out), ==, 5);
  tt_int_op(union2_get_length(out), ==, 16);
  tt_mem_op(union2_getarray_un_c(out), ==, ".pure machinery.", 16);
  tt_int_op(union2_get_un_c(out,1), ==, 'p');
  union2_free(out); out = NULL;
  out = union2_new();
  union2_set_tag(out, 5);
  memcpy(union2_getarray_un_c(out), "Xpure machinery.", 16);
  union2_set_un_c(out, 0, '.');
  union2_set_more(out, "");
  tt_int_op(len, ==, union2_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, len);
  union2_free(out); out = NULL;

  /* CASE4 */
  inp = ux(CASE4);
  len = strlen(CASE4)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 5);
  tt_int_op(out->length, ==, 34);
  tt_mem_op(out->un_c, ==, "Ashcans and unob", 16);
  tt_int_op(union2_getlen_un_remainder(out), ==, 18);
  tt_int_op(union2_get_un_remainder(out, 0), ==, 't');
  tt_int_op(union2_getlen_un_c(out), ==, 16);
  tt_mem_op(out->un_remainder.elts_, ==, "tainable dollars!", 18);
  tt_str_op(out->more, ==, "w");
  tt_mem_op(union2_getarray_un_remainder(out), ==, "tainable dollars!", 18);

  /* mess with un_remainder to exercise accessors. */
  union2_set_un_remainder(out, 17, '?');
  union2_add_un_remainder(out, '!');
  tt_int_op(len+1, ==, union2_encode(buf, sizeof(buf), out));
  inp = ux("05""0023"
      "41736863616e7320616e6420756e6f627461696e61626c6520646f6c6c617273213F21"
      "7700");
  tt_mem_op(buf, ==, inp, len+1);

  union2_free(out); out = NULL;
  out = union2_new();
  union2_set_tag(out, 5);
  memcpy(union2_getarray_un_c(out), "Ashcans and unob", 16);
  union2_set_more(out, "w");
  union2_setlen_un_remainder(out, 17);
  memcpy(union2_getarray_un_remainder(out), "tainable dollars!", 17);
  union2_add_un_remainder(out, '?');
  union2_add_un_remainder(out, '!');
  tt_int_op(len+1, ==, union2_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, len+1);
  union2_free(out); out = NULL;

  /* CASE5 */
  inp = ux(CASE5);
  len = strlen(CASE5)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(out->tag, ==, 8);
  tt_int_op(out->length, ==, 0);
  tt_str_op(out->more, ==, "@");
  union2_free(out); out = NULL;

  out = union2_new();
  union2_set_tag(out, 8);
  union2_set_more(out, "@");
  tt_int_op(len, ==, union2_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, len);

  /* CASE 6: */
  inp = ux(CASE6);
  len = strlen(CASE6)/2;
  tt_int_op(len, ==, union2_parse(&out, inp, len));
  tt_int_op(9, ==, out->tag);
  tt_int_op(10, ==, union2_get_un_x(out));
  tt_mem_op("\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A", ==,
            union2_getarray_un_xs(out), 10);
  tt_int_op(10, ==, union2_getlen_un_xs(out));
  tt_int_op(3, ==, union2_get_un_xs(out, 2));
  union2_free(out); out = NULL;
  out = union2_new();
  union2_set_tag(out, 9);
  union2_set_un_x(out, 10);
  union2_setlen_un_xs(out, 8);
  memcpy(union2_getarray_un_xs(out), "\x01\x02\x03\x04\x05\x06\x07\x08", 8);
  union2_add_un_xs(out, 9);
  union2_add_un_xs(out, 10);
  union2_set_more(out, "jkdhfkldshjf");
  union2_set_more(out, "\x40");
  tt_int_op(len, ==, union2_encode(buf, sizeof(buf), out));
  tt_mem_op(buf, ==, inp, len);

 end:
  union2_free(out);
}

static void
test_union2_allocfail(void *arg)
{
  union2_t *union2 = NULL;
  const uint8_t *inp;
  uint8_t buf[128];
  (void) arg;
#ifdef ALLOCFAIL
  {
    int fail_at, i;
    const struct { const char *s; int n_fails; } item[] = {
      { CASE1, 2 },
      { CASE2, 2 },
      { CASE3, 3 },
      { CASE4, 3 },
      { CASE5, 2 },
      { CASE6, 3 },
      { NULL, 0 },
    };
    for (i = 0; item[i].s; ++i) {
      size_t len = strlen(item[i].s)/2;
      inp = ux(item[i].s);
      for (fail_at = 1; fail_at <= item[i].n_fails; ++fail_at) {
        set_alloc_fail(fail_at);
        tt_int_op(-1, ==, union2_parse(&union2, inp, len));
        tt_ptr_op(union2, ==, NULL);
      }
    }
  }

  union2 = union2_new();
  set_alloc_fail(1);
  tt_int_op(-1, ==, union2_add_un_xs(union2, 9));
  tt_int_op(1, ==, union2_clear_errors(union2));

  union2->un_xs.n_ = 255;
  tt_int_op(-1, ==, union2_add_un_xs(union2, 9));
  tt_int_op(1, ==, union2_clear_errors(union2));
  union2->un_xs.n_ = 0;

  set_alloc_fail(1);
  tt_int_op(-1, ==, union2_setlen_un_xs(union2, 9));
  tt_int_op(-1, ==, union2_encode(buf, sizeof(buf), union2));
  tt_int_op(1, ==, union2_clear_errors(union2));

  tt_int_op(-1, ==, union2_setlen_un_xs(union2, 1024));
  tt_int_op(1, ==, union2_clear_errors(union2));
  tt_int_op(0, ==, union2_getlen_un_xs(union2));

  set_alloc_fail(1);
  tt_int_op(-1, ==, union2_add_un_remainder(union2, 9));
  tt_int_op(1, ==, union2_clear_errors(union2));

  set_alloc_fail(1);
  tt_int_op(-1, ==, union2_setlen_un_remainder(union2, 9));
  tt_int_op(1, ==, union2_clear_errors(union2));

  set_alloc_fail(1);
  tt_int_op(-1, ==, union2_set_more(union2, "Can't strdup this."));
  tt_int_op(1, ==, union2_clear_errors(union2));


#else
  (void) inp;
  tt_skip();
#endif
 end:
  union2_free(union2);
}

struct testcase_t union_withlen_tests[] = {
  { "truncated", test_union2_truncated, 0, NULL, NULL },
  { "invalid", test_union2_invalid, 0, NULL, NULL },
  { "encode-decode", test_union2_encdec, 0, NULL, NULL },
  { "allocfail", test_union2_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
