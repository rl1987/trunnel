#!/bin/sh

TRUNNEL=`dirname $0`/../lib/CodeGen.py

RUN0="python -m coverage run"
RUN="python -m coverage run -a"

# Try failing cases.
echo >tests.log "==== no argument"
$RUN0 $TRUNNEL 2>>tests.log && echo "FAIL"
for fn in `dirname $0`/failing/*.trunnel; do
  echo >>tests.log "==== $fn"
  $RUN $TRUNNEL $fn 2>>tests.log && echo "SHOULD HAVE FAILED: $fn"
done
