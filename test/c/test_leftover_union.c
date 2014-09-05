#include "test.h"
#include "valid/leftover.h"

static const char OK_CASE1[] =
  "01" "99" "07""77665544332211";

static const char OK_CASE2A[] =
  "02" "" "07""77665544332211";

static const char OK_CASE2B[] =
  "02" "90902526"  "07""01020304050607";
/*
static const char OK_CASE3A[] =
  "03" "" "03"  "07""77665544332211";

static const char OK_CASE3B[] =
  "03" "222324" "FF" "07""77665544332211";
*/
static const char OK_CASE4A[] =
  "04" "FF" "" "07""01020304050607";

static const char OK_CASE4B[] =
  "04" "FF" "90901111" "07""01020304050607";

static const char BAD1[] =
  "FF" "FFFFFF" "07" "01020304050607";

static const char BAD2[] =
  "01" "99" "FF" "77665544332211";

static const char BAD3[] =
  "01" "99" "FF" "07" "77665544332211";

static const char BAD4[] =
  "01" "99" "FF" "77665544332211";

static const char BAD5[] =
  "04" "99" "FF" "07""77665544332211";

static void
test_lo_union_truncated(void *arg)
{
  const char *ok[] = {
    OK_CASE1,
    OK_CASE2A, OK_CASE2B,
    //    OK_CASE3A, OK_CASE3B,
    OK_CASE4A, OK_CASE4B,
    NULL
  };
  unsigned int i, j;
  unlo_t *obj = NULL;
  uint8_t buf[128];
  (void)arg;

  for (i = 0; ok[i]; ++i) {

    const uint8_t *inp = ux(ok[i]);
    const size_t len = strlen(ok[i]) / 2;
    for (j = 0; j < len; ++j) {
      /* XXXX it would be nice to guarantee -2 */
      tt_int_op(unlo_parse(&obj, inp, j), <, 0);
      tt_assert(!obj);
    }
    tt_int_op(len, ==, unlo_parse(&obj, inp, len));
    for (j = 0; j < len; ++j) {
      tt_int_op(-2, ==, unlo_encode(buf, j, obj));
    }
    tt_want_int_op(len, ==, unlo_encode(buf, len, obj));
    tt_want_mem_op(buf, ==, inp, len);
    unlo_free(obj); obj = NULL;
  }
 end:
  unlo_free(obj);
}

static void
test_lo_union_invalid(void *arg)
{
  const char *bad[] = { BAD1, BAD2, BAD3, BAD4, BAD5, NULL };
  int i;
  unlo_t *obj;
  uint8_t buf[64];

  (void)arg;
  for (i = 0; bad[i]; ++i) {
    const uint8_t *inp = ux(bad[i]);
    const size_t len = strlen(bad[i]) / 2;
      /* XXXX it would be nice to guarantee -1 */
    tt_int_op(unlo_parse(&obj, inp, len), <, 0);
  }

  /* encode null fails */
  tt_int_op(-1, ==, unlo_encode(buf, sizeof(buf), NULL));

  /* Bad tag. */
  obj = unlo_new();
  unlo_set_tag(obj, 9);
  tt_int_op(-1, ==, unlo_encode(buf, sizeof(buf), obj));

  /* Bad length */
  unlo_set_tag(obj, 1);
  unlo_set_leftoverlen(obj, 5);
  unlo_setlen_leftovers(obj, 5);
  tt_int_op(-1, ==, unlo_encode(buf, sizeof(buf), obj));

  unlo_set_leftoverlen(obj, 7);
  tt_int_op(-1, ==, unlo_encode(buf, sizeof(buf), obj));

  unlo_setlen_leftovers(obj, 7);
  tt_int_op(10, ==, unlo_encode(buf, sizeof(buf), obj));

  unlo_add_leftovers(obj, 1);
  unlo_set_leftoverlen(obj, 8);
  tt_int_op(-1, ==, unlo_encode(buf, sizeof(buf), obj));
  tt_int_op(-2, ==, unlo_encode(buf, 10, obj));

 end:
  unlo_free(obj);
}


