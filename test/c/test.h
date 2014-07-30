#include <stdio.h>
#include <sys/types.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "valid/basic.h"
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

ssize_t unhex(uint8_t *out, size_t outlen, const char *in);
const uint8_t *ux(const char *in);
