<head>
<title>Trunnel manual</title>
   <style>
     <!--
        body { padding: 0 10% 0 15%; }
        h1 { text-indent: -10%; }
        h2 { text-indent: -7%; }
        h3,h4,h5,h6 {text-indent: -3%; }
     -->
   </style>
</head>

# Trunnel: a simple binary-format parser/encoder.

Trunnel is a tool that takes descriptions of binary formats and
generates C code to parse and encode them.  It's designed for
simplicity rather than maximum generality; if you need a tool that can
parse nearly anything at the cost of a bit more complexity, have a
look at "nail" instead.

Here are the goals for Trunnel:

   * Support all the binary formats used by Tor.
   * Generate human-readable, obviously correct code.
   * Generate secure code.
   * Generate code that compiles without warnings on a wide variety of
     compilers and platforms.
   * Provide a somewhat idiot-proof API.
   * Very high test coverage (currently, at 99% for code generator, 99% for
     generated code, and 100% for support library).
   * Be efficient enough for its performance not to matter for most
     applications.
   * Have a specification format that's easy to read and write.

Here are some non-goals for Trunnel:

   * Support every possible format.
   * Parse formats that aren't byte-based.
   * Parse formats that require backtracking.
   * Run as fast as possible.
   * Support very old versions of Python with the code generator.
   * Support pre-ANSI C with the code generator.
   * Generate optimal code
   * Generate code with no redundant checks
   * Handle input incrementally

## 1. About this document

I'll start with a quick example of the Trunnel workflow, and then move on to
document the format of the files that Trunnel uses to define binary formats.
After that, I'll briefly discuss the C functions that Trunnel exposes to the
outside world.

## 2. Working with Trunnel

Here's a quick overview of what Trunnel can do for you.

First, you write a simple format description of your binary formats in a
trunnel file.  It can look something like:

    const SHA256_LEN = 32;

    struct sha256_digest {
       u8 digest[SHA256_LEN];
    }

    struct message {
       u8 version;
       u8 command;
       u16 length IN [0..4096];
       u8 body[length]
       u8 digest[SHA256_LEN];
    }

