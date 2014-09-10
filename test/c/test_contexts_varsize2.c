
#include "test.h"
#include "valid/contexts.h"

static void
test_contexts_varsize2_encdec(void *arg)
{
  count_t *count_two = NULL, *count_three = NULL;
  varsize2_t *varsize2 = NULL;
  uint8_t buf[15];
  const uint8_t *inp;
  unsigned i;
  (void)arg;

  count_two = count_new();
  count_three = count_new();
  count_set_countval(count_two, 2);
  count_set_countval(count_three, 3);

  inp = ux("12345678""616d7573696e67");
  for (i = 0; i < 10; ++i)
    tt_int_op(-2, ==, varsize2_parse(&varsize2, inp, i, count_three));
  for (i = 0; i < 8; ++i)
    tt_int_op(-2, ==, varsize2_parse(&varsize2, inp, i, count_two));

  tt_int_op(-1, ==, varsize2_parse(&varsize2, inp, 13, NULL));
  tt_int_op(10, ==, varsize2_parse(&varsize2, inp, 13, count_three));
  tt_uint_op(0x12345678, ==, varsize2_get_a(varsize2));
  tt_int_op(3, ==, varsize2_getlen_msg(varsize2));

  for (i = 0; i < 10; ++i)
    tt_int_op(-2, ==, varsize2_encode(buf, i, varsize2, count_three));
  tt_int_op(10, ==, varsize2_encode(buf, 11, varsize2, count_three));
  varsize2_free(varsize2); varsize2 = NULL;
  tt_mem_op(buf, ==, inp, 10);

  tt_int_op(8, ==, varsize2_parse(&varsize2, inp, 8, count_two));
  tt_uint_op(0x12345678, ==, varsize2_get_a(varsize2));
  tt_int_op(2, ==, varsize2_getlen_msg(varsize2));

  memset(buf, 99, sizeof(buf));
  for (i = 0; i < 8; ++i)
    tt_int_op(-2, ==, varsize2_encode(buf, i, varsize2, count_two));
  tt_int_op(8, ==, varsize2_encode(buf, 11, varsize2, count_two));
  varsize2_free(varsize2); varsize2 = NULL;
  tt_mem_op(buf, ==, inp, 8);

 end:
  varsize2_free(varsize2);
  count_free(count_two);
  count_free(count_three);
}

static void
test_contexts_varsize2_invalid(void *arg)
{
  count_t *count = NULL;
  varsize2_t *varsize2 = NULL;
  uint8_t buf[32];
  unsigned u;

  (void)arg;
  count = count_new();
  varsize2 = varsize2_new();

  count->countval = 9;
  varsize2_setlen_msg(varsize2, 10);
  tt_int_op(-1, ==, varsize2_encode(buf, sizeof(buf), varsize2, count));
  for (u = 0; u < 10; ++u) {
    varsize2_set_msg(varsize2, u, point_new());
  }
  tt_int_op(-1, ==, varsize2_encode(buf, sizeof(buf), varsize2, count));

  count->countval = 10;
  tt_int_op(-1, ==, varsize2_encode(buf, sizeof(buf), NULL, count));
  tt_int_op(-1, ==, varsize2_encode(buf, sizeof(buf), varsize2, NULL));

  tt_int_op(24, ==, varsize2_encode(buf, sizeof(buf), varsize2, count));

 end:
  varsize2_free(varsize2);
  count_free(count);
}

static void
test_contexts_varsize2_accessors(void *arg)
{
  varsize2_t *varsize2 = NULL;
  count_t *count = count_new();
  point_t *p = NULL;
  uint8_t buf[32];

  (void)arg;

  varsize2 = varsize2_new();
  tt_ptr_op(varsize2, !=, NULL);

  tt_int_op(varsize2_get_a(varsize2), ==, 0);
  tt_int_op(varsize2_getlen_msg(varsize2), ==, 0);

  tt_int_op(varsize2_set_a(varsize2, 1000), ==, 0);
  tt_int_op(varsize2_setlen_msg(varsize2, 2), ==, 0);

  tt_int_op(varsize2_get_a(varsize2), ==, 1000);
  tt_int_op(varsize2_getlen_msg(varsize2), ==, 2);

  varsize2_getarray_msg(varsize2)[0] = point_new();
  varsize2_set_msg(varsize2, 1, point_new());
  varsize2_add_msg(varsize2, point_new());

  tt_int_op(varsize2_getlen_msg(varsize2), ==, 3);

  varsize2_get_msg(varsize2, 0)->x = 1;
  varsize2_get_msg(varsize2, 0)->y = 2;
  varsize2_getarray_msg(varsize2)[1]->x = 3;
  varsize2_getarray_msg(varsize2)[1]->y = 4;
  p = point_new();
  p->x = 10;
  p->y = 11;
  tt_int_op(0, ==, varsize2_set_msg(varsize2, 2, p));
  p = NULL;

  count->countval = 3;
  tt_int_op(10, ==, varsize2_encode(buf, sizeof(buf), varsize2, count));

 end:
  varsize2_free(varsize2);
  point_free(p);
  count_free(count);
}

static void
test_contexts_varsize2_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  varsize2_t *varsize2 = NULL;
  count_t *count = count_new();
  uint8_t buf[8] = {0};

  (void)arg;

  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, varsize2_new());

  set_alloc_fail(1);
  tt_int_op(-1, ==, varsize2_parse(&varsize2, buf, sizeof(buf), count));

  set_alloc_fail(2);
  count_set_countval(count, 4);
  tt_int_op(-1, ==, varsize2_parse(&varsize2, buf, sizeof(buf), count));

  varsize2 = varsize2_new();
  set_alloc_fail(1);
  tt_int_op(-1, ==, varsize2_setlen_msg(varsize2, 10));

  set_alloc_fail(1);
  tt_int_op(-1, ==, varsize2_add_msg(varsize2, NULL));
  count->countval = 0;
  tt_int_op(0, ==, varsize2_getlen_msg(varsize2));
  tt_int_op(-1, ==, varsize2_encode(buf, sizeof(buf), varsize2, count));
  tt_int_op(1, ==, varsize2_clear_errors(varsize2));
  tt_int_op(4, ==, varsize2_encode(buf, sizeof(buf), varsize2, count));

  varsize2_free(varsize2); varsize2 = NULL;

 end:
  varsize2_free(varsize2);
  count_free(count);
#else
  (void)arg;
  tt_skip();
#endif
}

struct testcase_t contexts_varsize2_tests[] = {
  { "encdec", test_contexts_varsize2_encdec, 0, NULL, NULL },
  { "invalid", test_contexts_varsize2_invalid, 0, NULL, NULL },
  { "accessors", test_contexts_varsize2_accessors, 0, NULL, NULL },
  { "allocfail", test_contexts_varsize2_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
