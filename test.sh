#!/bin/sh

# This file should go away

python lib/CodeGen.py doc/example2.trunnel && gcc -g -O2 -D_FORTIFY_SOURCE=2 -Qunused-arguments -fstack-protector-all -Wstack-protector -fwrapv --param ssp-buffer-size=1 -fPIE -fasynchronous-unwind-tables -Wall -fno-strict-aliasing -Wno-deprecated-declarations -W -Wfloat-equal -Wundef -Wpointer-arith -Wstrict-prototypes -Wmissing-prototypes -Wwrite-strings -Wredundant-decls -Wchar-subscripts -Wcomment -Wformat=2 -Wwrite-strings -Wmissing-declarations -Wredundant-decls -Wnested-externs -Wbad-function-cast -Wswitch-enum -Werror -Winit-self -Wmissing-field-initializers -Wdeclaration-after-statement -Wold-style-definition -Waddress -Wmissing-noreturn -Wstrict-overflow=1 -Wshorten-64-to-32 -c doc/example2.c
        

