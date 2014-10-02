# __main__.py -- CLI for trunnel
#
# Copyright 2014, The Tor Project, Inc.
# See license at the end of this file for copying information.

if __name__ == '__main__':
    import sys
    import trunnel.Boilerplate
    import trunnel.CodeGen
    import getopt

    opts, args = getopt.gnu_getopt(
        sys.argv[1:], "O:",
        ["option=", "write-c-files", "target-dir=", "require-version="])

    more_options = []
    target_dir = None
    write_c_files = None
    need_version = None

    for (k, v) in opts:
        if k in ('-O', '--option'):
            more_options.append(v)
        elif k == '--write-c-files':
            write_c_files = True
        elif k == '--target-dir':
            target_dir = v
        elif k == '--require-version':
            need_version = v

    if need_version is not None:
        try:
            from distutils.version import LooseVersion
            me, it = trunnel.__version__, need_version
            if LooseVersion(me) < LooseVersion(it):
                sys.stderr.write("I'm %s; you asked for %s\n" % (me, it))
                sys.exit(1)
        except ImportError:
            print "Can't import"

    if len(args) < 1 and not write_c_files and not need_version:
        sys.stderr.write("Syntax: python -m trunnel <fname>\n")
        sys.exit(1)

    for filename in args:
        trunnel.CodeGen.generate_code(filename, more_options,
                                      target_dir=target_dir)

    if write_c_files:
        trunnel.Boilerplate.emit(target_dir=target_dir)


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
