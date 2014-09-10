
#include "test.h"
#include "valid/contexts.h"

static void
test_contexts_varsize_encdec(void *arg)
{
  count_t *count_four = NULL, *count_seven = NULL;
  varsize_t *varsize = NULL;
  uint8_t buf[15];
  const uint8_t *inp;
  unsigned i;
  (void)arg;

  count_four = count_new();
  count_seven = count_new();
  count_set_countval(count_four, 4);
  count_set_countval(count_seven, 7);

  inp = ux("12345678""616d7573696e6721");
  for (i = 0; i < 11; ++i)
    tt_int_op(-2, ==, varsize_parse(&varsize, inp, i, count_seven));
  for (i = 0; i < 8; ++i)
    tt_int_op(-2, ==, varsize_parse(&varsize, inp, i, count_four));

  tt_int_op(-1, ==, varsize_parse(&varsize, inp, 13, NULL));
  tt_int_op(11, ==, varsize_parse(&varsize, inp, 13, count_seven));
  tt_uint_op(0x12345678, ==, varsize_get_a(varsize));
  tt_int_op(7, ==, varsize_getlen_msg(varsize));

  for (i = 0; i < 11; ++i)
    tt_int_op(-2, ==, varsize_encode(buf, i, varsize, count_seven));
  tt_int_op(11, ==, varsize_encode(buf, 11, varsize, count_seven));
  varsize_free(varsize); varsize = NULL;
  tt_mem_op(buf, ==, inp, 11);

  tt_int_op(8, ==, varsize_parse(&varsize, inp, 8, count_four));
  tt_uint_op(0x12345678, ==, varsize_get_a(varsize));
  tt_int_op(4, ==, varsize_getlen_msg(varsize));

  memset(buf, 99, sizeof(buf));
  for (i = 0; i < 8; ++i)
    tt_int_op(-2, ==, varsize_encode(buf, i, varsize, count_four));
  tt_int_op(8, ==, varsize_encode(buf, 11, varsize, count_four));
  varsize_free(varsize); varsize = NULL;
  tt_mem_op(buf, ==, inp, 8);

 end:
  varsize_free(varsize);
  count_free(count_four);
  count_free(count_seven);
}

static void
test_contexts_varsize_invalid(void *arg)
{
  count_t *count = NULL;
  varsize_t *varsize = NULL;
  uint8_t buf[16];
  //  const uint8_t *inp;

  (void)arg;
  count = count_new();
  varsize = varsize_new();

  count->countval = 9;
  varsize_setlen_msg(varsize, 10);
  tt_int_op(-1, ==, varsize_encode(buf, sizeof(buf), varsize, count));

  count->countval = 10;
  tt_int_op(-1, ==, varsize_encode(buf, sizeof(buf), NULL, count));
  tt_int_op(-1, ==, varsize_encode(buf, sizeof(buf), varsize, NULL));

  tt_int_op(14, ==, varsize_encode(buf, sizeof(buf), varsize, count));

 end:
  varsize_free(varsize);
  count_free(count);
}

static void
test_contexts_varsize_accessors(void *arg)
{
  varsize_t *varsize = NULL;

  (void)arg;

  varsize = varsize_new();
  tt_ptr_op(varsize, !=, NULL);

  tt_int_op(varsize_get_a(varsize), ==, 0);
  tt_int_op(varsize_getlen_msg(varsize), ==, 0);

  tt_int_op(varsize_set_a(varsize, 1000), ==, 0);
  tt_int_op(varsize_setlen_msg(varsize, 10), ==, 0);

  tt_int_op(varsize_get_a(varsize), ==, 1000);
  tt_int_op(varsize_getlen_msg(varsize), ==, 10);

  memcpy(varsize_getarray_msg(varsize), "pineapples", 10);
  tt_int_op('e', ==, varsize_get_msg(varsize, 3));
  tt_int_op(0, ==, varsize_set_msg(varsize, 9, '!'));
  tt_mem_op("pineapple!", ==, varsize_getarray_msg(varsize), 10);
  tt_int_op(0, ==, varsize_add_msg(varsize, '?'));
  tt_mem_op("pineapple!?", ==, varsize_getarray_msg(varsize), 11);

 end:
  varsize_free(varsize);
}

static void
test_contexts_varsize_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  varsize_t *varsize = NULL;
  count_t *count = count_new();
  uint8_t buf[8] = {0};

  (void)arg;

  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, varsize_new());

  set_alloc_fail(1);
  tt_int_op(-1, ==, varsize_parse(&varsize, buf, sizeof(buf), count));

  set_alloc_fail(2);
  count_set_countval(count, 4);
  tt_int_op(-1, ==, varsize_parse(&varsize, buf, sizeof(buf), count));

  varsize = varsize_new();
  set_alloc_fail(1);
  tt_int_op(-1, ==, varsize_setlen_msg(varsize, 10));

  set_alloc_fail(1);
  tt_int_op(-1, ==, varsize_add_msg(varsize, 'x'));
  count->countval = 0;
  tt_int_op(0, ==, varsize_getlen_msg(varsize));
  tt_int_op(-1, ==, varsize_encode(buf, sizeof(buf), varsize, count));
  tt_int_op(1, ==, varsize_clear_errors(varsize));
  tt_int_op(4, ==, varsize_encode(buf, sizeof(buf), varsize, count));

  varsize_free(varsize); varsize = NULL;

 end:
  varsize_free(varsize);
  count_free(count);
#else
  (void)arg;
  tt_skip();
#endif
}

struct testcase_t contexts_varsize_tests[] = {
  { "encdec", test_contexts_varsize_encdec, 0, NULL, NULL },
  { "invalid", test_contexts_varsize_invalid, 0, NULL, NULL },
  { "accessors", test_contexts_varsize_accessors, 0, NULL, NULL },
  { "allocfail", test_contexts_varsize_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
