
#include "test.h"
#include "valid/contexts.h"

static const char EXAMPLE[] =
  "2030" "00000001" "00000002" "05060708" "01020304" "05060708090a0b0c0d0e0f";

static void
test_contexts_complex_encdec(void *arg)
{
  flag_t *flag_one = NULL, *flag_zero = NULL;
  count_t *count_six = NULL, *count_four = NULL;
  ccomplex_t *ccomplex = NULL;
  uint8_t buf[64];
  const uint8_t *inp;
  unsigned u;
  size_t len;
  (void)arg;

  flag_one = flag_new();
  flag_zero = flag_new();
  flag_set_flagval(flag_one, 1);
  flag_set_flagval(flag_zero, 0);

  count_six = count_new();
  count_six->countval = 6;
  count_four = count_new();
  count_four->countval = 4;

  /* Truncated cases */
  inp = ux(EXAMPLE);
  len = strlen(EXAMPLE) / 2;
  for (u = 0; u < 18; ++u)
    tt_int_op(-2, ==, ccomplex_parse(&ccomplex, inp, u, flag_zero, count_four));

  for (u = 0; u < 16; ++u)
    tt_int_op(-2, ==, ccomplex_parse(&ccomplex, inp, u, flag_one, count_four));

  for (u = 0; u < 22; ++u)
    tt_int_op(-2, ==, ccomplex_parse(&ccomplex, inp, u, flag_zero, count_six));

  for (u = 0; u < 20; ++u)
    tt_int_op(-2, ==, ccomplex_parse(&ccomplex, inp, u, flag_one, count_six));


  /* zero, four */
  tt_int_op(18, ==, ccomplex_parse(&ccomplex, inp, len, flag_zero, count_four));
  tt_assert(ccomplex);
  tt_int_op(32, ==, ccomplex->p->x);
  tt_int_op(48, ==, ccomplex->p->y);
  tt_int_op(1, ==, ccomplex->tsz->u_x);
  tt_int_op(2, ==, ccomplex->vsz->a);
  tt_int_op(4, ==, varsize_getlen_msg(ccomplex->vsz));
  tt_mem_op("\x05\x06\x07\x08", ==, varsize_getarray_msg(ccomplex->vsz), 4);
  tt_int_op(4, ==, ccomplex_getlen_u_a(ccomplex));
  tt_mem_op("\x01\x02\x03\x04", ==, ccomplex_getarray_u_a(ccomplex), 4);
  for (u = 0; u < 18; ++u)
    tt_int_op(-2, ==, ccomplex_encode(buf, u, ccomplex, flag_zero, count_four));
  memset(buf, 0xff, sizeof(buf));
  tt_int_op(18, ==, ccomplex_encode(buf, 18, ccomplex, flag_zero, count_four));
  tt_mem_op(buf, ==, inp, 18);
  ccomplex_free(ccomplex); ccomplex = NULL;

  /* one, six */
  tt_int_op(20, ==, ccomplex_parse(&ccomplex, inp, len, flag_one, count_six));
  tt_assert(ccomplex);
  tt_int_op(32, ==, ccomplex->p->x);
  tt_int_op(48, ==, ccomplex->p->y);
  tt_int_op(0, ==, ccomplex->tsz->u_y);
  tt_int_op(0x10000, ==, ccomplex->vsz->a);
  tt_int_op(6, ==, varsize_getlen_msg(ccomplex->vsz));
  tt_mem_op("\x00\x02\x05\x06\x07\x08", ==,
            varsize_getarray_msg(ccomplex->vsz), 6);
  tt_int_op(3, ==, ccomplex_getlen_u_b(ccomplex));
  tt_int_op(0x102, ==, ccomplex_get_u_b(ccomplex, 0));
  tt_int_op(0x304, ==, ccomplex_get_u_b(ccomplex, 1));
  tt_int_op(0x506, ==, ccomplex_get_u_b(ccomplex, 2));
  for (u = 0; u < 20; ++u)
    tt_int_op(-2, ==, ccomplex_encode(buf, u, ccomplex, flag_one, count_six));
  memset(buf, 0xff, sizeof(buf));
  tt_int_op(20, ==, ccomplex_encode(buf, 20, ccomplex, flag_one, count_six));
  tt_mem_op(buf, ==, inp, 20);


 end:
  ccomplex_free(ccomplex);
  flag_free(flag_one);
  flag_free(flag_zero);
  count_free(count_six);
  count_free(count_four);
}

