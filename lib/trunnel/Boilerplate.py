# CodeGen.py -- code generator for trunnel.
#
# Copyright 2014, The Tor Project, Inc.
# See license at the end of this file for copying information.

import os
import trunnel

FILES = [ "trunnel.c", "trunnel.h", "trunnel-impl.h" ]

def emit(target_dir=None):
    if target_dir == None:
        target_dir = '.'
    directory = os.path.split(__file__)[0]
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    for f in FILES:
        emitfile(f,
                 os.path.join(directory, "data", f),
                 os.path.join(target_dir, f))

def emitfile(fname, in_fname, out_fname):
    settings = {
        'fname' : 'fname',
        'version' : trunnel.__version__
        }
    with open(in_fname, 'r') as inp, open(out_fname, 'w') as out:
        out.write("/* %(fname)s -- copied from Trunnel v%(version)s\n"
                  " * https://gitweb.torproject.org/trunnel.git\n"
                  " */\n")
        out.write(inp.read())

__license__ = """
Copyright 2014  The Tor Project, Inc.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

    * Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following disclaimer
in the documentation and/or other materials provided with the
distribution.

    * Neither the names of the copyright owners nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""