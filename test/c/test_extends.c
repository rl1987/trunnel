#include "test.h"

static void
test_extends_varlength(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[16] = { 0 };
  extends_t *extends1 = NULL;
  extends2_t *extends2 = NULL;
  unsigned i;
  (void)arg;

  /* Too short, or truncated during string. */
  inp = ux("74657374696e6700010203");
  for (i = 0; i < 8; ++i) {
    tt_int_op(-2, ==, extends_parse(&extends1, inp, i));
    tt_int_op(-2, ==, extends2_parse(&extends2, inp, i));
    tt_ptr_op(NULL, ==, extends1);
    tt_ptr_op(NULL, ==, extends2);
  }

  /* Success */
  for (i = 8; i <= 11; ++i) {
    tt_int_op(i, ==, extends_parse(&extends1, inp, i));
    tt_ptr_op(extends1, !=, NULL);
    tt_str_op(extends1->a, ==, "testing");
    tt_int_op(extends_get_remainder_len(extends1), ==, i-8);
    tt_mem_op(extends1->remainder.elts_, ==, inp+8, i-8);

    tt_int_op(i, ==, extends2_parse(&extends2, inp, i));
    tt_ptr_op(extends2, !=, NULL);
    tt_str_op(extends2->a, ==, "testing");
    tt_int_op(extends2_get_remainder_len(extends2), ==, i-8);
    tt_mem_op(extends2->remainder.elts_, ==, "\x01\x02\x03", i-8);
    tt_int_op(extends2->remainder.elts_[extends2->remainder.n_], ==, 0);

    memset(buf, 0xff, sizeof(buf));
    tt_int_op(i, ==, extends_encode(buf, i, extends1));
    tt_mem_op(inp, ==, buf, i);
    extends_free(extends1); extends1 = NULL;

    memset(buf, 0xff, sizeof(buf));
    tt_int_op(i, ==, extends2_encode(buf, i, extends2));
    tt_mem_op(inp, ==, buf, i);
    extends2_free(extends2); extends2 = NULL;
  }

  tt_int_op(11, ==, extends_parse(&extends1, inp, 11));
  tt_int_op(11, ==, extends2_parse(&extends2, inp, 11));

  /* Truncated on encode */
  for (i = 0; i < 11; ++i) {
    tt_int_op(-2, ==, extends_encode(buf, i, extends1));
    tt_int_op(-2, ==, extends2_encode(buf, i, extends2));
  }

  extends_free(extends1); extends1 = NULL;
  extends2_free(extends2); extends2 = NULL;

 end:
  extends_free(extends1);
  extends2_free(extends2);
}

static void
test_extends_invalid(void *arg)
{
  uint8_t buf[16];
  extends_t *extends = NULL;
  (void)arg;

  tt_int_op(-1, ==, extends_encode(buf, 16, NULL));

  /* no nul-terminated string */
  extends = extends_new();
  tt_int_op(-1, ==, extends_encode(buf, 16, extends));
  /* Fill things in. */
  extends->a = strdup("XYZZY");
  extends->remainder.elts_ = calloc(3, 1);
  extends->remainder.allocated_ = extends->remainder.n_ = 3;
  tt_int_op(9, ==, extends_encode(buf, 16, extends));

 end:
  extends_free(extends);
}

static void
test_extends2_invalid(void *arg)
{
  uint8_t buf[16];
  extends2_t *extends = NULL;
  (void)arg;

  tt_int_op(-1, ==, extends2_encode(buf, 16, NULL));

  /* no nul-terminated string */
  extends = extends2_new();
  tt_int_op(-1, ==, extends2_encode(buf, 16, extends));
  extends2_set_a(extends, "XYZZY");

  extends2_add_remainder(extends, 'a');
  extends2_add_remainder(extends, 'b');
  extends2_add_remainder(extends, 'c');
  tt_int_op(9, ==, extends2_encode(buf, 16, extends));
 end:
  extends2_free(extends);
}

static void
test_extends_encdec(void *arg)
{
  uint8_t buf[32] = { 0 };
  uint8_t buf2[32] = { 0 };
  extends_t *extends1 = NULL;
  (void)arg;

  memset(buf,0,32);
  memcpy(buf+1,"HelloWorld!",11);
  tt_int_op(11, ==, extends_parse(&extends1, buf, 11));
  tt_ptr_op(extends1, !=, 0);
  tt_str_op(extends1->a, ==, "");
  tt_int_op(extends_get_remainder_len(extends1), ==, 10);
  tt_int_op('H', ==, extends_get_remainder(extends1, 0));
  extends_set_remainder(extends1, 0, (uint8_t)'Z');
  tt_mem_op(extends1->remainder.elts_, ==, "ZelloWorld", 10);
  extends_set_remainder(extends1, 0, (uint8_t)'H');
  extends_add_remainder(extends1, '!');
  tt_int_op(12, ==, extends_encode(buf2, 12, extends1));
  tt_mem_op(buf, ==, buf2, 11);
  extends_free(extends1); extends1 = NULL;

 end:
  extends_free(extends1);
}

struct testcase_t extends_tests[] = {
  { "varlength", test_extends_varlength, 0, NULL, NULL },
  { "invalid", test_extends_invalid, 0, NULL, NULL },
  { "invalid2", test_extends2_invalid, 0, NULL, NULL },
  { "encode-decode", test_extends_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
