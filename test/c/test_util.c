#include "test.h"
#include "trunnel-impl.h"

#define trunnel_free free

static void
test_reallocarray(void *arg)
{
  unsigned *u = NULL, *u2 = NULL, tot=0;
  int i;
  (void) arg;

  u = trunnel_reallocarray(NULL, sizeof(unsigned), 10);
  tt_assert(u);
  for (i = 0; i < 10; ++i) {
    u[i] = 999; /* valgrind will complain if this goes off the end. */
  }
  u = trunnel_reallocarray(u, sizeof(unsigned), 30);
  tt_assert(u);
  for (i = 0; i < 10; ++i) {
    tt_int_op(u[i], ==, 999);
  }
  for (i = 10; i < 30; ++i) {
    u[i] = 1000;
  }
  u2 = trunnel_reallocarray(u, sizeof(unsigned), SIZE_MAX);
  tt_ptr_op(u2, ==, NULL);
  for (i = 0; i < 30; ++i) {
    tot += u[i];
  }
  u2 = trunnel_reallocarray(u, sizeof(unsigned), SIZE_MAX/sizeof(unsigned) + 1);
  tt_ptr_op(u2, ==, NULL);
  for (i = 0; i < 30; ++i) {
    tot += u[i];
  }
  tt_uint_op(tot, ==, 1000*40 + 999*20);

 end:
  if (u)
    free(u);
}

static void
test_dynarray_expand(void *arg)
{
  TRUNNEL_DYNARRAY_HEAD(, int) ints = TRUNNEL_DYNARRAY_INIT(int);
  (void) arg;

  /* Expand from nothing gets 8, unless it's more. */
  TRUNNEL_DYNARRAY_EXPAND(int, &ints, 3);
  tt_int_op(ints.allocated_, ==, 8);

  /* Expanding further should work okay. */
  TRUNNEL_DYNARRAY_EXPAND(int, &ints, 1);
  tt_int_op(ints.allocated_, ==, 16);

  /* Expanding by 0 expands too */
  TRUNNEL_DYNARRAY_EXPAND(int, &ints, 0);
  tt_int_op(ints.allocated_, ==, 32);

  ints.elts_[31] = 9999;

  TRUNNEL_DYNARRAY_EXPAND(int, &ints, 100);
  tt_int_op(ints.allocated_, ==, 132);

  tt_int_op(ints.elts_[31], ==, 9999);
  ints.elts_[131] = 9999;

  goto end;
 trunnel_alloc_failed:
  tt_fail();
 end:
  TRUNNEL_DYNARRAY_CLEAR(&ints);
}

static void
test_dynarray_expand_fail1(void *arg)
{
  TRUNNEL_DYNARRAY_HEAD(, int) ints = TRUNNEL_DYNARRAY_INIT(int);
  int should_fail_now = 0;
  (void) arg;

  TRUNNEL_DYNARRAY_EXPAND(int, &ints, 100);
  tt_int_op(ints.allocated_, ==, 100);

  /* Overflow the size. */
  should_fail_now = 1;
  TRUNNEL_DYNARRAY_EXPAND(int, &ints, SIZE_MAX - 50);
  tt_fail();
  assert(0);
 trunnel_alloc_failed:
  tt_assert(should_fail_now);
  tt_int_op(ints.allocated_, ==, 100);
  ints.elts_[99] = 12345;
end:
  TRUNNEL_DYNARRAY_CLEAR(&ints);
}

static void
test_dynarray_expand_fail2(void *arg)
{
  TRUNNEL_DYNARRAY_HEAD(, int) ints = TRUNNEL_DYNARRAY_INIT(int);
  int should_fail_now = 0;
  (void) arg;

  TRUNNEL_DYNARRAY_EXPAND(int, &ints, 100);
  tt_int_op(ints.allocated_, ==, 100);

  /* Make reallocarray fail */
  should_fail_now = 1;
  TRUNNEL_DYNARRAY_EXPAND(int, &ints, SIZE_MAX/sizeof(int));
  tt_fail();
  assert(0);
 trunnel_alloc_failed:
  tt_assert(should_fail_now);
  tt_int_op(ints.allocated_, ==, 100);
  ints.elts_[99] = 12345;
end:
  TRUNNEL_DYNARRAY_CLEAR(&ints);
}

