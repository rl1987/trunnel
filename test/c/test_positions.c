#include "test.h"

#include "valid/positions.h"

static void
test_pos_invalid(void *arg)
{
  haspos_t *hp = NULL, *hp2 = NULL;
  uint8_t buf[64];
  int i;
  (void)arg;

  /* Encode invalid */
  tt_int_op(-1, ==, haspos_encode(buf, sizeof(buf), NULL));
  hp = haspos_new();
  tt_int_op(-1, ==, haspos_encode(buf, sizeof(buf), hp));
  haspos_set_s1(hp, "Foo");
  tt_int_op(-1, ==, haspos_encode(buf, sizeof(buf), hp));
  haspos_set_s2(hp, "Bar");
  tt_int_op(12, ==, haspos_encode(buf, sizeof(buf), hp));

  /* Encode truncated */
  for (i = 0; i < 12; ++i)
    tt_int_op(-2, ==, haspos_encode(buf, i, hp));
  tt_int_op(12, ==, haspos_encode(buf, 12, hp));

  /* Parse truncated */
  for (i = 0; i < 12; ++i)
    tt_int_op(-2, ==, haspos_parse(&hp2, buf, i));

 end:
  haspos_free(hp);
}

static void
test_pos_encdec(void *arg)
{
  haspos_t *hp = NULL, *hp2 = NULL;
  uint8_t buf[64];
  (void)arg;

  hp = haspos_new();
  haspos_set_s1(hp, "hello");
  haspos_set_s2(hp, "world");
  haspos_set_x(hp, 3);
  tt_int_op(16, ==, haspos_encode(buf, sizeof(buf), hp));
  tt_mem_op("hello\0world\0\0\0\0\x03", ==, buf, 16);

  tt_int_op(16, ==, haspos_parse(&hp2, buf, sizeof(buf)));
  tt_str_op("hello", ==, haspos_get_s1(hp2));
  tt_str_op("world", ==, haspos_get_s2(hp2));
  tt_int_op(3, ==, haspos_get_x(hp));
  tt_ptr_op(buf + 6, ==, haspos_get_pos1(hp2));
  tt_ptr_op(buf + 12, ==, haspos_get_pos2(hp2));

 end:
  haspos_free(hp);
  haspos_free(hp2);
}

static void
test_pos_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  haspos_t *hp = NULL;
  const uint8_t inp[] = "hello\0world\0\0\0\0\x03";
  uint8_t buf[32];
  (void)arg;

  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, haspos_new());

  set_alloc_fail(1);
  tt_int_op(-1, ==, haspos_parse(&hp, inp, sizeof(inp)));

  set_alloc_fail(2);
  tt_int_op(-1, ==, haspos_parse(&hp, inp, sizeof(inp)));

  set_alloc_fail(3);
  tt_int_op(-1, ==, haspos_parse(&hp, inp, sizeof(inp)));

  hp = haspos_new();
  tt_assert(hp);
  set_alloc_fail(1);
  tt_int_op(-1, ==, haspos_set_s1(hp,"Hi"));
  tt_int_op(0, ==, haspos_set_s1(hp,"Hi"));

  set_alloc_fail(1);
  tt_int_op(-1, ==, haspos_set_s2(hp,"Hi"));
  tt_int_op(0, ==, haspos_set_s2(hp,"Hi"));

  tt_int_op(-1, ==, haspos_encode(buf, sizeof(buf), hp));
  haspos_clear_errors(hp);
  tt_int_op(10, ==, haspos_encode(buf, sizeof(buf), hp));

  haspos_free(hp); hp = NULL;

 end:
  haspos_free(hp);
#else
  (void)arg;
  tt_skip();
#endif
}

struct testcase_t positions_tests[] = {
  { "invalid", test_pos_invalid, 0, NULL, NULL },
  { "encdec", test_pos_encdec, 0, NULL, NULL },
  { "allocfail", test_pos_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
