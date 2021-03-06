#ifndef TEST_H_INCLUDED
#define TEST_H_INCLUDED

#include <stdio.h>
#include <sys/types.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "valid/simple.h"
#include "valid/derived.h"
#include "tinytest/tinytest.h"
#include "tinytest/tinytest_macros.h"

extern struct testcase_t numbers_tests[];
extern struct testcase_t restricted_tests[];
extern struct testcase_t strings_tests[];
extern struct testcase_t eos_tests[];
extern struct testcase_t extends_tests[];
extern struct testcase_t nested_tests[];
extern struct testcase_t fixedarray_tests[];
extern struct testcase_t vararray_tests[];
extern struct testcase_t union_nolen_tests[];
extern struct testcase_t union_withlen_tests[];
extern struct testcase_t union_defaults_tests[];
extern struct testcase_t repeats_tests[];
extern struct testcase_t util_tests[];
extern struct testcase_t leftover_messages_tests[];
extern struct testcase_t leftover_union_tests[];
extern struct testcase_t contexts_support_tests[];
extern struct testcase_t contexts_uniontag_tests[];
extern struct testcase_t contexts_varsize_tests[];
extern struct testcase_t contexts_varsize2_tests[];
extern struct testcase_t contexts_complex_tests[];
extern struct testcase_t positions_tests[];

ssize_t unhex(uint8_t *out, size_t outlen, const char *in);
const uint8_t *ux(const char *in);

#ifdef TRUNNEL_DEBUG_FAILING_ALLOC
#define ALLOCFAIL
#include "trunnel-impl.h"
#define set_alloc_fail(n)                       \
  do {                                          \
    trunnel_provoke_alloc_failure = (n);        \
  } while (0)
#endif

#endif
