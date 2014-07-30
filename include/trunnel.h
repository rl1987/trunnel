#ifndef TRUNNEL_H_INCLUDED_
#define TRUNNEL_H_INCLUDED_

#define TRUNNEL_DYNARRAY_HEAD(name, elttype)       \
  struct name {                                    \
    size_t n_;                                     \
    size_t allocated_;                             \
    elttype *elts_;                                \
  }

#define TRUNNEL_DYNARRAY_INIT(elttype) { 0, 0, (elttype*)NULL }

#endif

