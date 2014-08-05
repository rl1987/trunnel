
#include "test.h"

const char CASE1[] =
  "0002""0001""FF";
const char CASE2[] =
  "0009""0000";
const char CASE3[] =
  "0010""0005""6566676869";

static void
test_unions_truncated(void *arg)
{
  const uint8_t *inp;
  int j;
  unsigned i;
  union3_t *union3 = NULL;
  union4_t *union4 = NULL;
  uint8_t buf[128];

  const char *strings[] = {
    CASE1,
    CASE2,
    CASE3,
    NULL
  };
  const char *u4_encoded[] = {
    CASE1,
    CASE2,
    "0010""0000",
    NULL
  };

  (void) arg;
  for (j=0; strings[j]; ++j) {
    const char *str = strings[j];
    size_t outlen = strlen(str) / 2;
    inp = ux(str);
    /* Truncated on parse */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, union3_parse(&union3, inp, i));
      tt_ptr_op(NULL, ==, union3);
      tt_int_op(-2, ==, union4_parse(&union4, inp, i));
      tt_ptr_op(NULL, ==, union4);
    }
    /* Success */
    tt_int_op(outlen, ==, union3_parse(&union3, inp, outlen));
    tt_int_op(outlen, ==, union4_parse(&union4, inp, outlen));

    /* Truncated on encode */
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, union3_encode(buf, i, union3));
    }
    /* Success */
    memset(buf, 0x31, sizeof(buf));
    tt_int_op(outlen, ==, union3_encode(buf, outlen, union3));
    tt_mem_op(buf, ==, inp, outlen);

    /* Truncated on encode */
    str = u4_encoded[j];
    inp = ux(str);
    outlen = strlen(str) / 2;
    for (i = 0; i < outlen; ++i) {
      tt_int_op(-2, ==, union4_encode(buf, i, union4));
    }
    /* Success */
    memset(buf, 0x13, sizeof(buf));
    tt_int_op(outlen, ==, union4_encode(buf, outlen, union4));
    tt_mem_op(buf, ==, inp, outlen);

    union3_free(union3); union3 = NULL;
    union4_free(union4); union4 = NULL;
  }

 end:
  union3_free(union3);
  union4_free(union4);
}

static void
test_union3_invalid(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128];
  uint8_t *buf2 = NULL;
  union3_t *union3=NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, union3_encode(buf, sizeof(buf), NULL));

  union3 = union3_new();
  union3->tag = 6;

  /* Success! */
  union3->un_stuff.n_ = union3->un_stuff.allocated_ = 10;
  union3->un_stuff.elts_ = (uint8_t*) strdup("hola mundo");
  memset(buf, 99, sizeof(buf));
  tt_int_op(14, ==, union3_encode(buf, sizeof(buf), union3));
  inp = ux("0006000A686f6c61206d756e646f");
  tt_mem_op(buf, ==, inp, 14);
  union3_free(union3); union3 = NULL;

  /* Can't parse with extra data after the a field. */
  inp = ux("000200025555");
  tt_int_op(-1, ==, union3_parse(&union3, inp, 6));

  /* Can't parse with no room for the a field */
  inp = ux("00020000");
  tt_int_op(-1, ==, union3_parse(&union3, inp, 4));

  /* Can't encode if 'un_stuff' would overflow length field. */
  union3 = union3_new();
  union3->tag = 90;
  union3->un_stuff.n_ = union3->un_stuff.allocated_ = 65536;
  union3->un_stuff.elts_ = calloc(1,65536);
  buf2 = malloc(100000);
  tt_int_op(-1, ==, union3_encode(buf2, 100000, union3));

 end:
  union3_free(union3);
  if (buf2)
    free(buf2);
}

static void
test_union4_invalid(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128];
  union4_t *union4 = NULL;
  (void)arg;

  /* NULL can't be encoded */
  tt_int_op(-1, ==, union4_encode(buf, sizeof(buf), NULL));

  /* Can't parse with extra data after the a field. */
  inp = ux("000200025555");
  tt_int_op(-1, ==, union4_parse(&union4, inp, 6));

  /* Can't parse with no room for the a field */
  inp = ux("00020000");
  tt_int_op(-1, ==, union4_parse(&union4, inp, 4));

 end:
  union4_free(union4);
}

static void
test_union34_encdec(void *arg)
{
  const uint8_t *inp;
  union3_t *union3 = NULL;
  union4_t *union4 = NULL;
  uint8_t buf[128];
  size_t len;
  (void)arg;

  /* (We already round-tripped these in truncated.) */

  /* CASE1 */
  inp = ux(CASE1);
  len = strlen(CASE1)/2;
  tt_int_op(len, ==, union3_parse(&union3, inp, len));
  tt_int_op(len, ==, union4_parse(&union4, inp, len));
  tt_int_op(2, ==, union3->tag);
  tt_int_op(2, ==, union4->tag);
  tt_int_op(1, ==, union3->length);
  tt_int_op(1, ==, union4->length);
  tt_int_op(0xff, ==, union3->un_a);
  tt_int_op(0xff, ==, union4->un_a);
  union3_free(union3); union3 = NULL;
  union4_free(union4); union4 = NULL;

  /* CASE2 */
  inp = ux(CASE2);
  len = strlen(CASE2)/2;
  tt_int_op(len, ==, union3_parse(&union3, inp, len));
  tt_int_op(len, ==, union4_parse(&union4, inp, len));
  tt_int_op(9, ==, union3->tag);
  tt_int_op(9, ==, union4->tag);
  tt_int_op(0, ==, union3->length);
  tt_int_op(0, ==, union4->length);
  tt_int_op(0, ==, union3_getlen_un_stuff(union3));

  /* verify correct re-encode after 'length' trashed for union3 */
  union3->length = 9999;
  memset(buf, 0xff, sizeof(buf));
  tt_int_op(len, ==, union3_encode(buf, sizeof(buf), union3));
  tt_mem_op(buf, ==, inp, len);

  union3_free(union3); union3 = NULL;
  union4_free(union4); union4 = NULL;

  /* CASE3 */
  inp = ux(CASE3);
  len = strlen(CASE3)/2;
  tt_int_op(len, ==, union3_parse(&union3, inp, len));
  tt_int_op(len, ==, union4_parse(&union4, inp, len));
  tt_int_op(16, ==, union3->tag);
  tt_int_op(16, ==, union4->tag);
  tt_int_op(5, ==, union3->length);
  tt_int_op(5, ==, union4->length);
  tt_int_op(5, ==, union3_getlen_un_stuff(union3));
  tt_mem_op("efghi", ==, union3->un_stuff.elts_, 5);
  tt_int_op('e', ==, union3_get_un_stuff(union3, 0));
  union3_set_un_stuff(union3, 0, (uint8_t)'f');
  union3_add_un_stuff(union3, (uint8_t)'j');

  /* verify correct re-encode after 'length' trashed for union3 */
  union3->length = 9999;
  memset(buf, 0xff, sizeof(buf));
  tt_int_op(len+1, ==, union3_encode(buf, sizeof(buf), union3));
  inp = ux("00100006""66666768696A");
  tt_mem_op(buf, ==, inp, len+1);

  union3_free(union3); union3 = NULL;
  union4_free(union4); union4 = NULL;

 end:
  union3_free(union3);
  union4_free(union4);
}

struct testcase_t union_defaults_tests[] = {
  { "truncated", test_unions_truncated, 0, NULL, NULL },
  { "invalid-default", test_union3_invalid, 0, NULL, NULL },
  { "invalid-ignore", test_union4_invalid, 0, NULL, NULL },
  { "encode-decode", test_union34_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