static void
test_setstr0(void *arg)
{
  trunnel_string_t s = TRUNNEL_DYNARRAY_INIT(char);
  uint8_t error = 0;
  (void)arg;

  tt_int_op(0, ==, trunnel_string_setstr0(&s, "Hello", 5, &error));
  tt_str_op("Hello", ==, s.elts_);
  tt_int_op(0, ==, trunnel_string_setstr0(&s, "Bye", 5, &error));
  tt_str_op("Bye", ==, s.elts_);
  tt_int_op(0, ==, error);

  tt_int_op(8, ==, s.allocated_);
  tt_int_op(0, ==, trunnel_string_setstr0(&s, "trunnel!", 8, &error));
  tt_str_op("trunnel!", ==, s.elts_);
  tt_int_op(0, ==, error);

  tt_int_op(16, ==, s.allocated_);
  tt_int_op(0, ==, trunnel_string_setstr0(&s, "trunnel!trunnel", 15, &error));
  tt_str_op("trunnel!trunnel", ==, s.elts_);
  tt_int_op(16, ==, s.allocated_);
  tt_int_op(0, ==, error);

  /* Fail if the size is insane. */
  tt_int_op(-1, ==, trunnel_string_setstr0(&s, "foobar", SIZE_MAX, &error));
  tt_int_op(1, ==, error);
  tt_str_op("trunnel!trunnel", ==, s.elts_);
  tt_int_op(16, ==, s.allocated_);

#ifdef ALLOCFAIL
  /* Fail if EXPAND fails. */
  error = 0;
  set_alloc_fail(1);
  tt_int_op(-1, ==, trunnel_string_setstr0(&s,
         "----------------------------------------------------------------",
                                            64, &error));
  tt_int_op(1, ==, error);
  tt_str_op("trunnel!trunnel", ==, s.elts_);
  tt_int_op(16, ==, s.allocated_);
#endif

end:
  TRUNNEL_DYNARRAY_CLEAR(&s);
}

static void test_getstr(void *arg)
{
  trunnel_string_t s = TRUNNEL_DYNARRAY_INIT(char);
  uint8_t error = 0;
  (void)arg;

  tt_int_op(0, ==, trunnel_string_setstr0(&s, "Hello", 5, &error));
  s.elts_[5] = 'x'; /* smash this to verify that we re-terminate the string. */
  tt_str_op("Hello", ==, trunnel_string_getstr(&s));

  /* now we need to resize the string to terminate it. */
  tt_int_op(8, ==, s.allocated_);
  memcpy(s.elts_, "TRUNNEL!", 8);
  s.n_ = 8;
  tt_str_op("TRUNNEL!", ==, trunnel_string_getstr(&s));
  tt_int_op(s.n_, ==, 8);

#ifdef ALLOCFAIL
  {
    void *p;
    /* Now, allocation failure. */
    tt_int_op(16, ==, s.allocated_);
    memset(s.elts_, '?', 16);
    s.n_ = 16;
    set_alloc_fail(1);
    p = s.elts_;
    tt_ptr_op(NULL, ==, trunnel_string_getstr(&s));
    tt_ptr_op(s.elts_, ==, p);
    tt_int_op(s.n_, ==, 16);
    tt_int_op(16, ==, s.allocated_);
  }
#endif
 end:
  TRUNNEL_DYNARRAY_CLEAR(&s);
}

static void
test_str_setlen(void *arg)
{
  trunnel_string_t s = TRUNNEL_DYNARRAY_INIT(char);
  uint8_t error = 0;
  int i;
  (void) arg;

  tt_int_op(0, ==, trunnel_string_setstr0(&s, "Hello", 5, &error));
  tt_int_op(0, ==, error);

  s.elts_[5] = 5;

  tt_int_op(0, ==, trunnel_string_setlen(&s, 33, &error));
  tt_int_op(34, ==, s.allocated_);
  tt_int_op(33, ==, s.n_);
  for (i = 5; i < 34; ++i) {
    tt_int_op(s.elts_[i], ==, 0);
  }
  tt_int_op(0, ==, error);

  /* So, this fails, since we can't alloc that many. */
  tt_int_op(-1, ==, trunnel_string_setlen(&s, SIZE_MAX, &error));
  tt_int_op(1, ==, error);
  tt_str_op("Hello", ==, trunnel_string_getstr(&s));
  error = 0;

#ifdef ALLOCFAIL
  /* And this fails, since the allocation will fail. */
  set_alloc_fail(1);
  tt_int_op(-1, ==, trunnel_string_setlen(&s, 100, &error));
  tt_str_op("Hello", ==, trunnel_string_getstr(&s));
  tt_int_op(34, ==, s.allocated_);
  tt_int_op(33, ==, s.n_);
  tt_int_op(1, ==, error);
  error = 0;
#endif

  /* We can get smaller too. */
  memcpy(s.elts_, "squish SQUISH squish", 20);
  tt_int_op(0, ==, trunnel_string_setlen(&s, 15, &error));
  tt_str_op("squish SQUISH s", ==, s.elts_);
  tt_int_op(34, ==, s.allocated_);
  tt_int_op(15, ==, s.n_);

 end:
  TRUNNEL_DYNARRAY_CLEAR(&s);
}

