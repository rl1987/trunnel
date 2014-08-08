#!/bin/sh
#
# run_tests.sh -- a kludgey test wrapper for the Trunnel code generator.
#
# This is meant to exersie the whole trunnel code generator, using the
# input files in valid/* and failing/*.
#
# Copyright 2014 The Tor Project, Inc.
# See LICENSE file for copying information.

TRUNNEL=`dirname $0`/../lib/CodeGen.py
GRAMMAR=`dirname $0`/../lib/Grammar.py
CC=gcc
CFLAGS="-g -O2 -D_FORTIFY_SOURCE=2 -fstack-protector-all -Wstack-protector -fwrapv --param ssp-buffer-size=1 -fPIE -fasynchronous-unwind-tables -Wall -fno-strict-aliasing -Wno-deprecated-declarations -W -Wfloat-equal -Wundef -Wpointer-arith -Wstrict-prototypes -Wmissing-prototypes -Wwrite-strings -Wredundant-decls -Wchar-subscripts -Wcomment -Wformat=2 -Wwrite-strings -Wmissing-declarations -Wredundant-decls -Wnested-externs -Wbad-function-cast -Wswitch-enum -Werror -Winit-self -Wmissing-field-initializers -Wdeclaration-after-statement -Wold-style-definition -Waddress -Wmissing-noreturn -Wstrict-overflow=1 -I `dirname $0`/../include"
X=" -Wshorten-64-to-32  -Qunused-arguments"

PYTHON=python

if $PYTHON -m coverage >/dev/null ; then
  COVERAGE="$PYTHON -m coverage"
  RUN0="$PYTHON -m coverage run"
  RUN="$PYTHON -m coverage run -a"
else
  COVERAGE="true"
  RUN0="$PYTHON"
  RUN="$PYTHON"
fi


# Try failing cases.
echo >tests.log "==== no argument"
$RUN0 $TRUNNEL 2>>tests.log && echo "FAIL"
for fn in `dirname $0`/failing/*.trunnel; do
  echo >>tests.log "==== $fn"
  $RUN $TRUNNEL $fn 2>>tests.log && echo "SHOULD HAVE FAILED: $fn"
done

# Try valid tests.
for fn in `dirname $0`/valid/*.trunnel; do
  echo >>tests.log "==== $fn"
  $RUN $TRUNNEL $fn 2>>tests.log || echo "FAILED: $fn"
  CNAME=`echo $fn | sed -e 's/trunnel$/c/'`
  $CC $CFLAGS -c $CNAME || echo "FAILED: $CC $CFLAGS $fn"
done

echo >>tests.log "==== MakeGrammar"
$RUN $GRAMMAR > grammar.tmp 2>>tests.log || echo "FAILED: grammar"
rm -f grammar.tmp

$COVERAGE report $TRUNNEL $GRAMMAR
$COVERAGE annotate $TRUNNEL
$COVERAGE annotate $GRAMMAR
