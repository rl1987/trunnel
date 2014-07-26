#include "test.h"

static void
test_strs_truncated(void *arg)
{
  const uint8_t *inp;
  uint8_t buf[16] = { 0 };
  strings_t *out = NULL;
  unsigned i;
  (void)arg;

  /* Too short, or truncated during string. */
  inp = ux("4142430000000000000041424300");
  for (i = 0; i < 14; ++i) {
    tt_int_op(-2, ==, strings_parse(&out, inp, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(14, ==, strings_parse(&out, inp, 14));

  /* Truncated on encode */
  for (i = 0; i < 14; ++i) {
    tt_int_op(-2, ==, strings_encode(buf, i, out));
  }

  /* Success */
  tt_int_op(14, ==, strings_encode(buf, 14, out));

 end:
  strings_free(out);
}

static void
test_strs_invalid(void *arg)
{
  uint8_t buf[16];
  strings_t strs;
  (void)arg;

  memset(&strs, 0, sizeof(strs));

  tt_int_op(-1, ==, strings_encode(buf, 16, NULL));

  /* no nul-terminated string */
  tt_int_op(-1, ==, strings_encode(buf, 16, &strs));
  strs.nt = strdup("ABC");
  /* Okay */
  tt_int_op(-1, !=, strings_encode(buf, 16, &strs));
  /* Too long; overwrites nul-terminator*/
  memcpy(strs.f, "abcdefghijk", 11);
  tt_int_op(-1, ==, strings_encode(buf, 16, &strs));

 end:
  if (strs.nt) free(strs.nt);
}

static void
test_strs_encdec(void *arg)
{
  uint8_t buf[32] = { 0 };
  uint8_t buf2[32] = { 0 };
  strings_t *out = NULL;
  (void)arg;

  memset(buf,0,32);
  memcpy(buf,"HelloWorld",10);
  memcpy(buf+10,"xyzzy",6);
  tt_int_op(16, ==, strings_parse(&out, buf, 32));
  tt_ptr_op(out, !=, 0);
  tt_str_op(out->f, ==, "HelloWorld");
  tt_str_op(out->nt, ==, "xyzzy");
  tt_int_op(16, ==, strings_encode(buf2, 32, out));
  tt_mem_op(buf, ==, buf2, 17);
  strings_free(out); out = NULL;

  memset(buf,0,32);
  memcpy(buf,"Moxie",5);
  memcpy(buf+10,"X",2);
  tt_int_op(12, ==, strings_parse(&out, buf, 32));
  tt_ptr_op(out, !=, 0);
  tt_str_op(out->f, ==, "Moxie");
  tt_str_op(out->nt, ==, "X");
  tt_int_op(12, ==, strings_encode(buf2, 32, out));
  tt_mem_op(buf, ==, buf2, 12);
  strings_free(out); out = NULL;

  memset(buf,0,32);
  tt_int_op(11, ==, strings_parse(&out, buf, 32));
  tt_ptr_op(out, !=, 0);
  tt_str_op(out->f, ==, "");
  tt_str_op(out->nt, ==, "");
  tt_int_op(11, ==, strings_encode(buf2, 32, out));
  tt_mem_op(buf, ==, buf2, 11);
  strings_free(out); out = NULL;

 end:
  strings_free(out);
}

struct testcase_t strings_tests[] = {
  { "truncated", test_strs_truncated, 0, NULL, NULL },
  { "invalid", test_strs_invalid, 0, NULL, NULL },
  { "encode-decode", test_strs_encdec, 0, NULL, NULL },
  END_OF_TESTCASES
};