static void
test_contexts_complex_invalid(void *arg)
{
  ccomplex_t *cc = NULL;
  flag_t *flag_zero = NULL;
  count_t *count_two = NULL;
  uint8_t buf[64];

  (void)arg;
  cc = ccomplex_new();
  flag_zero = flag_new();
  count_two = count_new();
  count_two->countval = 2;

  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), NULL, flag_zero, count_two));
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));

  ccomplex_set_p(cc, point_new());
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));

  ccomplex_set_tsz(cc, twosize_new());
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));

  ccomplex_set_vsz(cc, varsize_new());
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));
  varsize_setlen_msg(cc->vsz, 2);
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));

  ccomplex_setlen_u_a(cc, 2);
  tt_int_op(14, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));

  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, NULL, count_two));
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, NULL));

  flag_zero->flagval = 3;
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));
  flag_zero->flagval = 0;

  count_two->countval = 3;
  varsize_add_msg(cc->vsz, 5);
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));
  ccomplex_add_u_a(cc, 10);
  tt_int_op(16, ==, ccomplex_encode(buf, sizeof(buf), cc, flag_zero, count_two));

 end:
  ccomplex_free(cc);
  count_free(count_two);
  flag_free(flag_zero);
}

static void
test_contexts_complex_unparseable(void *arg)
{
  ccomplex_t *cc = NULL;
  flag_t flag;
  count_t count;
  unsigned u;
  const uint8_t *inp;
  size_t len;
  const struct { int flag; int count; const char *s; } strs[] = {
    { 3, 0, EXAMPLE },
    { 1, 3, "0102" "0002" "00000003" "112233" "1111222233334444" },
    { 0, 0, NULL },
  };

  (void)arg;
  for (u = 0; strs[u].s; ++u) {
    flag.flagval = strs[u].flag;
    count.countval = strs[u].count;
    inp = ux(strs[u].s);
    len = strlen(strs[u].s)/2;
    tt_int_op(-1, ==, ccomplex_parse(&cc, inp, len, &flag, &count));
  }

 end:
  ccomplex_free(cc);
}

static void
test_contexts_complex_accessors(void *arg)
{
  ccomplex_t *ccomplex = NULL;
  point_t *p = NULL;
  twosize_t *tsz = NULL;
  varsize_t *vsz = NULL;

  (void)arg;

  ccomplex = ccomplex_new();
  tt_ptr_op(ccomplex, !=, NULL);
  tt_ptr_op(NULL, ==, ccomplex_get_p(ccomplex));
  tt_ptr_op(NULL, ==, ccomplex_get_tsz(ccomplex));
  tt_ptr_op(NULL, ==, ccomplex_get_vsz(ccomplex));
  tt_int_op(0, ==, ccomplex_getlen_u_a(ccomplex));
  tt_int_op(0, ==, ccomplex_getlen_u_b(ccomplex));

  tt_int_op(0, ==, ccomplex_add_u_a(ccomplex, 64));
  tt_int_op(0, ==, ccomplex_add_u_b(ccomplex, 4096));
  tt_int_op(0, ==, ccomplex_add_u_b(ccomplex, 8192));
  tt_int_op(1, ==, ccomplex_getlen_u_a(ccomplex));
  tt_int_op(2, ==, ccomplex_getlen_u_b(ccomplex));
  tt_int_op(0, ==, ccomplex_setlen_u_a(ccomplex, 5));
  tt_int_op(0, ==, ccomplex_setlen_u_b(ccomplex, 10));
  tt_int_op(5, ==, ccomplex_getlen_u_a(ccomplex));
  tt_int_op(10, ==, ccomplex_getlen_u_b(ccomplex));

  tt_int_op(0, ==, ccomplex_set_u_a(ccomplex, 2, 40));
  tt_int_op(0, ==, ccomplex_set_u_b(ccomplex, 3, 4000));

  tt_int_op(64, ==, ccomplex_get_u_a(ccomplex, 0));
  tt_int_op(8192, ==, ccomplex_get_u_b(ccomplex, 1));
  tt_int_op(40, ==, ccomplex_get_u_a(ccomplex, 2));
  tt_int_op(4000, ==, ccomplex_get_u_b(ccomplex, 3));

  tt_mem_op(ux("4000280000"), ==, ccomplex_getarray_u_a(ccomplex), 5);
  tt_int_op(4096, ==, ccomplex_getarray_u_b(ccomplex)[0]);

  p = point_new();
  ccomplex_set_p(ccomplex, p);
  tt_ptr_op(p, ==, ccomplex_get_p(ccomplex));
  ccomplex_set_p(ccomplex, point_new());
  tt_ptr_op(p, !=, ccomplex_get_p(ccomplex));
  p = NULL;

  tsz = twosize_new();
  ccomplex_set_tsz(ccomplex, tsz);
  tt_ptr_op(tsz, ==, ccomplex_get_tsz(ccomplex));
  ccomplex_set_tsz(ccomplex, twosize_new());
  tt_ptr_op(tsz, !=, ccomplex_get_tsz(ccomplex));
  tsz = NULL;

  vsz = varsize_new();
  ccomplex_set_vsz(ccomplex, vsz);
  tt_ptr_op(vsz, ==, ccomplex_get_vsz(ccomplex));
  ccomplex_set_vsz(ccomplex, varsize_new());
  tt_ptr_op(vsz, !=, ccomplex_get_vsz(ccomplex));
  vsz = NULL;

 end:
  ccomplex_free(ccomplex);
  point_free(p);
  twosize_free(tsz);
  varsize_free(vsz);
}

