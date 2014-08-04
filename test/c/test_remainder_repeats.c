#include "test.h"

static void
test_repeats_invalid32(void *arg)
{
  extends3_t *extends3 = NULL;
  uint8_t buf[128];
  (void)arg;

  /* Encoding NULL fails. */
  tt_int_op(-1, ==, extends3_encode(buf, sizeof(buf), NULL));

  /* Encoding with a missing field fails */
  extends3 = extends3_new();
  tt_int_op(-1, ==, extends3_encode(buf, sizeof(buf), extends3));

  extends3->a = strdup("bedtime");
  tt_int_op(8, ==, extends3_encode(buf, sizeof(buf), extends3));
  tt_str_op((char*)buf, ==, "bedtime");

  extends3_free(extends3); extends3 = NULL;

 end:
  extends3_free(extends3);
}

static void
test_repeats_encdec32(void *arg)
{
  /* Also tests truncated cases */

  const uint8_t *inp;
  uint8_t buf[128];
  extends3_t *extends3 = NULL;
  (void)arg;

  inp = ux("00" "00000101" "00010000");

  tt_int_op(-2, ==, extends3_parse(&extends3, inp, 0));
  tt_int_op(1, ==, extends3_parse(&extends3, inp, 1));
  tt_str_op("", ==, extends3->a);
  tt_int_op(0, ==, extends3_get_remainder_len(extends3));

  tt_int_op(-2, ==, extends3_encode(buf, 0, extends3));
  memset(buf, 0xff, sizeof(buf));
  tt_int_op(1, ==, extends3_encode(buf, 1, extends3));
  tt_mem_op(buf, ==, inp, 1);
  extends3_free(extends3); extends3 = NULL;

  tt_int_op(-1, ==, extends3_parse(&extends3, inp, 2));
  tt_int_op(-1, ==, extends3_parse(&extends3, inp, 3));
  tt_int_op(-1, ==, extends3_parse(&extends3, inp, 4));

  tt_int_op(5, ==, extends3_parse(&extends3, inp, 5));
  tt_str_op("", ==, extends3->a);
  tt_int_op(1, ==, extends3_get_remainder_len(extends3));
  tt_int_op(257, ==, extends3_get_remainder(extends3, 0));

  memset(buf, 0xff, sizeof(buf));
  tt_int_op(-2, ==, extends3_encode(buf, 4, extends3));
  tt_int_op(5, ==, extends3_encode(buf, 5, extends3));
  tt_mem_op(buf, ==, inp, 5);
  extends3_free(extends3); extends3 = NULL;

  tt_int_op(-1, ==, extends3_parse(&extends3, inp, 6));
  tt_int_op(-1, ==, extends3_parse(&extends3, inp, 7));
  tt_int_op(-1, ==, extends3_parse(&extends3, inp, 8));

  tt_int_op(9, ==, extends3_parse(&extends3, inp, 9));
  tt_str_op("", ==, extends3->a);
  tt_int_op(2, ==, extends3_get_remainder_len(extends3));
  tt_int_op(257, ==, extends3_get_remainder(extends3, 0));
  tt_int_op(65536, ==, extends3_get_remainder(extends3, 1));

  memset(buf, 0xff, sizeof(buf));
  tt_int_op(-2, ==, extends3_encode(buf, 8, extends3));
  tt_int_op(9, ==, extends3_encode(buf, 9, extends3));
  tt_mem_op(buf, ==, inp, 9);

  /* Try other accessors */
  extends3_set_remainder(extends3, 0, 0x9999);
  extends3_add_remainder(extends3, 0xffffffff);

  tt_int_op(-2, ==, extends3_encode(buf, 12, extends3));
  tt_int_op(13, ==, extends3_encode(buf, 13, extends3));
  inp = ux("00" "00009999" "00010000" "FFFFFFFF");
  tt_mem_op(buf, ==, inp, 13);

 end:
  extends3_free(extends3);
}

static void
test_repeats_invalid_struct(void *arg)
{
  extends4_t *extends4 = NULL;
  uint8_t buf[128];
  (void)arg;

  /* Encoding NULL fails. */
  tt_int_op(-1, ==, extends4_encode(buf, sizeof(buf), NULL));

  /* Encoding with a missing field fails */
  extends4 = extends4_new();
  tt_int_op(-1, ==, extends4_encode(buf, sizeof(buf), extends4));

  extends4->a = strdup("bedtime");
  tt_int_op(8, ==, extends4_encode(buf, sizeof(buf), extends4));
  tt_str_op((char*)buf, ==, "bedtime");

  /* Encoding with a bad struct fails. */
  extends4_add_remainder(extends4, NULL);
  tt_int_op(-1, ==, extends4_encode(buf, sizeof(buf), extends4));

  extends4_free(extends4); extends4 = NULL;

 end:
  extends4_free(extends4);
}

