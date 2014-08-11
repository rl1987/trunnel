# Makefile -- a clumsy makefile for the C unit tests for generated trunnel
#   code.
#
# Copyright 2014 The Tor Project, Inc.
# See LICENSE file for copying information.

MORE_CFLAGS=-fno-inline --coverage

CC=gcc
CFLAGS=-g -O0 -fstack-protector-all -Wstack-protector -fwrapv --param ssp-buffer-size=1 -fPIE -fasynchronous-unwind-tables -Wall -fno-strict-aliasing -Wno-deprecated-declarations -W -Wfloat-equal -Wundef -Wpointer-arith -Wstrict-prototypes -Wmissing-prototypes -Wwrite-strings -Wredundant-decls -Wchar-subscripts -Wcomment -Wformat=2 -Wwrite-strings -Wmissing-declarations -Wredundant-decls -Wnested-externs -Wbad-function-cast -Wswitch-enum -Werror -Winit-self -Wmissing-field-initializers -Wdeclaration-after-statement -Wold-style-definition -Waddress -Wmissing-noreturn -Wstrict-overflow=1 -I . -I ../include -DTRUNNEL_DEBUG_FAILING_ALLOC $(MORE_CFLAGS)
#OTHER_FLAGS= -Qunused-arguments -Wshorten-64-to-32

TEST_OBJS = \
    c/test.o \
    c/test_numbers.o \
    c/test_restricted.o \
    c/test_strings.o \
    c/test_eos.o \
    c/test_extends.o \
    c/test_nested.o \
    c/test_fixedarray.o \
    c/test_vararray.o \
    c/test_union_nolen.o \
    c/test_union_withlen.o \
    c/test_union_defaults.o \
    c/test_remainder_repeats.o \
    c/test_util.o

OBJS=tinytest/tinytest.o \
    valid/simple.o \
    valid/derived.o \
    valid/opaque.o \
    ../c/trunnel.o \
    $(TEST_OBJS)

all: ctest

ctest: $(OBJS)
	$(CC) $(CFLAGS) -o ctest $(OBJS)

clean:
	rm -f $(OBJS) ctest

reset-gcov:
	rm -f */*.gcda ../*/*.gcda

distclean: clean
	rm -f valid/*.[ch]

test: ctest
	./ctest

valid/simple.o: valid/simple.h valid/simple.c
valid/derived.o: valid/derived.h valid/derived.c
$(TEST_OBJS) : tinytest/tinytest.h tinytest/tinytest_macros.h valid/simple.h valid/derived.h
tinytest/tinytest.o: tinytest/tinytest.h tinytest/tinytest_macros.h

valid/simple.c valid/simple.h: valid/simple.trunnel ../lib/trunnel/*py
	PYTHONPATH=../lib:${PYTHONPATH} python -m trunnel.Main valid/simple.trunnel

valid/derived.c valid/derived.h: valid/derived.trunnel ../lib/trunnel/*py
	PYTHONPATH=../lib:${PYTHONPATH} python -m trunnel.Main valid/derived.trunnel

valid/opaque.c valid/opaque.h: valid/opaque.trunnel ../lib/trunnel/*py
	PYTHONPATH=../lib:${PYTHONPATH} python -m trunnel.Main valid/opaque.trunnel