static void
test_dynarray_setlen_ints(void *arg)
{
  void *newptr;
  uint8_t error;
  int i;
  TRUNNEL_DYNARRAY_HEAD(,uint32_t) da = TRUNNEL_DYNARRAY_INIT(uint32_t);
  (void)arg;

  /* Expand! */
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 10, sizeof(uint32_t), NULL,
                                   &error);
  tt_assert(newptr);
  tt_assert(!error);
  da.elts_ = newptr;
  tt_int_op(0, ==, da.elts_[5]);
  tt_int_op(10, ==, da.n_);
  tt_int_op(10, ==, da.allocated_);

  for (i = 0; i < 10; ++i)
    da.elts_[i] = 99;

  /* Shrink! */
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 3, sizeof(uint32_t), NULL,
                                   &error);
  tt_ptr_op(newptr, ==, da.elts_); /* Same pointer */
  tt_int_op(3, ==, da.n_);
  tt_int_op(10, ==, da.allocated_);
  tt_int_op(da.elts_[2], ==, 99);

  /* Expand some more.  Note that this should clear. */
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 12, sizeof(uint32_t), NULL,
                                   &error);
  tt_assert(newptr);
  tt_assert(!error);
  da.elts_ = newptr;
  tt_int_op(0, ==, da.elts_[3]);
  tt_int_op(0, ==, da.elts_[11]);
  tt_int_op(12, ==, da.n_);
  tt_int_op(20, ==, da.allocated_);
  tt_int_op(da.elts_[2], ==, 99);

  /* Expand and verify that the right ones (and only they) are cleared. */
  for (i = 0; i < 20; ++i)
    da.elts_[i] = 99;
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 14, sizeof(uint32_t), NULL,
                                   &error);
  tt_assert(newptr);
  tt_assert(!error);
  da.elts_ = newptr;
  tt_int_op(14, ==, da.n_);
  tt_int_op(20, ==, da.allocated_);
  for (i = 0; i < 20; ++i) {
    if (i == 12 || i == 13) {
      tt_int_op(da.elts_[i], ==, 0);
    } else {
      tt_int_op(da.elts_[i], ==, 99);
    }
  }


  /* Failing allocation */
#ifdef ALLOCFAIL
  /* And this fails, since the allocation will fail. */
  set_alloc_fail(1);
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 30, sizeof(uint32_t), NULL,
                                   &error);
  tt_ptr_op(newptr, ==, NULL);
  tt_assert(error == 1);
  tt_int_op(da.elts_[2], ==, 99);
  tt_int_op(99, ==, da.elts_[3]);
  tt_int_op(0, ==, da.elts_[12]);
  tt_int_op(14, ==, da.n_);
  tt_int_op(20, ==, da.allocated_);
#endif

 end:
  TRUNNEL_DYNARRAY_CLEAR(&da);
}


struct foo {
  int my_int;
  char junk[30];
};

static int n_called = 0;
static int n_freed = 0;

static void
foo_free(struct foo *foo)
{
  ++n_called;
  if (!foo)
    return;
  foo->my_int = 0xdeadbeef;
  free(foo);
  ++n_freed;
}

static struct foo *
foo_new(void)
{
  return calloc(1, sizeof(struct foo));
}