static void
test_lo_union_accessors(void *arg)
{
  unlo_t *obj = NULL;
  uint8_t buf[64];
  int i;
#define GET(s) tt_int_op(strlen(s)/2, ==, unlo_parse(&obj, ux(s), strlen(s)/2))

  (void)arg;
  GET(OK_CASE1);
  tt_int_op(1, ==, unlo_get_tag(obj));
  tt_int_op(7, ==, unlo_get_leftoverlen(obj));
  tt_int_op(7, ==, unlo_getlen_leftovers(obj));
  tt_mem_op(ux("77665544332211"), ==, unlo_getarray_leftovers(obj), 7);
  tt_int_op(0x55, ==, unlo_get_leftovers(obj, 2));
  tt_int_op(0x99, ==, unlo_get_u_x(obj));
  tt_int_op(0, ==, unlo_set_u_x(obj, 0x55));
  tt_int_op(10, ==, unlo_encode(buf, sizeof(buf), obj));
  tt_mem_op(ux("01" "55" "07""77665544332211"), ==, buf, 10);

  tt_int_op(0, ==, unlo_set_tag(obj, 4));
  tt_int_op(0, ==, unlo_set_u_byte(obj, 255));
  tt_int_op(255, ==, unlo_get_u_byte(obj));
  tt_int_op(0, ==, unlo_getlen_u_z(obj));
  tt_int_op(0, ==, unlo_add_u_z(obj, 0x9090));
  tt_int_op(0, ==, unlo_add_u_z(obj, 0x1111));
  for (i = 0; i < 7; ++i)
    unlo_set_leftovers(obj, i, i+1);
  memset(buf, 0, sizeof(buf));
  tt_int_op(14, ==, unlo_encode(buf, sizeof(buf), obj));
  tt_mem_op(ux(OK_CASE4B), ==, buf, 14);
  tt_int_op(0x9090, ==, unlo_get_u_z(obj, 0));
  tt_int_op(0x1111, ==, unlo_getarray_u_z(obj)[1]);
  tt_int_op(2, ==, unlo_getlen_u_z(obj));
  tt_int_op(0, ==, unlo_set_u_z(obj, 1, 0x2223));
  tt_int_op(14, ==, unlo_encode(buf, sizeof(buf), obj));
  tt_mem_op(ux("04" "FF" "90902223" "07""01020304050607"), ==, buf, 14);
  tt_int_op(0, ==, unlo_setlen_u_z(obj, 3));
  tt_int_op(16, ==, unlo_encode(buf, sizeof(buf), obj));
  tt_mem_op(ux("04" "FF" "909022230000" "07""01020304050607"), ==, buf, 14);

  unlo_set_tag(obj, 2);
  unlo_setlen_leftovers(obj, 0);
  for (i = 0; i < 7; ++i)
    unlo_add_leftovers(obj, i+1);
  unlo_setlen_u_y(obj, 2);
  unlo_set_u_y(obj, 0, 0x90);
  tt_int_op(0, ==, unlo_get_u_y(obj, 1));
  unlo_set_u_y(obj, 1, 0x90);
  unlo_add_u_y(obj, 0x25);
  unlo_add_u_y(obj, 0x26);
  tt_mem_op(ux("90902526"), ==, unlo_getarray_u_y(obj), 4);

  tt_int_op(13, ==, unlo_encode(buf, sizeof(buf), obj));
  tt_mem_op(ux(OK_CASE2B), ==, buf, 13);
  tt_int_op(4, ==, unlo_getlen_u_y(obj));

  tt_int_op(-1, ==, unlo_setlen_leftovers(obj, 1024));
  tt_int_op(-1, ==, unlo_encode(buf, sizeof(buf), obj));
  unlo_clear_errors(obj);
  tt_int_op(13, ==, unlo_encode(buf, sizeof(buf), obj));

  tt_int_op(0, ==, unlo_setlen_leftovers(obj, 255));
  tt_int_op(-1, ==, unlo_add_leftovers(obj, 5));

 end:
  unlo_free(obj);
}

static void
test_lo_union_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  unlo_t *obj;
  (void)arg;

  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_parse(&obj, ux(OK_CASE1), strlen(OK_CASE1)/2));
  set_alloc_fail(2);
  tt_int_op(-1, ==, unlo_parse(&obj, ux(OK_CASE1), strlen(OK_CASE1)/2));

  set_alloc_fail(2);
  tt_int_op(-1, ==, unlo_parse(&obj, ux(OK_CASE2B), strlen(OK_CASE2B)/2));

  set_alloc_fail(2);
  tt_int_op(-1, ==, unlo_parse(&obj, ux(OK_CASE4B), strlen(OK_CASE4B)/2));


  obj = unlo_new();
  tt_assert(obj);
  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_add_u_y(obj, 1));
  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_add_u_z(obj, 1));
  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_add_leftovers(obj, 1));

  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_setlen_u_y(obj, 1));
  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_setlen_u_z(obj, 1));
  set_alloc_fail(1);
  tt_int_op(-1, ==, unlo_setlen_leftovers(obj, 1));

 end:
  unlo_free(obj);
#else
  tt_skip();
 end: ;
#endif
}



struct testcase_t leftover_union_tests[] = {
  { "invalid", test_lo_union_invalid, 0, NULL, NULL },
  { "truncated", test_lo_union_truncated, 0, NULL, NULL },
  { "accessors", test_lo_union_accessors, 0, NULL, NULL },
  { "allocfail", test_lo_union_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
