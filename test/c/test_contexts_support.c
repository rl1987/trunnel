
#include "test.h"
#include "valid/contexts.h"

static void
test_contexts_support_point_encdec(void *arg)
{
  point_t *point = NULL;
  uint8_t buf[10];
  const uint8_t *inp;
  (void)arg;

  inp = ux("ABCDEF");
  tt_int_op(-2, ==, point_parse(&point, inp, 0));
  tt_int_op(-2, ==, point_parse(&point, inp, 1));
  tt_int_op(2, ==, point_parse(&point, inp, 3));
  tt_int_op(0xab, ==, point_get_x(point));
  tt_int_op(0xcd, ==, point_get_y(point));

  tt_int_op(2, ==, point_encode(buf, sizeof(buf), point));
  tt_mem_op(buf, ==, inp, 2);

  tt_int_op(-2, ==, point_encode(buf, 0, point));
  tt_int_op(-2, ==, point_encode(buf, 1, point));

  point->x = 255;
  tt_int_op(-1, ==, point_encode(buf, 2, point));

  tt_int_op(-1, ==, point_set_x(point, 255));
  tt_int_op(0, ==, point_set_x(point, 250));
  tt_int_op(-1, ==, point_encode(buf, 2, point));
  tt_int_op(1, ==, point_clear_errors(point));
  tt_int_op(2, ==, point_encode(buf, 2, point));

  point_free(point);
  point = NULL;

  inp = ux("FFFF");
  tt_int_op(-1, ==, point_parse(&point, inp, 2));
  tt_ptr_op(NULL, ==, point);

  tt_int_op(-1, ==, point_encode(buf, sizeof(buf), NULL));

 end:
  point_free(point);
}

static void
test_contexts_support_accessors(void *arg)
{
  point_t *point = NULL;
  flag_t *flag = NULL;
  count_t *count = NULL;

  (void)arg;

  point = point_new();
  flag = flag_new();
  count = count_new();
  tt_ptr_op(flag, !=, NULL);
  tt_ptr_op(point, !=, NULL);
  tt_ptr_op(count, !=, NULL);

  tt_int_op(flag_get_flagval(flag), ==, 0);
  tt_int_op(point_get_x(point), ==, 0);
  tt_int_op(point_get_y(point), ==, 0);
  tt_int_op(count_get_countval(count), ==, 0);

  tt_int_op(flag_set_flagval(flag, 1), ==, 0);
  tt_int_op(point_set_x(point, 64), ==, 0);
  tt_int_op(point_set_y(point, 65), ==, 0);
  tt_int_op(count_set_countval(count, 10), ==, 0);

  tt_int_op(flag_get_flagval(flag), ==, 1);
  tt_int_op(point_get_x(point), ==, 64);
  tt_int_op(point_get_y(point), ==, 65);
  tt_int_op(count_get_countval(count), ==, 10);

  tt_int_op(flag->flagval, ==, 1);
  tt_int_op(point->x, ==, 64);
  tt_int_op(point->y, ==, 65);
  tt_int_op(count->countval, ==, 10);

 end:
  point_free(point);
  flag_free(flag);
  count_free(count);
}


static void
test_contexts_support_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  point_t *point = NULL;
  flag_t *flag = NULL;
  count_t *count = NULL;
  uint8_t buf[8] = {0};

  (void)arg;

  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, point_new());
  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, flag_new());
  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, count_new());

  set_alloc_fail(1);
  tt_int_op(-1, ==, point_parse(&point, buf, sizeof(buf)));

 end:
  point_free(point);
  flag_free(flag);
  count_free(count);
#else
  (void)arg;
  tt_skip();
#endif
}

struct testcase_t contexts_support_tests[] = {
  { "point/encdec", test_contexts_support_point_encdec, 0, NULL, NULL },
  { "accessors", test_contexts_support_accessors, 0, NULL, NULL },
  { "allocfail", test_contexts_support_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