static void
test_contexts_complex_nulls(void *arg)
{
  ccomplex_t *ccomplex = ccomplex_new();
  flag_t *flag = flag_new();
  count_t *count = count_new();
  uint8_t buf[64] = {0};

  (void)arg;
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), NULL, flag, count));
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), ccomplex, NULL, count));
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), ccomplex, flag, NULL));

  ccomplex_free(ccomplex);
  ccomplex = NULL;

  tt_int_op(-1, ==, ccomplex_parse(&ccomplex, buf, sizeof(buf), NULL, count));
  tt_int_op(-1, ==, ccomplex_parse(&ccomplex, buf, sizeof(buf), flag, NULL));

 end:
  ccomplex_free(ccomplex);
  flag_free(flag);
  count_free(count);
}

static void
test_contexts_complex_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  ccomplex_t *ccomplex = NULL;
  flag_t *flag = flag_new();
  count_t *count = count_new();
  uint8_t buf[64] = {0};
  int i,j;

  (void)arg;

  set_alloc_fail(1);
  tt_ptr_op(NULL, ==, ccomplex_new());

  count->countval = 4;

  for (j = 0; j <= 1; ++j) {
    flag->flagval = j;
    for (i = 1; i <= 6; ++i) {
      set_alloc_fail(i);
      tt_int_op(-1, ==,
                ccomplex_parse(&ccomplex, buf, sizeof(buf), flag, count));
    }
  }

  ccomplex = ccomplex_new();
  set_alloc_fail(1);
  tt_int_op(-1, ==, ccomplex_setlen_u_a(ccomplex, 5));
  tt_int_op(1, ==, ccomplex_clear_errors(ccomplex));
  set_alloc_fail(1);
  tt_int_op(-1, ==, ccomplex_setlen_u_b(ccomplex, 5));
  tt_int_op(1, ==, ccomplex_clear_errors(ccomplex));

  set_alloc_fail(1);
  tt_int_op(-1, ==, ccomplex_add_u_a(ccomplex, 10));
  tt_int_op(1, ==, ccomplex_clear_errors(ccomplex));
  set_alloc_fail(1);
  tt_int_op(-1, ==, ccomplex_add_u_b(ccomplex, 10));
  tt_int_op(-1, ==, ccomplex_encode(buf, sizeof(buf), ccomplex, flag, count));
  tt_int_op(1, ==, ccomplex_clear_errors(ccomplex));

  tt_int_op(0, ==, ccomplex_clear_errors(ccomplex));

 end:
  ccomplex_free(ccomplex);
  flag_free(flag);
  count_free(count);
#else
  (void)arg;
  tt_skip();
#endif
}

struct testcase_t contexts_complex_tests[] = {
  { "encdec", test_contexts_complex_encdec, 0, NULL, NULL },
  { "invalid", test_contexts_complex_invalid, 0, NULL, NULL },
  { "unparseable", test_contexts_complex_unparseable, 0, NULL, NULL },
  { "accessors", test_contexts_complex_accessors, 0, NULL, NULL },
  { "nulls", test_contexts_complex_nulls, 0, NULL, NULL },
  { "allocfail", test_contexts_complex_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};