static void
test_dynarray_setlen_ptrs(void *arg)
{
  void *newptr;
  uint8_t error;
  int i;
  TRUNNEL_DYNARRAY_HEAD(,struct foo *) da = TRUNNEL_DYNARRAY_INIT(struct foo *);
  (void)arg;

  /* Expand! */
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 10, sizeof(struct foo *),
                                   (trunnel_free_fn_t)foo_free,
                                   &error);
  tt_assert(newptr);
  tt_assert(!error);
  da.elts_ = newptr;
  tt_ptr_op(0, ==, da.elts_[5]);
  tt_int_op(10, ==, da.n_);
  tt_int_op(10, ==, da.allocated_);

  for (i = 0; i < 10; ++i) {
    da.elts_[i] = foo_new();
    da.elts_[i]->my_int = 99;
  }

  foo_free(da.elts_[7]);
  da.elts_[7] = NULL;
  n_called = n_freed = 0;

  /* Shrink! */
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 3, sizeof(struct foo *),
                                   (trunnel_free_fn_t)foo_free,
                                   &error);
  tt_ptr_op(newptr, ==, da.elts_); /* Same pointer */
  tt_int_op(3, ==, da.n_);
  tt_int_op(10, ==, da.allocated_);
  tt_int_op(da.elts_[2]->my_int, ==, 99);
  tt_int_op(n_called, ==, 7);
  tt_int_op(n_freed, ==, 6);
  n_called = n_freed = 0;

  /* Expand some more.  Note that this should clear. */
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 12, sizeof(struct foo *),
                                   (trunnel_free_fn_t)foo_free,
                                   &error);
  tt_assert(newptr);
  tt_assert(!error);
  da.elts_ = newptr;
  tt_ptr_op(NULL, ==, da.elts_[3]);
  tt_ptr_op(NULL, ==, da.elts_[11]);
  tt_int_op(12, ==, da.n_);
  tt_int_op(20, ==, da.allocated_);
  tt_int_op(da.elts_[2]->my_int, ==, 99);
  tt_int_op(n_called, ==, 0);
  tt_int_op(n_freed, ==, 0);

  /* Expand and verify that the right ones (and only they) are cleared. */
  for (i = 0; i < 12; ++i) {
    if (!da.elts_[i])
      da.elts_[i] = foo_new();
    da.elts_[i]->my_int = 999;
  }
  for (i = 12; i < 20; ++i) {
    da.elts_[i] = (void*)(uintptr_t)0xdeadf00d;
  }

  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 14, sizeof(struct foo *),
                                   (trunnel_free_fn_t)foo_free,
                                   &error);
  tt_assert(newptr);
  tt_assert(!error);
  da.elts_ = newptr;
  tt_int_op(14, ==, da.n_);
  tt_int_op(20, ==, da.allocated_);
  for (i = 0; i < 20; ++i) {
    if (i == 12 || i == 13) {
      tt_ptr_op(da.elts_[i], ==, NULL);
    } else if (i < 12) {
      tt_int_op(da.elts_[i]->my_int, ==, 999);
    } else {
      tt_uint_op(0xdeadf00d, ==, (uintptr_t)da.elts_[i]);
    }
  }
  tt_int_op(n_called, ==, 0);
  tt_int_op(n_freed, ==, 0);

  for (i = 0; i < 12; ++i) {
    foo_free(da.elts_[i]);
  }

  /* Failing allocation */
#ifdef ALLOCFAIL
  /* And this fails, since the allocation will fail. */
  set_alloc_fail(1);
  newptr = trunnel_dynarray_setlen(&da.allocated_, &da.n_,
                                   da.elts_, 30, sizeof(struct foo *),
                                   (trunnel_free_fn_t)foo_free,
                                   &error);
  tt_ptr_op(newptr, ==, NULL);
  tt_assert(error == 1);
  tt_ptr_op(NULL, !=, da.elts_[3]);
  tt_ptr_op(NULL, ==, da.elts_[12]);
  tt_int_op(14, ==, da.n_);
  tt_int_op(20, ==, da.allocated_);
#endif

 end:
  TRUNNEL_DYNARRAY_CLEAR(&da);
}

struct testcase_t util_tests[] = {
  { "reallocarray", test_reallocarray, 0, NULL, NULL },
  { "string_setstr0", test_setstr0, 0, NULL, NULL },
  { "string_setstr0", test_getstr, 0, NULL, NULL },
  { "string_setlen", test_str_setlen, 0, NULL, NULL },
  { "dynarray_expand", test_dynarray_expand, 0, NULL, NULL },
  { "dynarray_expand_fail1", test_dynarray_expand_fail1, 0, NULL, NULL },
  { "dynarray_expand_fail2", test_dynarray_expand_fail2, 0, NULL, NULL },
  { "dynarray_setlen_ints", test_dynarray_setlen_ints, 0, NULL, NULL },
  { "dynarray_setlen_ptrs", test_dynarray_setlen_ptrs, 0, NULL, NULL },
  END_OF_TESTCASES
};
