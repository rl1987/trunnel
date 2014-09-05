#include "test.h"
#include "valid/leftover.h"

static void
test_lo_messages_invalid(void *arg)
{
  message_t *msg = NULL;
  uint8_t buf[128] = {0};
  (void)arg;

  /* Encoding NULL fails. */
  tt_int_op(-1, ==, message_encode(buf, sizeof(buf), NULL));

  msg = message_new();
  tt_int_op(-1, ==, message_encode(buf, sizeof(buf), msg));

  message_add_message(msg, (uint8_t)'a');
  message_add_message(msg, (uint8_t)'b');
  message_add_message(msg, (uint8_t)'c');
  tt_int_op(-1, ==, message_encode(buf, sizeof(buf), msg));
  message_set_stuff(msg, "ABC");
  tt_int_op(7, ==, message_encode(buf, sizeof(buf), msg));
  tt_mem_op(buf, ==, "abcABC\0", 7);

  message_set_stuff(msg, "AB");
  tt_int_op(-1, ==, message_encode(buf, sizeof(buf), msg));
  message_set_stuff(msg, "ABCD");
  tt_int_op(-1, ==, message_encode(buf, sizeof(buf), msg));
  tt_int_op(-2, ==, message_encode(buf, 7, msg));
  message_free(msg); msg = NULL;

 end:
  message_free(msg);
}

