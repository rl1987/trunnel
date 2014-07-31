# Makefile -- a clumsy makefile for the C unit tests for generated trunnel
#   code.
#
# Copyright 2014 The Tor Project, Inc.
# See LICENSE file for copying information.

MORE_CFLAGS=-fno-inline --coverage

CC=gcc
CFLAGS=-g -O2 -D_FORTIFY_SOURCE=2 -Qunused-arguments -fstack-protector-all -Wstack-protector -fwrapv --param ssp-buffer-size=1 -fPIE -fasynchronous-unwind-tables -Wall -fno-strict-aliasing -Wno-deprecated-declarations -W -Wfloat-equal -Wundef -Wpointer-arith -Wstrict-prototypes -Wmissing-prototypes -Wwrite-strings -Wredundant-decls -Wchar-subscripts -Wcomment -Wformat=2 -Wwrite-strings -Wmissing-declarations -Wredundant-decls -Wnested-externs -Wbad-function-cast -Wswitch-enum -Werror -Winit-self -Wmissing-field-initializers -Wdeclaration-after-statement -Wold-style-definition -Waddress -Wmissing-noreturn -Wstrict-overflow=1 -Wshorten-64-to-32 -I . -I ../include $(MORE_CFLAGS)

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
    c/test_union_defaults.o

OBJS=tinytest/tinytest.o \
    valid/basic.o \
    $(TEST_OBJS)

all: ctest

ctest: $(OBJS)
	$(CC) $(CFLAGS) -o ctest $(OBJS)

clean:
	rm -f $(OBJS) ctest

reset-gcov:
	rm -f */*.gcda

distclean: clean
	rm -f valid/basic.[ch]

test: ctest
	./ctest

valid/basic.o: valid/basic.h valid/basic.c
$(TEST_OBJS) : tinytest/tinytest.h tinytest/tinytest_macros.h valid/basic.h
tinytest/tinytest.o: tinytest/tinytest.h tinytest/tinytest_macros.h

valid/basic.c valid/basic.h: valid/basic.trunnel
	python ../lib/CodeGen.py valid/basic.trunnel


