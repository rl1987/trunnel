#ifndef TRUNNEL_H_INCLUDED_
#define TRUNNEL_H_INCLUDED_

/* XXXX stick this in a file or something */
void *trunnel_reallocarray(void *a, size_t x, size_t y);
#define trunnel_abort() abort()

#define TRUNNEL_DYNARRAY_HEAD(name, elttype)       \
  struct name {                                    \
    size_t n_;                                     \
    size_t allocated_;                             \
    elttype *elts_;                                \
  }

#define TRUNNEL_DYNARRAY_INIT(elttype) { 0, 0, (elttype*)NULL }

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
    size_t newsize__ = (size_t)(howmanymore) + (da)->allocated_;     \
    elttype *newarray__ = NULL;                                      \
    if (newsize__ == 0)                                              \
      newsize__ = 8;                                                 \
    if (newsize__ < (da)->allocated_ * 2)                            \
      newsize__ = (da)->allocated_ * 2;                              \
    if (newsize__ <= (da)->allocated_ || newsize__ < (howmanymore))     \
      goto trunnel_alloc_failed;                                        \
    newarray__ = trunnel_reallocarray((da)->elts_, newsize__, sizeof(elttype)); \
    if (newarray__ == NULL)                                             \
      goto trunnel_alloc_failed;                                        \
    (da)->elts_ = newarray__;                                           \
    (da)->allocated_ = newsize__;                                       \
  } while (0)

#define TRUNNEL_DYNARRAY_ADD(elttype, da, v) do {          \
      if ((da)->n_ == (da)->allocated_) {                  \
        TRUNNEL_DYNARRAY_EXPAND(elttype, da, 0);           \
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

#endif