static void
test_lo_messages_truncated(void *arg)
{
  uint8_t buf[16] = { 0 };
  message_t *out = NULL, *msg2=NULL;
  unsigned i;
  (void)arg;

  memcpy(buf, "ABC", 4);

  /* Truncated on parse */
  for (i = 0; i < 4; ++i) {
    tt_int_op(-2, ==, message_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(4, ==, message_parse(&out, buf, 4));
  tt_int_op(0, ==, message_getlen_message(out));
  tt_str_op("ABC", ==, message_get_stuff(out));

  /* Truncated on encode */
  for (i = 0; i < 4; ++i) {
    tt_int_op(-2, ==, message_encode(buf, i, out));
  }
  msg2 = message_new();
  message_set_stuff(msg2, "DEF");
  message_add_message(msg2, 10);
  message_add_message(msg2, 11);
  message_add_message(msg2, 12);
  message_add_message(msg2, 13);
  for (i = 0; i < 8; ++i) {
    tt_int_op(-2, ==, message_encode(buf, i, msg2));
  }

  /* Success */
  tt_int_op(4, ==, message_encode(buf, 15, out));
  tt_int_op(8, ==, message_encode(buf, 15, msg2));

  message_free(out); out = NULL;
  memcpy(buf, "ABCD", 4);
  tt_int_op(-2, ==, message_parse(&out, buf, 4));

 end:
  message_free(out);
  message_free(msg2);
}

static void
test_lo_messages_accessors8(void *arg)
{
  message_t *msg = NULL;
  const uint8_t *inp;
  uint8_t buf[16];
  (void)arg;

  inp = ux("76616d7069726f74686575746973" "63636300");
  tt_int_op(18, ==, message_parse(&msg, inp, 18));
  tt_assert(msg);

  tt_int_op(14, ==, message_getlen_message(msg));
  tt_mem_op("vampirotheutis", ==, message_getarray_message(msg), 14);
  tt_int_op('m', ==, message_get_message(msg, 2));
  tt_str_op("ccc", ==, message_get_stuff(msg));

  message_set_message(msg, 0, (uint8_t)'V');
  message_set_stuff(msg, "woo");

  tt_mem_op("Vampirotheutis", ==, message_getarray_message(msg), 14);
  tt_str_op("woo", ==, message_get_stuff(msg));

  tt_int_op(0, ==, message_add_message(msg, '!'));
  tt_int_op(15, ==, message_getlen_message(msg));
  tt_mem_op("Vampirotheutis!", ==, message_getarray_message(msg), 15);

  message_setlen_message(msg, 6);
  tt_int_op(6, ==, message_getlen_message(msg));
  tt_mem_op("Vampir", ==, message_getarray_message(msg), 6);

  tt_int_op(10, ==, message_encode(buf, sizeof(buf), msg));
  tt_mem_op(buf, ==, ux("56616d706972" "776f6f00"), 10);

 end:
  message_free(msg);
}

static void
test_lo_messages_invalid16(void *arg)
{
  message16_t *msg = NULL;
  uint8_t buf[128] = {0};
  const uint8_t *inp;
  (void)arg;

  /* Encoding NULL fails. */
  tt_int_op(-1, ==, message16_encode(buf, sizeof(buf), NULL));

  /* Odd size fails */
  inp = ux("01" "0102030405060708");
  tt_int_op(-1, ==, message16_parse(&msg, inp, 9));

  msg = message16_new();
  tt_int_op(8, ==, message16_encode(buf, sizeof(buf), msg));

  message16_add_message(msg, 5);
  message16_add_message(msg, 1024);
  message16_add_message(msg, 4096);
  tt_int_op(14, ==, message16_encode(buf, sizeof(buf), msg));
  tt_mem_op(buf, ==, ux("0005""0400""1000" "0000000000000000"), 14);
  message16_free(msg); msg = NULL;

 end:
  message16_free(msg);
}

static void
test_lo_messages_truncated16(void *arg)
{
  uint8_t buf[32] = { 0 };
  message16_t *out = NULL, *msg2=NULL;
  unsigned i;
  (void)arg;

  /* Truncated on parse */
  for (i = 0; i < 8; ++i) {
    tt_int_op(-2, ==, message16_parse(&out, buf, i));
    tt_ptr_op(NULL, ==, out);
  }

  /* Success */
  tt_int_op(8, ==, message16_parse(&out, buf, 8));
  tt_int_op(0, ==, message16_getlen_message(out));
  tt_mem_op(ux("0000000000000000"), ==, message16_getarray_stuff(out), 8);

  /* Truncated on encode */
  for (i = 0; i < 4; ++i) {
    tt_int_op(-2, ==, message16_encode(buf, i, out));
  }
  msg2 = message16_new();
  message16_set_stuff(msg2, 0, 128);
  message16_add_message(msg2, 10);
  message16_add_message(msg2, 11);
  message16_add_message(msg2, 12);
  message16_add_message(msg2, 13);
  for (i = 0; i < 16; ++i) {
    tt_int_op(-2, ==, message16_encode(buf, i, msg2));
  }

  /* Success */
  tt_int_op(8, ==, message16_encode(buf, 32, out));
  tt_int_op(16, ==, message16_encode(buf, 32, msg2));

 end:
  message16_free(out);
  message16_free(msg2);
}

static void
test_lo_messages_accessors16(void *arg)
{
  message16_t *msg = NULL;
  const uint8_t *inp;
  uint8_t buf[32];
  (void)arg;

  inp = ux("76616d7069726f74686575746973" "0000006300000001");
  tt_int_op(22, ==, message16_parse(&msg, inp, 22));
  tt_assert(msg);

  tt_int_op(7, ==, message16_getlen_message(msg));
  tt_int_op(0x6d70, ==, message16_get_message(msg, 1));
  tt_int_op(99, ==, message16_get_stuff(msg, 3));
  tt_int_op(1, ==, message16_get_stuff(msg, 7));

  message16_set_message(msg, 0, (uint8_t)'V');
  message16_set_stuff(msg, 1, 255);

  tt_int_op('V', ==, message16_getarray_message(msg)[0]);
  tt_int_op(255, ==, message16_get_stuff(msg, 1));
  tt_int_op(8, ==, message16_getlen_stuff(msg));

  tt_int_op(0, ==, message16_add_message(msg, 0x1001));
  tt_int_op(8, ==, message16_getlen_message(msg));

  message16_setlen_message(msg, 9);
  tt_int_op(9, ==, message16_getlen_message(msg));

  tt_int_op(26, ==, message16_encode(buf, sizeof(buf), msg));
  tt_mem_op(buf, ==,
            ux("00566d7069726f74686575746973""1001""0000" "00ff006300000001"), 26);

 end:
  message16_free(msg);
}

static void
test_lo_messages_allocfail(void *arg)
{
#ifdef ALLOCFAIL
  message_t *msg = NULL;
  message16_t *msg16 = NULL;
  uint8_t buf[128] = {0};
  (void) arg;
  set_alloc_fail(1);
  tt_int_op(-1, ==, message_parse(&msg, buf, 6));
  set_alloc_fail(1);
  tt_int_op(-1, ==, message16_parse(&msg16, buf, 6));

  msg = message_new();
  msg16 = message16_new();

  set_alloc_fail(1);
  tt_int_op(-1, ==, message_add_message(msg, 0));
  tt_int_op(0, ==, message_getlen_message(msg));

  set_alloc_fail(1);
  tt_int_op(-1, ==, message16_add_message(msg16, 0));
  tt_int_op(0, ==, message16_getlen_message(msg16));

  set_alloc_fail(1);
  tt_int_op(-1, ==, message_setlen_message(msg, 5));
  tt_int_op(0, ==, message_getlen_message(msg));

  set_alloc_fail(1);
  tt_int_op(-1, ==, message16_setlen_message(msg16, 10));
  tt_int_op(0, ==, message16_getlen_message(msg16));

  set_alloc_fail(1);
  tt_int_op(-1, ==, message_set_stuff(msg, "woo"));

  tt_int_op(-1, ==, message_encode(buf, sizeof(buf), msg));
  tt_int_op(-1, ==, message16_encode(buf, sizeof(buf), msg16));

  message_clear_errors(msg);
  message16_clear_errors(msg16);

  tt_int_op(0, ==, message_set_stuff(msg, "woo"));
  tt_int_op(4, ==, message_encode(buf, sizeof(buf), msg));
  tt_int_op(8, ==, message16_encode(buf, sizeof(buf), msg16));

  message_free(msg); msg = NULL;
  message16_free(msg16); msg16 = NULL;

  set_alloc_fail(2);
  tt_int_op(-1, ==, message_parse(&msg, buf, 20));
  set_alloc_fail(3);
  tt_int_op(-1, ==, message_parse(&msg, buf, 20));
  set_alloc_fail(2);
  tt_int_op(-1, ==, message16_parse(&msg16, buf, 20));
 end:
  message_free(msg);
  message16_free(msg16);
#else
  (void)arg;
  tt_skip();
 end: ;
#endif
}

struct testcase_t leftover_messages_tests[] = {
  { "invalid8", test_lo_messages_invalid, 0, NULL, NULL },
  { "truncated8", test_lo_messages_truncated, 0, NULL, NULL },
  { "accessors8", test_lo_messages_accessors8, 0, NULL, NULL },
  { "invalid16", test_lo_messages_invalid16, 0, NULL, NULL },
  { "truncated16", test_lo_messages_truncated16, 0, NULL, NULL },
  { "accessors16", test_lo_messages_accessors16, 0, NULL, NULL },
  { "allocfail", test_lo_messages_allocfail, 0, NULL, NULL },
  END_OF_TESTCASES
};


