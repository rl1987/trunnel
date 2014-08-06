/* trunnel-impl.h -- Implementation helpers for trunnel, included by
 * generated trunnel files
 *
 * Copyright 2014, The Tor Project, Inc.
 * See license at the end of this file for copying information.
 */

#ifndef TRUNNEL_IMPL_H_INCLUDED_
#define TRUNNEL_IMPL_H_INCLUDED_
#include <sys/types.h>

#define TRUNNEL_DYNARRAY_INITIALIZE(da) do {     \
    (da)->n_ = 0;                                \
    (da)->allocated_ = 0;                        \
    (da)->elts_ = NULL;                          \
  } while (0)

#define TRUNNEL_DYNARRAY_GET(da, n)                                     \
  (((n) >= (da)->n_ ? (trunnel_abort(),0) : 0), (da)->elts_[(n)])

#define TRUNNEL_DYNARRAY_SET(da, n, v) do {                   \
    if ((n) >= (da)->n_) {                                    \
      trunnel_abort();                                        \
    }                                                          \
    (da)->elts_[(n)] = (v);                                    \
  } while (0)

#define TRUNNEL_DYNARRAY_EXPAND(elttype, da, howmanymore) do {       \
    elttype *newarray;                                               \
    newarray = trunnel_dynarray_expand(&(da)->allocated_,            \
                                       (da)->elts_, (howmanymore),   \
                                       sizeof(elttype));             \
    if (newarray == NULL)                                            \
      goto trunnel_alloc_failed;                                     \
    (da)->elts_ = newarray;                                          \
  } while (0)

#define TRUNNEL_DYNARRAY_ADD(elttype, da, v) do {          \
      if ((da)->n_ == (da)->allocated_) {                  \
        TRUNNEL_DYNARRAY_EXPAND(elttype, da, 1);           \
      }                                                    \
      (da)->elts_[(da)->n_++] = (v);                       \
    } while (0)

#define TRUNNEL_DYNARRAY_LEN(da) ((da)->n_)

#define TRUNNEL_DYNARRAY_CLEAR(da) do {           \
    if ((da)->elts_)                              \
      trunnel_free((da)->elts_);                  \
    (da)->elts_ = NULL;                           \
    (da)->n_ = (da)->allocated_ = 0;              \
  } while (0)

void *trunnel_reallocarray(void *a, size_t x, size_t y);
void *trunnel_dynarray_expand(size_t *allocated_p, void *ptr,
                              size_t howmanymore, size_t eltsize);

#endif


/*
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
*/
