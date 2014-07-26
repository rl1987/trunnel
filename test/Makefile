
MORE_CFLAGS=-fno-inline --coverage

CC=gcc
CFLAGS=-g -O2 -D_FORTIFY_SOURCE=2 -Qunused-arguments -fstack-protector-all -Wstack-protector -fwrapv --param ssp-buffer-size=1 -fPIE -fasynchronous-unwind-tables -Wall -fno-strict-aliasing -Wno-deprecated-declarations -W -Wfloat-equal -Wundef -Wpointer-arith -Wstrict-prototypes -Wmissing-prototypes -Wwrite-strings -Wredundant-decls -Wchar-subscripts -Wcomment -Wformat=2 -Wwrite-strings -Wmissing-declarations -Wredundant-decls -Wnested-externs -Wbad-function-cast -Wswitch-enum -Werror -Winit-self -Wmissing-field-initializers -Wdeclaration-after-statement -Wold-style-definition -Waddress -Wmissing-noreturn -Wstrict-overflow=1 -Wshorten-64-to-32 -I . $(MORE_CFLAGS)


OBJS=tinytest/tinytest.o \
    c/test.o \
    c/test_numbers.o \
    c/test_restricted.o \
    valid/basic.o

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
c/test.o: tinytest/tinytest.h tinytest/tinytest_macros.h valid/basic.h
c/test_numbers.o: tinytest/tinytest.h tinytest/tinytest_macros.h valid/basic.h
c/test_restricted.o: tinytest/tinytest.h tinytest/tinytest_macros.h valid/basic.h
tinytest/tinytest.o: tinytest/tinytest.h tinytest/tinytest_macros.h

valid/basic.c valid/basic.h: valid/basic.trunnel
	python ../lib/CodeGen.py valid/basic.trunnel