Then you save that file with a name like `myformat.trunnel` and run trunnel
on it.  (Right now, that's `python -m trunnel myformat.trunnel` .)  If the
input file is well-formatted, Trunnel will generate a header file
(`myformat.h`) and an implementation file (`myformat.c`).

To use this code in your program, include the header file and build and link
with the C file.  You'll also need to distribute both generated code files,
along with trunnel-impl.h, trunnel.h, and trunnel.c.  (Trunnel will
emit those files for you when you run `python -m trunnel
--write-c-files`.)

Then you can write code that uses the generated functions documented in
myformat.h.

## 3. Writing trunnel definitions

A trunnel definition file can contain any number of three types of
definitions: constants, structure declarations, and extern declarations.

Both kinds of C comments are allowed: C99 comments that start with a
`//`, and the C comments that start with a `/*`.  Additionally, you
can insert doxygen-style comments that start with `/**` before any
structure, constant, or structure member.  These will be included
verbatim in the output file.

Constants are declared with:

    const <CONST_NAME> = <VAL> ;

As in:

    const N_ELEMENTS = 100;
    const U8_MAX = 0xff;

Constants can be used in the file anywhere that a number can be used.  The
name of a constant must be a C identifier in all-caps.

Structure declarations define a format that trunnel can parse.  They take
the form of:

    struct <ID> {
      <member>
      <member>
      ...
    }

As in:

    struct rgb {
       u8 r;
       u8 g;
       u8 b;
    }

The names of structures and their members may be any valid C
identifier containing at least one lowercase letter.  Structures can
contain 0, 1, or more members.  We define the possible member types
below.

An extern structure definition takes the form of:

    extern struct <ID>;

As in:

    extern struct message;

An extern struct definition declares that a structure will be defined in
another trunnel file, and that it's okay to use it in this trunnel file.


Finally, an options definition takes the form of:

    trunnel options <ID_LIST> ;

As in:

    trunnel options foo, bar, baz;

These options are used to control code generation.


### Structure members: integers

All integers are given as 8, 16, 32, or 64-bit values:

    u8 value_a;
    u16 value_b;
    u32 value_c;
    u64 value_d;

These values are encoded and parsed in network (big-endian) order.  The
corresponding values in C are generated as `uint8_t`, `uint16_t`, `uint32_t`,
and `uint64_t`.

(Signed values and little-endian values aren't supported.)

You can specify constraints for an integer value by providing a list of
one or more values and ranges.

    u8 version_num IN [ 4, 5, 6 ];
    u16 length IN [ 0..16384 ];
    u16 length2 IN [ 0..MAX_LEN ];
    u8 version_num2 IN [ 1, 2, 4..6, 9..128 ];

In a newly constructed structure, all integer fields are initialized to their
lowest constrained value (or to 0 if no constraint is given).

### Structure members: Nested structures

You can specify that one structure contains another, as in:

    struct inner inner_val;

You can also define the structure itself inline, as in:

    struct inner {
       u16 a;
       u16 b;
    } inner_val;

It's okay to use a structure before it's defined, but Trunnel does require
that structure definitions be non-circular.

In a newly constructed structure, all structure fields are initialized to
NULL.

### Structure members: NUL-terminated strings

You can specify a string whose length is determined by a terminating 0 (NUL)
byte, with:

    nulterm <ID>;

As in:

    nulterm string;

In a newly constructed structure, all nul-terminated string fields are
initialized to NULL.

### Structure members: fixed-length arrays

A structure can contain fixed-length arrays of integers, structures, or
(8-bit) characters.  The lengths of the arrays can be expressed as
decimal literals, hexadecimal literals, or constants:

    u8 ipv6_addr[16];
    u32 elements[N_ELEMENTS];
    struct rgb colors[2];
    char hostname[0x40];

Each of these types is parsed and encoded by parsing or encoding its
members the specified number of times.  Strings are not expected to be
NUL-terminated in the binary format.

Fixed-length arrays of integers are represented as arrays of the appropriate
uint\*_t type. Fixed-length arrays of structures are represented as arrays of
pointers to that structure type.  Fixed-length arrays of char are represented
as having one extra byte at the end, so that we can ensure that the C
representation of the array always ends with NUL -- internal NULs are
permitted, however.

In newly constructed structures, as before, integers are initialized to 0 and
structures are initialized to `NUL`.  Character arrays are initialized to be
filled with 0-valued bytes.

### Structure members: variable-length arrays

A structure can contain arrays of integers, structures, or characters whose
lengths depend on an earlier integer-valued field:

    u16 length;

    u8 bytes[length];
    u64 bignums[length];
    struct rgb colors[length];
    char string[length];

Each of these types is parsed and encoded by parsing or encoding its
members the specified number of times.  Strings are not expected to be
NUL-terminated in the binary format.

You can also specify that a variable-length array continues to the end of the
containing structure or union by leaving its length field empty:

    u8 remaining_bytes[];

    u32 remaining_words[];

    struct rgb remaining_colors[];

    char remaining_text[];

Of course, you couldn't end a structure with all four of those: they can't
_all_ extend to the end of a structure.  We also require that these "greedy"
arrays consume their input completely: If you specify `u32
remaining_words[];`, then the input must contain a multiple of 4 bytes, or it
will be invalid.

Variable-length arrays are represented internally with a dynamic array type
that expands as needed to hold all its elements.  You can inspect and modify
them through a set of accessor functions documented later on.

In newly constructed structures, all variable-length arrays are empty.

It's an error to try to encode a variable-length array with a length field if
that array's length field doesn't match its actual length.

### Structure members: zero-length indices into the input

Sometimes you need to record the position in the input the corresponds to
a position in the structure.  You can use an `@ptr` field to record
a position within a structure when parsing it:

    struct s {
      nulterm unsigned_header;
      @ptr start_of_signed_material;
      u32 bodylen;
      u8 body[bodylen];
      u64 flags;
      @ptr end_of_signed_material;
      u16 signature_len;
      u8 signature[signature_len];
    }

When an object of this type is parsed, then `start_of_signed_material`
and `end_of_signed_material` will get set to pointers into the input.
These pointers are only set when the input is parsed; you don't need
to set them to encode the object.

### Structure members: unions

You can specify that different elements should be parsed based on some
earlier integer field:

     u8 tag;
     union addr[tag] {
       4 : u32 ipv4_addr;
       5 : ; // Nothing to parse here.
       6 : u8 ipv6_addr[16];
       0xf0,0xf1 : u8 hostname_len;
              char hostname[hostname_len];
       0xF2 .. 0xFF : struct extension ext;
       default : fail;
     };

Only one variant of the union, depending on the given tag value, is parsed
or encoded.

You can specify the behavior of the union when no tag value is matched using
the `default:` label.  The `fail` production is a special value that causes
parsing and encoding to always fail for a given tag value. The `default: fail;`
case is understood unless some other behavior for default is given.

The fields in a union are represented by storing them in the generated
structure.  (To avoid user errors, no C union is generated.)  Their names are
prefixed with the name of the union, so `ipv4_addr` would be stored as
`addr_ipv4_addr`, and so on.

When encoding a union, only the fields referenced by the actual tag value are
inspected: it's okay to encode if the other fields are invalid.

### Structure members: unions with length constraints

Tagged unions are pretty useful for describing typed fields.  But many users
of typed fields need to support unknown types in order to future-proof
themselves against later extensions.  You can do this as:

    u8 tag;
    u16 length;
    union addr[tag] with length length {
       4 : u32 ipv4_addr;
       6 : u8 ipv6_addr[16];
       7 : ignore;
       0xEE : u32 ipv4_addr;
              ...;
       0xEF : u32 ipv4_addr;
              u8 remainder[];
       0xF0 : char hostname[];
       default: u8 unrecognized[];
    };

Here, the union is required to take up a number of bytes dependent on the
value of `length`.  The `hostname` and `unrecognized` cases extend to the end
of the union.  The `...` in the `0xEE` case indicates that extra bytes are
accepted and ignored, whereas in the `0xEF` case, extra bytes are accepted and
stored.  Unless otherwise specified, the length field must match the length
of the fields in the union exactly.

When encoding a union of this kind, you do _not_ need to set the 'length'
field; trunnel will fill it in for you in the output automatically based on
the actual length.

(*In a future version of Trunnel*, length constraints might be supported
independently of unions; the code is orthogonal internally.)

### Structure variants: end-of-string constraints

By default, trunnel allows extra data to appear after the end of a
structure when parsing it from the input.  To suppress this behavior
for a given structure, you can give an end-of-string constraint:

    struct fourbytes {
       u16 x;
       u16 y;
       eos;
    }

(*This feature might go away* in a future version if it doesn't turn
out to be useful.)

### Fields that extend up to a certain point before the end of the structure

Some data formats have fixed-width fields at the end, and
indeterminate-extent fields in the middle.  For example, you might
have an "encrypted message" format where the first 16 bytes are a
salt, the last 32 bytes are a message authentication code, and
everything in the middle is an encrypted message.  You can express
this in Trunnel with:

    struct encrypted {
       u8 salt[16];
       u8 message[..-32];
       u8 mac[32];
    }

The "..-32" notation means that the array should try to consume
everything up to but not including the last 32 bytes of the message.

You can also use this notation to indicate the extent of a union:

    struct encrypted {
       u8 type;
       union u[type] with length ..-32 {
          1: u8 bytes[];
          2: u8 salt[16];
             u8 other_bytes[];
       }
       u64 data[4];
    }

### Parameterizing structures

Some protocols have the type of length of some structure fields depend
on settings elsewhere in the protocol.  For example, you might have a
TLS-like protocol where each encrypted records's format depends on
some session parameters.

To support this, trunnel provides context-dependent objects:

    context stream_settings {
       u8 block_mode;
       u8 iv_len;
       u8 block_len;
       u8 mac_len;
    }

    struct encrypted_record with context stream_settings {
       u8 iv[stream_settings.iv_len];
       union msg[stream_settings.block_mode] {
          0: u16 n_bytes; u8 bytes[n_bytes];
          1: u16 n_blocks; struct block[n_blocks];
       };
       u8 mac[stream_settings.maclen];
    }

    struct block with context stream_settings {
       u8 body[stream_settings.block_len]
    }

In the example above, the lengths of the `mac`, `iv`, and `body`
fields do not depend on values within the structures themselves;
instead, they depend on the values set within the `stream_settings`
context.  It's similar for the tag of the `msg` union: it depends on a
value in the stream_settings context.

Note also that the `stream_settings` context can propagate from the
`encrypted_record` structure to the `block` structure it contains.  It
is an error to include a context-dependent structure in an environment
that doesn't declare the same context dependency.

Contexts may only include integer types, and may not declare integer
restrictions.

## 4. Controlling code generation with options

Two options are supported in Trunnel right now:

    trunnel option opaque;
    trunnel option very_opaque;

The `opaque` option makes the generated structures not get exposed in the
generated header files by default.  You can override this and expose a single
structure name by defining `TRUNNEL_EXPOSE_<STRUCTNAME>_` in your C before
including the generated header.

The `very_opaque` option prevents the generated structures from being put
into the generated header files at all: you will only be able to access their
fields with the generated accessor functions.

## 5. Using Trunnel's generated code

When you run Trunnel on `module.trunnel`, it generates `module.c` and
`module.h`.  Your program should include `module.h`, and compile and link
`module.c`.

For each structure you define in your trunnel file, Trunnel will generate a
structure with an `_st` suffix and a typedef with a `_t` suffix.  For
example, `struct rgb` in your definition file wile generate `struct rgb_st;`
and `typedef struct rgb_st rgb_t;` in C.

In addition to consulting the documentation below, you can also read the
comments in the generated header file to learn how to use the generated
functions.

In the examples below, I'll be assuming a structure called `example`, defined
with something like:

    struct example {
       u16 shortword;
       /* Contents go here... */
    }

### Generated code: creating and destroying objects

Every object gets a `new` and a `free` function:

     example_t *example_new(void);
     void example_free(example_t *obj);

The `example_new()` function creates a new `example_t`, with its fields
initialized to 0, NULL, or to their lowest legal value (in the cases of
constrained integers).

The `example_free()` function frees the provided object, along with all the
objects inside it.  It's okay to call it with NULL.

### Generated code: encoding an object

If you have a filled-in object, you can encode it into a buffer:

     ssize_t example_encode(uint8_t *buf, size_t buf_len, const example_t *obj);

The `buf_len` parameter describes the number of available bytes in `buf` to
use for encoding `obj`.  On success, this function will return the number of
bytes that it used.  On failure, the function will return -2 on a truncated
result, where providing a longer `buf_len` might make it succeed, and will
return -1 if there is an error that prevents encoding the object entirely.

You can find out the required buffer length before the encoding, if you like:

     ssize_t example_encoded_len(const example_t *obj);

This function returns a negative value on an error.  On success, it
returns the suggested length of the buffer to allocate for encoding
'obj'.  Note that this number may be an underestimate or an
overestimate: you still need to check for truncation when encoding.

### Generated code: checking an object for correctness

If you want to find out whether you can encode an object, or find out why an
encode operation has just failed, you can call:

     const char *example_check(const example_t *obj);

This function returns `NULL` if the object is correct and encodeable, and
returns a string explaining what has gone wrong otherwise.

### Generated code: parsing an object

Here's the big one: parsing an object form a binary string.

    ssize_t example_parse(example_t **out, const uint8_t *inp, size_t inp_len);

Here we take up to `inp_len` bytes from the buffer `inp`.  On success, this
function returns the number of bytes actually consumed, and sets `*out` to a
newly allocated `example_t` holding the parsed object.  On failure, it returns
-1 if the input was completely invalid, and -2 if it was possibly truncated.

Note that truncation detection depends on the actual layout of your
objects.  Some valid encoded objects are prefixes of other encoded
objects.  In these cases, there's no way to tell that truncation has
occurred.

### Generated code: accessor functions

For each struct member, Trunnel creates a set of set and get functions to
inspect and change its value.  If you've specified the `opaque` or `very_opaque`
option, these are the only (recommended) way to view or modify a structure.

Each type has its own set of accessors.

By convention, the set accessors (the ones that modify the objects) return `0`
on success and `-1` on failure.  Additionally on failure, they set an error
code on the object that prevents the object from being encoded unless the
error code is cleared.

**Integers** and **nul-terminated strings** have a` get` and `set` function:

     struct example {
        u8 a;
        u16 b in [ 5..5000 ];
        nulterm s;
     }

will produce these self-explanatory accessor functions:

     uint8_t example_get_a(const example_t *ex);
     int example_set_a(const example_t *ex, uint8_t val);
     uint16_t example_get_b(const example_t *ex);
     int example_set_b(const example_t *ex, uint16_t val);
     const char *example_get_s(const example_t *ex);
     int example_set_s(const example_t *ex, const char *val);

Note that the string set function makes a copy of its input string.

**Structures** have a get, set, and set0 function:

     struct example {
        struct rgb xyz;
     }

becomes:

     rgb_t *example_get_xyz(example_t *ex);
     int example_set_xyz(example_t *ex, rgb_t *val);
     int example_set0_xyz(example_t *ex, rgb_t *val);

The `set` and `set0` functions behave identically, except that the set function
frees the previous value of the xyz field (if any), whereas the set0 function
will overwrite it.

**All arrays** have functions to inspect them and change their members, so
that:

    struct example {
       struct rgb colors[16];
    }
    // OR
    struct example {
       u8 n;
       struct rgb colors[n];
    }

will both produce:

    size_t example_getlen_colors(const example_t *example);
    rgb_t **example_getarray_colors(const example_t *example);
    rgb_t *example_get_colors(const example_t *example, size_t idx);
    int example_set_colors(example_t *example, size_t idx, rgb_t *val);
    int example_set0_colors(example_t *example, size_t idx, rgb_t *val);

In this case, the getlen function returns the length of the array, the
getarray function returns a pointer to the array itself, and the `get` and
`set` and `set0` functions access or replace the value of the array at a
given index.  The set0 function is only generated in the case of an array of
structures: when it is generated, `set` frees the old value of the array at
that index (if any), and `set0` does not.

**Variable-length arrays** additionally have functions that adjust their
lengths, so that :

     struct example {
         u8 n;
         struct rgb colors[n];
     }

will also produce:

     int example_add_colors(example_t *example, rgb_t *val);
     int example_setlen_colors(example_t *example, size_t newlen);

The `add` function appends a new item to the end of the array.  The `setlen`
function changes the current length of the array.  (If the length increases,
the new fields are padded with `0` or `NULL` as appropriate.  If the length
decreases, the removed members are freed if necessary.)

Note that the length field `n` is not automatically kept in sync with the
length of the dynamic array `colors`.

Finally, **variable-length arrays of char** have extra functions to help you
access them as variable-length strings:

    struct example {
       u8 n;
       char value[n];
    }

produces:

    const char *example_getstr_value(example_t *obj);
    int example_setstr_value(example_t *obj, const char *val);
    int example_setstr0_value(example_t *obj, const char *val, size_t len);

The `getstr` function is identical to `getarray`, except that it guarantees a
NUL-terminated result.  (It can return `NULL` if it fails to NUL-terminate the
answer.)  This time the `setstr0` function takes a new value and its length;
the `setstr` function just takes a value and assumes it is NUL-terminated.

### Generated code: the impact of contexts

If you declare context-dependent structures, Trunnel will add extra
context arguments to the generated `encode`, `parse`, and `check`
functions.  For example, if you say:

    context len {
       u16 len;
    }
    struct msg with context len {
       u8 tag;
       u16 items[len.len];
    }

Then trunnel will generate those functions with the protptypes:

    ssize_t msg_encode(uint8_t *buf, size_t buf_len, msg_t *obj,
                       const len_t *len_ctx);
    ssize_t msg_encoded_len(msg_t *obj, const len_t *len_ctx);
    const char *msg_check(const msg_t *obj, const len_t *len_ctx);
    ssize_t msg_parse(msg_t **out, const uint8_t *inp, size_t inp_len,
                      const len_t *len_ctx);

Trunnel will also generate a declaration for the context type, along
with `new`, `free`, and accessor functions for it:

    struct len_t {
       uint16_t len;
    };
    len_t *len_new(void);
    void len_free(len_t *len);
    int len_set_len(len_t *len, uint16_t newval);
    uint16_t len_get_len(const len_t *len);

### Extending trunnel

You can extend Trunnel using the 'extern struct' mechanism described above.
All you need to do is provide your own structure definition, along with
`parse`, `encode`, `free`, and `check` functions.  The generated trunnel code
will use those functions as appropriate to access your extended type.

### Overriding allocators and other internal functions

By default, trunnel uses the libc malloc implementation for its
allocation.  You can override this by defining a "trunnel-local.h"
file, and defining the TRUNNEL_LOCAL_H macro when compiling any
trunnel C files.  When you do this, your "trunnel-local.h" will get
included before any generated trunnel code.

To replace the allocator, you must use #define to declare replacements
for the following functions:

  * `trunnel_malloc`
  * `trunnel_calloc`
  * `trunnel_realloc` OR `trunnel_reallocarray`
  * `trunnel_free_` (note trailing underscore
  * `trunnel_strdup`

These functions work equivalently to their libc counterparts, and take
arguments in the same order.

You can also replace trunnel's internal-error behavior by defining one
or more of these:

  * `trunnel_abort`
  * `trunnel_assert`

These macros are also expected to behave equivalently to their libc
counterparts.  They are only invoked in the case of an internal
programming error in Trunnel -- if Trunnel is implemented correctly,
they should be unreachable.

Finally, if you want to ensure that all objects freed by trunnel are
wiped from memory before they're freed, you can define a
`trunnel_memwipe` function.  For example:

    #define trunnel_memipe(mem, len)  memset_s((mem), 0, (len));

Note that the standard caveats about wiping memory apply: if this
matters to you, you should know why you should be using memset_s or
explicit_bzero instead of memset here.


### Notes on thread-safety

There are no global structures and there are no locks.  It's up to you to
avoid calling multiple functions at once on the same structure.  If you
manage to avoid that, Trunnel should be thread-safe.