static void
test_repeats_encdec_struct(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[128];
  extends4_t *extends4 = NULL;
  numbers_t *n, *n2;
  int i;
  (void)arg;

  inp = ux("00"
           "05" "0004" "00000003" "00000000""00000002"
           "08" "0009" "0000000A" "00000000""0000000B"
           );

  /* Try the truncated cases */
  for (i=0;i<31;++i) {
    int errcode = (i == 0) ? -2 : -1;
    if ((i-1) % 15 == 0)
      continue; /* Not truncated. */
    tt_int_op(errcode, ==, extends4_parse(&extends4, inp, i));
  }

  /* Now try the full cases. */
  /* First, parse no structs */
  tt_int_op(1, ==, extends4_parse(&extends4, inp, 1));
  tt_str_op("", ==, extends4->a);
  tt_int_op(0, ==, extends4_get_remainder_len(extends4));

  memset(buf, 0xff, sizeof(buf));
  tt_int_op(1, ==, extends4_encode(buf, 1, extends4));
  tt_mem_op(buf, ==, inp, 1);
  extends4_free(extends4); extends4 = NULL;

  /* Parse one of the structs. */
  tt_int_op(16, ==, extends4_parse(&extends4, inp, 16));
  tt_str_op("", ==, extends4->a);
  tt_int_op(1, ==, extends4_get_remainder_len(extends4));
  n = extends4_get_remainder(extends4, 0);
  tt_assert(n);
  tt_int_op(n->i8, ==, 5);
  tt_int_op(n->i16, ==, 4);
  tt_int_op(n->i32, ==, 3);
  tt_assert(n->i64 == 2);

  memset(buf, 0xff, sizeof(buf));
  tt_int_op(-2, ==, extends4_encode(buf, 0, extends4));
  tt_int_op(-2, ==, extends4_encode(buf, 15, extends4));
  tt_int_op(16, ==, extends4_encode(buf, 16, extends4));
  tt_mem_op(buf, ==, inp, 16);
  extends4_free(extends4); extends4 = NULL;

  /* Parse both structs. */
  tt_int_op(31, ==, extends4_parse(&extends4, inp, 31));
  tt_str_op("", ==, extends4->a);
  tt_int_op(2, ==, extends4_get_remainder_len(extends4));
  n = extends4_get_remainder(extends4, 0);
  tt_assert(n);
  tt_int_op(n->i8, ==, 5);
  tt_int_op(n->i16, ==, 4);
  tt_int_op(n->i32, ==, 3);
  tt_assert(n->i64 == 2);
  n2 = extends4_get_remainder(extends4, 1);
  tt_assert(n2);
  tt_int_op(n2->i8, ==, 8);
  tt_int_op(n2->i16, ==, 9);
  tt_int_op(n2->i32, ==, 10);
  tt_assert(n2->i64 == 11);

  memset(buf, 0xff, sizeof(buf));
  tt_int_op(-2, ==, extends4_encode(buf, 30, extends4));
  tt_int_op(31, ==, extends4_encode(buf, 31, extends4));
  tt_mem_op(buf, ==, inp, 31);

  /* Try other accessors */
  extends4_set0_remainder(extends4, 0, n2);
  extends4_set0_remainder(extends4, 1, n);
  n = numbers_new();
  --n->i64;
  extends4_add_remainder(extends4, n);

  tt_int_op(-2, ==, extends4_encode(buf, 45, extends4));
  tt_int_op(46, ==, extends4_encode(buf, 46, extends4));
  inp = ux("00"
           "08" "0009" "0000000A" "00000000""0000000B"
           "05" "0004" "00000003" "00000000""00000002"
           "00" "0000" "00000000" "FFFFFFFF""FFFFFFFF"
           );
  tt_mem_op(buf, ==, inp, 46);

 end:
  extends4_free(extends4);
}

struct testcase_t repeats_tests[] = {
  { "invalid-u32", test_repeats_invalid32, 0, NULL, NULL },
  { "encode-decode-u32", test_repeats_encdec32, 0, NULL, NULL },
  { "invalid-struct", test_repeats_invalid_struct, 0, NULL, NULL },
  { "encode-decode-struct", test_repeats_encdec_struct, 0, NULL, NULL },

  END_OF_TESTCASES
};
