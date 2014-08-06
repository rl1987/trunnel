#include "trunnel-impl.h"
#include <stdlib.h>
#include <stdint.h>

#ifdef TRUNNEL_DEBUG_FAILING_ALLOC
int trunnel_provoke_alloc_failure = 0;
#endif

void *
trunnel_dynarray_expand(size_t *allocated_p, void *ptr,
                        size_t howmanymore, size_t eltsize)
{
  size_t newsize = howmanymore + *allocated_p;
  void *newarray = NULL;
  if (newsize < 8)
    newsize = 8;
  if (newsize < *allocated_p * 2)
    newsize = *allocated_p * 2;
  if (newsize <= *allocated_p || newsize < howmanymore)
    return NULL;
  newarray = trunnel_reallocarray(ptr, newsize, eltsize);
  if (newarray == NULL)
    return NULL;

  *allocated_p = newsize;
  return newarray;
}

void *
trunnel_reallocarray(void *a, size_t x, size_t y)
{
#ifdef TRUNNEL_DEBUG_FAILING_ALLOC
   if (trunnel_provoke_alloc_failure) {
     if (--trunnel_provoke_alloc_failure == 0)
       return NULL;
   }
#endif
   if (x > SIZE_MAX / y)
     return NULL;
   return realloc(a, x * y);
}

