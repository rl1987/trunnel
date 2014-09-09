
#include "test.h"
#include "valid/contexts.h"

static void
test_contexts_uniontag_encdec(void *arg)
{
  flag_t *flag_one = NULL, *flag_zero = NULL;
  twosize_t *twosize = NULL;
  uint8_t buf[10];
  const uint8_t *inp;
  (void)arg;

  flag_one = flag_new();
  flag_zero = flag_new();
  flag_set_flagval(flag_one, 1);
  flag_set_flagval(flag_zero, 0);

  inp = ux("123456789ABCDEF0");
  tt_int_op(-2, ==, twosize_parse(&twosize, inp, 0, flag_zero));
  tt_int_op(-2, ==, twosize_parse(&twosize, inp, 1, flag_zero));
  tt_int_op(-2, ==, twosize_parse(&twosize, inp, 2, flag_zero));
  tt_int_op(-2, ==, twosize_parse(&twosize, inp, 3, flag_zero));
  tt_int_op(-2, ==, twosize_parse(&twosize, inp, 0, flag_one));
  tt_int_op(-2, ==, twosize_parse(&twosize, inp, 1, flag_one));

  tt_int_op(4, ==, twosize_parse(&twosize, inp, 8, flag_zero));
  tt_uint_op(0x12345678, ==, twosize_get_u_x(twosize));
  tt_int_op(-2, ==, twosize_encode(buf, 0, twosize, flag_zero));
  tt_int_op(-2, ==, twosize_encode(buf, 1, twosize, flag_zero));
  tt_int_op(-2, ==, twosize_encode(buf, 2, twosize, flag_zero));
  tt_int_op(-2, ==, twosize_encode(buf, 3, twosize, flag_zero));
  tt_int_op(4, ==, twosize_encode(buf, 4, twosize, flag_zero));
  twosize_free(twosize); twosize = NULL;
  tt_mem_op(buf, ==, inp, 4);

  tt_int_op(2, ==, twosize_parse(&twosize, inp, 5, flag_one));
  tt_uint_op(0x1234, ==, twosize_get_u_y(twosize));
  tt_int_op(-2, ==, twosize_encode(buf, 0, twosize, flag_one));
  tt_int_op(-2, ==, twosize_encode(buf, 1, twosize, flag_one));
  memset(buf, 0xff, sizeof(buf));
  tt_int_op(2, ==, twosize_encode(buf, 2, twosize, flag_one));
  twosize_free(twosize); twosize = NULL;
  tt_mem_op(buf, ==, inp, 2);

  tt_int_op(-1, ==, twosize_encode(buf, sizeof(buf), NULL, flag_one));

  inp = ux("FFFFFFFFFF");
  tt_int_op(-1, ==, twosize_parse(&twosize, inp, 5, NULL));
  tt_int_op(2, ==, twosize_parse(&twosize, inp, 5, flag_one));
  tt_uint_op(0xffff, ==, twosize_get_u_y(twosize));
  twosize_set_u_x(twosize, 0xf0000000);
  tt_int_op(-1, ==, twosize_encode(buf, sizeof(buf), twosize, flag_zero));
  twosize_clear_errors(twosize);
  tt_int_op(4, ==, twosize_encode(buf, sizeof(buf), twosize, flag_zero));
  twosize_free(twosize); twosize = NULL;
  tt_int_op(-1, ==, twosize_parse(&twosize, inp, 5, flag_zero));

  twosize = twosize_new();
  twosize->u_x = 0xf0000000;
  tt_int_op(-1, ==, twosize_encode(buf, sizeof(buf), twosize, flag_zero));
  twosize->u_x = 0x0f000000;
  tt_int_op(4, ==, twosize_encode(buf, sizeof(buf), twosize, flag_zero));

  tt_int_op(-1, ==, twosize_encode(buf, sizeof(buf), twosize, NULL));

  flag_zero->flagval = 2;
  tt_int_op(-1, ==, twosize_encode(buf, sizeof(buf), twosize, flag_zero));
  inp = ux("0000000000");
  tt_int_op(-1, ==, twosize_parse(&twosize, inp, 5, flag_zero));

 end:
  twosize_free(twosize);
  flag_free(flag_one);
  flag_free(flag_zero);
}

static void
test_contexts_uniontag_accessors(void *arg)
{
  twosize_t *twosize = NULL;

  (void)arg;

  twosize = twosize_new();
  tt_ptr_op(twosize, !=, NULL);

  tt_int_op(twosize_get_u_x(twosize), ==, 0);
  tt_int_op(twosize_get_u_y(twosize), ==, 0);

  tt_int_op(twosize_set_u_x(twosize,20), ==, 0);
  tt_int_op(twosize_set_u_y(twosize,30), ==, 0);

  tt_int_op(twosize_get_u_x(twosize), ==, 20);
  tt_int_op(twosize_get_u_y(twosize), ==, 30);

  tt_int_op(twosize_set_u_x(twosize, (uint32_t)-1), ==, -1);
  tt_int_op(twosize_get_u_x(twosize), ==, 20);

 end:
  twosize_free(twosize);
}


static void
test_contexts_uniontag_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  twosize_t *twosize = NULL;
  flag_t *flag = flag_new();
  uint8_t buf[4] = {0};

  (void)arg;

  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, twosize_new());

  set_alloc_fail(1);
  tt_int_op(-1, ==, twosize_parse(&twosize, buf, sizeof(buf), flag));

 end:
  twosize_free(twosize);
  flag_free(flag);
#else
  (void)arg;
  tt_skip();
#endif
}

struct testcase_t contexts_uniontag_tests[] = {
  { "encdec", test_contexts_uniontag_encdec, 0, NULL, NULL },
  { "accessors", test_contexts_uniontag_accessors, 0, NULL, NULL },
  { "allocfail", test_contexts_uniontag_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
