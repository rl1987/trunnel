/* trunnel-impl.h -- Implementation helpers for trunnel, included by
 * generated trunnel files
 *
 * Copyright 2014, The Tor Project, Inc.
 * See license at the end of this file for copying information.
 */

#ifndef TRUNNEL_IMPL_H_INCLUDED_
#define TRUNNEL_IMPL_H_INCLUDED_
#include "trunnel.h"
#include <assert.h>

#define trunnel_assert(x) assert(x)

#define TRUNNEL_DYNARRAY_INITIALIZE(da) do {     \
    (da)->n_ = 0;                                \
    (da)->allocated_ = 0;                        \
    (da)->elts_ = NULL;                          \
  } while (0)

#ifdef NDEBUG
#define TRUNNEL_DYNARRAY_GET(da, n)             \
  ((da)->elts_[(n)])
#else
#define TRUNNEL_DYNARRAY_GET(da, n)             \
  (((n) >= (da)->n_ ? (trunnel_abort(),0) : 0), (da)->elts_[(n)])
#endif

#define TRUNNEL_DYNARRAY_SET(da, n, v) do {                    \
    trunnel_assert((n) < (da)->n_);                            \
    (da)->elts_[(n)] = (v);                                    \
  } while (0)

#define TRUNNEL_DYNARRAY_EXPAND(elttype, da, howmanymore, on_fail) do { \
    elttype *newarray;                                               \
    newarray = trunnel_dynarray_expand(&(da)->allocated_,            \
                                       (da)->elts_, (howmanymore),   \
                                       sizeof(elttype));             \
    if (newarray == NULL) {                                          \
      on_fail;                                                       \
      goto trunnel_alloc_failed;                                     \
    }                                                                \
    (da)->elts_ = newarray;                                          \
  } while (0)

#define TRUNNEL_DYNARRAY_ADD(elttype, da, v, on_fail) do { \
      if ((da)->n_ == (da)->allocated_) {                  \
        TRUNNEL_DYNARRAY_EXPAND(elttype, da, 1, on_fail);  \
      }                                                    \
      (da)->elts_[(da)->n_++] = (v);                       \
    } while (0)

#define TRUNNEL_DYNARRAY_LEN(da) ((da)->n_)

#define TRUNNEL_DYNARRAY_CLEAR(da) do {           \
    trunnel_free((da)->elts_);                    \
    (da)->elts_ = NULL;                           \
    (da)->n_ = (da)->allocated_ = 0;              \
  } while (0)

void *trunnel_reallocarray(void *a, size_t x, size_t y);

void *trunnel_dynarray_expand(size_t *allocated_p, void *ptr,
                              size_t howmanymore, size_t eltsize);

typedef void (*trunnel_free_fn_t)(void *);

void *trunnel_dynarray_setlen(size_t *allocated_p, size_t *len_p,
                              void *ptr, size_t newlen,
                              size_t eltsize, trunnel_free_fn_t free_fn,
                              uint8_t *errcode_ptr);

const char *trunnel_string_getstr(trunnel_string_t *str);
int trunnel_string_setstr0(trunnel_string_t *str, const char *inp, size_t len,
                           uint8_t *errcode_ptr);
int trunnel_string_setlen(trunnel_string_t *str, size_t newlen,
                           uint8_t *errcode_ptr);

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
