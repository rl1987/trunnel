# CodeGen.py -- code generator for trunnel.
#
# Copyright 2014, The Tor Project, Inc.
# See license at the end of this file for copying information.

"""This is the code-generator part of Trunnel.

  It has everything to generate the declarations and methods.  It also
  performs checking and annotation for Trunnel ASTs.

  The command-line interface is at the end of this module.

  CODE GENERATION NOTES: Representing data in C.

   Integer types are represented as uint8_t, uint16_t, uint32_t, or uint64_t.

   Structures nested directly inside structures are stored as pointers.

   "nulterm" strings are represented as char *, pointing to a
   nul-terminated string.

   Fixed-length arrays are represented by fixed-length arrays of the
   appropriate type.  Fixed-length arrays of integer are represented as
   uint8_t[N], uint16_t[N], uint32_t[N], or uint64_t[N].  Fixed-length
   arryas of char are represented as char[N+1], with the last byte always
   set to NUL.  And fixed-length arrys of "struct X" are represented
   as arrays of pointer, as in "struct *X[N];"

   Variable-length arrays are represented with the TRUNNEL_DYNARRAY
   macros.  Variable-length arrays of integer or char are represented
   as TRUNNEL_DYNARRAYs of uint8_t, uint16_t, uint32_t, uint64_t, or
   char.  And variable-length arrys of "struct X" are represented as
   arrays of pointer, as in TRUNNEL_DYNARRAY of "struct *".

   Unions are represented by including their members inline, prefixed
   with the name of the union and an underscore.  (Note: Unions are
   NOT represented by unions right now.  I might revisit this
   decision, though.)

  CODE GENERATION NOTES: Generated functions.

   For every type declared as "struct typename", we generate these
   public functions.  See the associated generators for more information
   about how they work and what they do.

      typename_t *typename_new(void) -- see NewFnGenerator.
      void typename_free(typename_t *) -- see FreeFnGenerator.
      ssize_t typename_encode(uint8_t *, size_t, const typename_t *obj)
                                                   -- see EncodeFnGenerator
      ssize_t typename_parse_into(typename_t **, const uint8_t *, size_t)
                                                   -- see ParseFnGenerator
      const char *typename_check(const typename_t *) -- see CheckFnGenerator

   We also generate these static, non-exported functions. See the
   associated generators for more information about how they work and
   what they do.

      void typename_clear(typename_t *) -- see FreeFnGenerator.
      ssize_t typename_parse_into(typename_t *, const uint8_t *, size_t)
                                                   -- see ParseFnGenerator

   For every member, we generate two or more accessor functions.  See
   AccessorFnGenerator for more information about them.

"""

import os
import re
import textwrap
import trunnel.Grammar


class ASTVisitor(object):

    """Visitor pattern for an AST object.  When you call
       ASTVisitor.visit(foo) on an object of type X, it calls the
       appropriate visitX method on the visitor.
    """

    def __init__(self):
        pass

    def visit(self, ast, *args):
        name = "visit" + ast.__class__.__name__
        method = getattr(self, name, self.visit_other)
        return method(ast, *args)

    def visit_other(self, ast, *args):
        """Invoked when there is no visitor method for a given AST node"""
        raise ValueError("visit" + ast.__class__.__name__)


class CheckError(Exception):
    pass

# Map from integer field width to the maximum for that field.
TYPE_MAXIMA = {
    8: (1 << 8) - 1,
    16: (1 << 16) - 1,
    32: (1 << 32) - 1,
    64: (1 << 64) - 1,
}

# Map from integer field width to the function (if any) that you call
# to put network-order fields of that width into host-order fields.
HTON_FN = {
    8: '',
    16: 'trunnel_htons',
    32: 'trunnel_htonl',
    64: 'trunnel_htonll'
}

# Map from integer field width to the function (if any) that you call
# to put host-order fields of that width into network-order fields.
NTOH_FN = {
    8: '',
    16: 'trunnel_ntohs',
    32: 'trunnel_ntohl',
    64: 'trunnel_ntohll'
}


class Checker(ASTVisitor):

    """Validation visitor for a Trunnel AST.  Ensures consistency and
       well-formedness for the AST.
    """
    #
    # structNames -- a set of all the identifiers used as structure names.
    # constNames -- a set of all the identifiers used as constant names.
    # constValues -- a map from constant name to integer constant value.
    # structFieldNames -- if currently analyzing a structure, a set
    #     of all names used as member identifiers.  Otherwise None.
    # structIntFieldNames -- if currently analyzing a structure, a map of
    #     of all integer-typed fields to their width. Otherwise None.
    # structIntFieldUsage --  if currently analyzing a structure, a map of
    #     of all integer-typed fields to "TL" for the ones that have been
    #     usage as tag or array length, or "CL" for ones that have been used
    #     for SMLenConstrained length.
    # structUses -- a map from each structure's name to a set of all the other
    #     structures that structure uses.
    # memberPrefix -- a prefix to be appended to each member's name when
    #     determining that name for its C identifier.
    # sortedStructs -- the names of all structures analyzed, topologically
    #     sorted so that no structure appears before any structure that it
    #     uses.
    #
    # structName -- the name of the current structure we're analyzing.
    # containing -- a string holding the thing that contains what we're
    #     analyzing now.
    #
    # curunion -- the SMUnion member we're analyzing right now.
    # lenFieldDepth -- count of the SMLenConstraineds containing
    #     us right now.
    # unionName -- the name of the SMUnion we're analyzing right now.
    # unionTagMax -- the integer maximum value for the tag field of
    #     the SMUnion we're analyzing right now.
    # foundDefaults -- the number of default: cases we've found in the
    #     SMUnion we're analyzing right now.

    def __init__(self):
        ASTVisitor.__init__(self)
        self.structNames = set()
        self.constNames = set()
        self.constValues = {}
        self.contextNames = set()  # XXXX
        self.structFieldNames = None
        self.structIntFieldNames = None
        self.structIntFieldUsage = None
        self.structUses = {}
        self.structUsesContexts = {}  # XXXX
        self.memberPrefix = ""
        self.sortedStructs = None
        self.lenFieldDepth = 0

    def visitFile(self, f):
        # Check options.
        if "opaque" in f.options and "very_opaque" in f.options:
            raise CheckError("can't use both 'opaque' and 'very_opaque'")

        # Build up the sets of all constant and structure names.
        for c in f.constants:
            if c.name in self.constNames:
                raise CheckError("duplicate constant name %s" % c.name)
            self.constNames.add(c.name)
        for es in f.externStructs:
            n = es.name
            if n in self.structNames:
                raise CheckError("duplicate structure name %s" % n)

            self.structNames.add(n)
            self.structUsesContexts[n] = set(es.contextList)
            self.structUses[n] = set()
            self.structUsesContexts[n] = set()
        for d in f.declarations:
            if d.name in self.structNames:
                raise CheckError("duplicate structure name %s" % d.name)
            if d.isContext():
                self.contextNames.add(d.name)
            else:
                self.structNames.add(d.name)

        # Recurse through all the constants and structures.
        f.visitChildren(self)

        # Compute the transitive closure of self.structUses
        while True:
            changed = False
            for structname, uses in list(self.structUses.items()):
                oldlen = len(uses)
                newuses = uses.copy()
                for used in uses:
                    newuses.update(self.structUses[used])
                uses.update(newuses)
                if len(uses) != oldlen:
                    changed = True

            if not changed:
                break

        # check for cycles
        for structname, uses in list(self.structUses.items()):
            if structname in uses:
                raise CheckError(
                    "There is a cycle in the %s structure" % structname)

        # check for context mismatch.
        for structname, uses in list(self.structUses.items()):
            for u in uses:
                missing = self.structUsesContexts[
                    u] - self.structUsesContexts[structname]
                if missing:
                    raise CheckError(
                        "{0} contains {1}, which uses contexts ({2}), but {0} does not use those contexts.".format(structname, u, ",".join(missing)))

        # Perform a topological sort.
        sorted_structs = []
        removed = set()
        while len(self.structUses):
            removed_this_time = []
            for structname, uses in list(self.structUses.items()):
                uses.difference_update(removed)
                if len(uses) == 0:
                    removed_this_time.append(structname)

            removed_this_time.sort()
            sorted_structs.extend(removed_this_time)
            removed.update(removed_this_time)

            for s in removed_this_time:
                del self.structUses[s]

        externNames = set(es.name for es in f.externStructs)

        self.sortedStructs = [
            s for s in sorted_structs if s not in externNames]

    def visitConstDecl(self, cd):
        self.constValues[cd.name] = cd.value.value

    def visitStructDecl(self, sd):
        self.structFieldNames = set()
        self.structIntFieldNames = {}
        self.structIntFieldUsage = {}
        self.structName = sd.name
        self.structUses[sd.name] = set(sd.contextList)
        self.structUsesContexts[sd.name] = set(sd.contextList)
        sd.visitChildren(self)
        sd.constrainedIntFields = set(self.structIntFieldUsage.keys())
        self.structFieldNames = None
        self.structIntFieldNames = None
        self.structIntFieldUsage = None

    def addMemberName_(self, m):
        """Add m as a name of a member of the current structure, checking for
           duplicates."""
        if m in self.structFieldNames:
            raise CheckError("duplicate field %s.%s" % (self.structName, m))
        self.structFieldNames.add(m)

    def addMemberName(self, m):
        self.addMemberName_(m)

        if self.memberPrefix != "":
            m = self.addMemberName_("%s%s" % (self.memberPrefix, m))

    def visitSMInteger(self, smi):
        self.addMemberName(smi.name)

        self.structIntFieldNames[smi.name] = smi.inttype.width

        self.containing = "%s.%s" % (self.structName, smi.name)
        self.containingType = smi.inttype
        smi.visitChildren(self)
        self.containing = None
        self.containingType = None

    def visitIntConstraint(self, ic):
        maximum = TYPE_MAXIMA[self.containingType.width]
        self.checkIntegerList(ic.ranges, maximum, None)
        ic.ranges.sort()

    def visitSMStruct(self, sms):
        self.addMemberName(sms.name)

        if sms.structname not in self.structNames:
            raise CheckError("Unrecognized structure %s used in %s" % (
                sms.structname, self.structName))

        self.structUses[self.structName].add(sms.structname)

    def visitSMFixedArray(self, sfa):
        self.addMemberName(sfa.name)

        if type(sfa.width) == str:
            self.expandConstant(sfa.width)

        if type(sfa.basetype) == str:
            if sfa.basetype not in self.structNames:
                raise CheckError("Unrecognized structure %s used in %s.%s" % (
                    sfa.basetype, self.structName, sfa.name))

            self.structUses[self.structName].add(sfa.basetype)

    def visitSMVarArray(self, sva):
        self.addMemberName(sva.name)

        if sva.widthfield is not None:
            self.checkIntField(sva.widthfield, "array length", "%s.%s" %
                               (self.structName, sva.name))

        if type(sva.basetype) == str:
            if sva.basetype not in self.structNames:
                raise CheckError("Unrecognized structure %s used in %s.%s" % (
                    sva.basetype, self.structName, sva.name))

            self.structUses[self.structName].add(sva.basetype)

    def visitSMString(self, sms):
        self.addMemberName(sms.name)

    def visitSMPosition(self, smp):
        self.addMemberName(smp.name)

    def visitSMLenConstrained(self, sml):
        if sml.lengthfield != None:
            self.checkIntField(
                sml.lengthfield, "union length", self.structName)
        self.lenFieldDepth += 1
        if self.lenFieldDepth >= 2:
            # This is an undesirable restriction, but the alternative
            # is to fix some really knotty bugs.
            raise CheckError("Nested fields with length constraints.")

        sml.visitChildren(self)
        self.lenFieldDepth -= 1

    def visitSMUnion(self, smu):
        self.addMemberName(smu.name)

        self.checkIntField(smu.tagfield, "tag", "%s.%s" %
                           (self.structName, smu.name))

        self.curunion = smu
        self.unionName = smu.name
        self.unionMatching = []
        if '.' in smu.tagfield:
            self.unionTagMax = (1 << 64) - 1  # XXXX wrong
        else:
            self.unionTagMax = TYPE_MAXIMA[
                self.structIntFieldNames[smu.tagfield]]
        self.containing = "%s.%s" % (self.structName, smu.name)
        self.memberPrefix = smu.name + "_"
        self.foundDefaults = 0
        smu.visitChildren(self)
        self.curunion = None

        self.unionMatching.sort()
        lasthi = -1
        for lo, hi in self.unionMatching:
            if lo <= lasthi:
                raise CheckError("Duplicate tag values in %s.%s" %
                                 (self.structName, smu.name))
            assert hi >= lo
            lasthi = hi

        if self.foundDefaults > 1:
            raise CheckError("Multiple default cases in %s.%s" %
                             (self.structName, smu.name))
        elif self.foundDefaults == 0:
            # If no default was given, the default is 'fail'
            smu.members.append(
                trunnel.Grammar.UnionMember(None, [trunnel.Grammar.SMFail()]))

        self.memberPrefix = ""
        self.unionName = None
        self.unionMatching = None
        self.unionTagMax = None
        self.containing = None

    def visitUnionMember(self, um):
        if um.tagvalue is not None:
            self.checkIntegerList(
                um.tagvalue, self.unionTagMax, self.unionMatching)
        else:
            self.foundDefaults += 1

        # save list of int fields so that other declarations can't
        # depend on integers declared here.
        saved = self.structIntFieldNames.copy()
        um.visitChildren(self)
        self.structIntFieldNames = saved

    def visitSMEos(self, eos):
        pass

    def visitSMFail(self, fail):
        pass

    def visitSMIgnore(self, ignore):
        if self.lenFieldDepth == 0:
            raise CheckError(
                "'...' found outside of a length-constrained element")

    def checkIntegerList(self, lst, maximum, expandInto=None):
        """Given a list of (lo,hi) integer ranges, check it for correctness."""
        for lo, hi in lst:
            if type(lo) == str:
                lo = self.expandConstant(lo)
            if type(hi) == str:
                hi = self.expandConstant(hi)
            if lo > hi:
                raise CheckError("Bad range in %s", self.containing)
            if lo > maximum:
                raise CheckError("Tag value %s out of range in %s",
                                 lo, self.containing)
            if hi > maximum:
                raise CheckError("Tag value %s out of range in %s",
                                 hi, self.containing)

            if expandInto != None:
                expandInto.append((lo, hi))

    def expandConstant(self, const):
        """Given a constant name, return its value or give an error if it
           has no value."""
        try:
            return self.constValues[const]
        except KeyError:
            raise CheckError("Unrecognized constant %s in %s" % (
                const, self.containing))

    def checkIntField(self, fieldname, ftype, inside):
        """Check whether a reference to an integer field is correct."""
        if '.' in fieldname:
            ctx, field = fieldname.split('.', 2)
            if ctx not in self.contextNames:
                raise CheckError("Unrecognized context %s for %s in %s" % (
                    fieldname.context, ftype, inside))
            # XXXXX Check that the field really exists
            return

        if fieldname not in self.structFieldNames:
            raise CheckError("Unrecognized %s field %s for %s" % (
                ftype, fieldname, inside))

        if fieldname not in self.structIntFieldNames:
            raise CheckError("Non-integer %s field %s for %s" % (
                ftype, fieldname, inside))

        note = {'tag': 'TL', 'array length': 'AL',
                'union length': 'CL'}[ftype]
        try:
            curUsage = self.structIntFieldUsage[fieldname]
            if curUsage != note:
                raise CheckError(
                    "Invalid mixed usage for field %s" % fieldname)
        except KeyError:
            self.structIntFieldUsage[fieldname] = note


class Annotator(ASTVisitor):

    """Annotating visitor for a Trunnel AST.  This visitor's job is to
       annotate struct members with cross-references to other struct
       members, and to set everything's C name.
    """
    #
    # prefix -- as Checker.memberPrefix
    # memberByName -- a map from member name to StructMember
    # cur_struct -- the name of the current StructDecl we're annotating
    # cur_struct_obj -- the current StructDecl we're annotating
    # after_leftover_field -- true if we are after an SMLenConstrained
    #   that uses the 'leftover bytes' feature.
    # file -- the Grammar.File object we're currently checking

    def __init__(self):
        ASTVisitor.__init__(self)
        self.prefix = ""
        self.memberByName = None

    def visitFile(self, f):
        self.file = f
        f.visitChildren(self)

    def visitConstDecl(self, cd):
        pass

    def visitStructDecl(self, sd):
        self.cur_struct_obj = sd
        self.cur_struct = sd.name
        self.cur_struct_obj.has_leftover_field = False
        self.after_leftover_field = False
        self.memberByName = {}
        sd.lengthFields = {}
        sd.visitChildren(self)
        self.cur_struct = None
        self.cur_struct_obj = None
        self.memberByName = None

    def annotateMember(self, member):
        """Set the c_name field of a StructMember, and add it to
           self.memberByName"""
        member.c_name = "%s%s" % (self.prefix, member.name)
        member.c_fn_name = member.c_name
        member.after_leftover_field = self.after_leftover_field
        self.memberByName[member.name] = member

    def visitSMInteger(self, smi):
        self.annotateMember(smi)

    def visitSMStruct(self, sms):
        self.annotateMember(sms)
        sms.structDeclaration = self.file.getDeclaration(sms.structname)

    def visitSMFixedArray(self, sfa):
        self.annotateMember(sfa)
        if type(sfa.basetype) == str:
            sfa.structDeclaration = self.file.getDeclaration(sfa.basetype)

    def visitSMVarArray(self, sva):
        self.annotateMember(sva)
        if sva.widthfield is not None:
            sva.widthfieldmember = self.memberByName.get(sva.widthfield)
        if type(sva.basetype) == str:
            sva.structDeclaration = self.file.getDeclaration(sva.basetype)

    def visitSMString(self, ss):
        self.annotateMember(ss)

    def visitSMPosition(self, smp):
        self.annotateMember(smp)

    def visitSMLenConstrained(self, sml):
        sml.lengthfieldmember = None
        if sml.lengthfield is not None:
            m = self.memberByName.get(sml.lengthfield)
            if m is not None:
                self.cur_struct_obj.lengthFields[m.c_name] = m
                sml.lengthfieldmember = m
        else:
            self.cur_struct_obj.has_leftover_field = True
        sml.after_leftover_field = self.after_leftover_field
        sml.visitChildren(self)

        if sml.lengthfield is None:
            self.after_leftover_field = True

    def visitSMUnion(self, smu):
        self.annotateMember(smu)
        self.prefix = smu.name + "_"
        prev_alf = next_alf = self.after_leftover_field
        for child in smu.members:
            self.after_leftover_field = prev_alf
            self.visit(child)
            if self.after_leftover_field:
                next_alf = True
        self.after_leftover_field = next_alf
        self.prefix = ""
        smu.tagfieldmember = self.memberByName.get(smu.tagfield)

    def visitUnionMember(self, um):
        um.visitChildren(self)

    def visitSMFail(self, fail):
        pass

    def visitSMEos(self, eos):
        pass

    def visitSMIgnore(self, ignore):
        pass


def dedent_code(s):
    """Given a string 's', see whether all nonblank lines in 's' are prefixed
       with some number of spaces.  If so, remove that number of spaces from
       the front of every line (except possibly blank lines).
    """
    lines = s.split("\n")
    if lines[0] == "":
        del lines[0]
    if lines[-1] == "":
        del lines[-1]
    min_indentation = 10000
    for line in lines:
        indent = len(re.match(r"^ *", line).group(0))
        if indent < len(line) and indent < min_indentation:
            min_indentation = indent
    assert min_indentation < 10000
    result = []
    indentation = " " * min_indentation
    for line in lines:
        if line.startswith(indentation):
            result.append(line[min_indentation:])
        else:
            result.append(line)
    return "\n".join(result)


class CodeGenerator(ASTVisitor):

    """Helper class for code-generating visitors: tracks current indentation
       level and writes blocks of code.
    """
    #
    # w_ -- a function to use to emit code.  Writes strings.
    # indent -- The current indentation prefix
    # action -- The verb to use in code-documentation when saying what
    #   we're about to do to a struct member

    def __init__(self, writefn):
        self.w_ = writefn
        self.w_real = self.w
        self.indent = ""
        self.action = "Handle"

    def w(self, string):
        """Write some code, with the current indentation level added to
           each line."""
        lines = string.split("\n")
        if lines[-1] == "":
            del lines[-1]
        for line in lines:
            if line.isspace() or not line:
                self.w_('\n')
            elif line.startswith("#"):
                self.w_("%s\n" % line)
            else:
                self.w_("%s%s\n" % (self.indent, line))

    def format(self, fmt, *args, **kwargs):
        """Write code from 'fmt' with the current indentation level added to
           the block as a whole.  If the code is indented to some
           level already, remove the code's indentation before
           indenting it.  Fill in variables in the string using
           'str.format', and the arguments from 'args' and 'kwargs'.
        """
        self.w(self.format_s(fmt, *args, **kwargs))

    def format_s(self, fmt, *args, **kwargs):
        """As format, but return a string rather writing to the file."""
        fmt = dedent_code(fmt)
        return fmt.format(*args, **kwargs)

    def pushIndent(self, n):
        """Increase the current indentation level by 'n' spaces"""
        self.indent += " " * n

    def popIndent(self, n):
        """Decrease the current indentation level by 'n' spaces"""
        self.indent = self.indent[:-n]

    def comment(self, string):
        """Write a comment containing 'string'."""
        self.w('/* %s */\n' % string)

    def eltHeader(self, element, skipLine=True):
        """Write a comment saying we're about to do something to a struct
           member named 'element'"""
        nl = ("\n" if skipLine else "")
        self.w('%s/* %s %s */\n' % (nl, self.action, element))

    def docstring(self, string):
        """Emit a docstring for a function, wrapped to a nice readable format.
        """
        string = re.sub(r'\s+', ' ', string)
        lines = textwrap.wrap(string,
                              initial_indent="/** ",
                              subsequent_indent=" * ")
        for line in lines:
            self.w_real(line + "\n")
        self.w_real(" */\n")


class DeclarationGenerationVisitor(CodeGenerator):

    """Code generating visitor: emit a structure declaration for all of the
       structure types in a file.

       See the docstring at the top of the file for a description of
       how we turn structure members into C.

    """

    def __init__(self, sort_order, f, inCFile=False):
        CodeGenerator.__init__(self, f.write)
        self.sort_order = sort_order
        self.inCFile = inCFile

    def visitFile(self, f):
        for n in f.externStructs:
            self.w("struct %s_st;\n" % n.name)
        self.isOpaque = ("opaque" in f.options) and not self.inCFile
        self.isVeryOpaque = ("very_opaque" in f.options) and not self.inCFile
        f.visitChildrenSorted(self.sort_order, self)

    def visitConstDecl(self, cd):
        if cd.annotation != None:
            self.w(cd.annotation)
        self.w("#define %s %s\n" % (cd.name, cd.value.value))

    def visitStructDecl(self, sd):
        if sd.annotation != None:
            self.w(sd.annotation)
        if self.isVeryOpaque:
            self.format("typedef struct {name}_st {name}_t;", name=sd.name)
            return
        if self.isOpaque:
            self.format("""
              #if defined(TRUNNEL_EXPOSE_{upname}_)
              struct {name}_st {{""", name=sd.name, upname=sd.name.upper())
        else:
            self.format("""
              #if !defined(TRUNNEL_OPAQUE) && !defined(TRUNNEL_OPAQUE_{upname})
              struct {name}_st {{""", name=sd.name, upname=sd.name.upper())
        self.pushIndent(2)
        sd.visitChildren(self)
        self.popIndent(2)
        self.format("""
              uint8_t trunnel_error_code_;
            }};
            #endif""")
        if not self.inCFile:
            self.format("""typedef struct {name}_st {name}_t;""", name=sd.name)

    def visitSMInteger(self, smi):
        if smi.annotation != None:
            self.w(smi.annotation)
        self.w("uint%d_t %s;\n" % (smi.inttype.width, smi.c_name))

    def visitSMStruct(self, sms):
        if sms.annotation != None:
            self.w(sms.annotation)

        self.w("struct %s_st *%s;\n" % (sms.structname, sms.c_name))

    def visitSMFixedArray(self, sfa):
        if sfa.annotation != None:
            self.w(sfa.annotation)
        fields = {'base': sfa.basetype, 'c_name': sfa.c_name, 'w': sfa.width}
        if type(sfa.basetype) == str:
            self.format("struct {base}_st *{c_name}[{w}];", **fields)
        elif str(sfa.basetype) == "char":
            self.format("char {c_name}[{w}+1];", **fields)
        else:
            self.format("uint{base.width}_t {c_name}[{w}];", **fields)

    def visitSMVarArray(self, sva):
        if sva.annotation != None:
            self.w(sva.annotation)

        fields = {'base': sva.basetype, 'c_name': sva.c_name}
        if str(sva.basetype) == "char":
            self.format("trunnel_string_t {c_name};", **fields)
        elif type(sva.basetype) == str:
            self.format(
                "TRUNNEL_DYNARRAY_HEAD(, struct {base}_st *) {c_name};",
                        **fields)
        else:
            self.format(
                "TRUNNEL_DYNARRAY_HEAD(, uint{base.width}_t) {c_name};",
                        **fields)

    def visitSMString(self, ss):
        if ss.annotation != None:
            self.w(ss.annotation)

        self.w("char *%s;\n" % (ss.c_name))

    def visitSMPosition(self, smp):
        if smp.annotation != None:
            self.w(smp.annotation)
        self.w("const uint8_t *%s;\n" % smp.c_name)

    def visitSMLenConstrained(self, sml):
        sml.visitChildren(self)

    def visitSMUnion(self, smu):
        if smu.annotation != None:
            self.w(smu.annotation)

        smu.visitChildren(self)

    def visitUnionMember(self, um):
        um.visitChildren(self)

    def visitSMFail(self, fail):
        pass

    def visitSMEos(self, eos):
        pass

    def visitSMIgnore(self, ignore):
        pass


class PrototypeGenerationVisitor(CodeGenerator):

    """Code-generating visitor that generates prototypes and documentation
       for the code manipulation functions that are generated in the header
       files.

       See docstring at the top of this file for a description of the
       various functions we generate.
    """

    def __init__(self, sort_order, f, docstrings=True):
        CodeGenerator.__init__(self, f.write)
        self.sort_order = sort_order
        if not docstrings:
            self.docstring = lambda *a: None

    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)

    def visitConstDecl(self, cd):
        pass

    def visitStructDecl(self, sd):
        name = sd.name
        self.docstring("""Return a newly allocated %s with all elements set
                          to zero.""" % name)
        self.w("%s_t *%s_new(void);\n" % (name, name))

        self.docstring("""Release all storage held by the %s in 'victim'.
                          (Do nothing if 'victim' is NULL.)
                       """
                       % name)
        self.w("void %s_free(%s_t *victim);\n" % (name, name))

        if not sd.isContext():
            self.writeParseEncodePrototypes(sd)

        AccessorFnGenerator(self.w_, True).visit(sd)

    def writeParseEncodePrototypes(self, sd):
        name = sd.name
        contextFormals = formatContexts(sd.contextList, declaration=True)
        self.docstring("""Try to parse a %s from the buffer in 'input',
                          using up to 'len_in' bytes from the input buffer.
                          On success, return the number of bytes consumed and
                          set *output to the newly allocated %s_t. On failure,
                          return -2 if the input appears truncated, and -1
                          if the input is otherwise invalid.
                       """ % (name, name))
        self.w(
            "ssize_t %s_parse(%s_t **output, const uint8_t *input, const size_t len_in%s);\n" %
               (name, name, contextFormals))

        self.docstring("""Return the number of bytes we expect to need to
                          encode the %s in 'obj'.  On
                          failure, return a negative value.  Note that
                          this value may be an overestimate, and can
                          even be an underestimate for certain
                          unencodeable objects.
                       """ % (name))
        self.w(
            "ssize_t %s_encoded_len(const %s_t *obj%s);\n" %
               (name, name, contextFormals))

        self.docstring("""Try to encode the %s from 'input' into the buffer
                          at 'output', using up to 'avail' bytes of the
                          output buffer. On success, return the number of
                          bytes used. On failure, return -2 if the buffer
                          was not long enough, and -1 if the input was
                          invalid.""" % (name))
        self.w(
            "ssize_t %s_encode(uint8_t *output, size_t avail, const %s_t *input%s);\n" %
               (name, name, contextFormals))

        self.docstring("""Check whether the internal state of the %s in
                          'obj' is consistent. Return NULL if it is, and a
                          short message if it is not.""" % name)
        self.w("const char *%s_check(const %s_t *obj%s);\n" %
               (name, name, contextFormals))

        self.docstring("""Clear any errors that were set on the object 'obj'
                          by its setter functions.  Return true iff errors
                          were cleared.""")
        self.w("int %s_clear_errors(%s_t *obj);\n" % (name, name))


def formatContexts(contexts, declaration=True):
    """Given a list of context type names, generate a list of declarations
       for them as formal parameters (if 'declaration' is true), or
       as arguments to a function (if 'declaration' is false).
    """
    if declaration:
        s = "".join(", const {0}_t *{0}_ctx".format(c) for c in contexts)
    else:
        s = "".join(", {0}_ctx".format(c) for c in contexts)
    return s


def field(name):
    """Return a string for accessing the field called 'name'.  This can
       be either a field in a context, or a field in the target object. """
    if '.' in name:
        return name.replace(".", "_ctx->")
    else:
        return "obj->" + name


def formatContextChecks(cg, contextList, onFail):
    """Using the code generator 'cg', emit code to call 'onFail' if
       any of the context objects in 'contextList' fails a check call."""
    for context in contextList:
        cg.format("""
             if ({0}_ctx == NULL)
               {1}
             """, context, onFail)


class CodeGenerationVisitor(CodeGenerator):

    """Code-generating visitor to produce all the code for a file.

       Iterates over all the structures in a file in a provided
       topologically sorted order, and then generates the functions
       for each.
    """

    def __init__(self, sort_order, f):
        CodeGenerator.__init__(self, f.write)
        self.f = f
        self.sort_order = sort_order
        self.generators = [NewFnGenerator, FreeFnGenerator,
                           AccessorFnGenerator, CheckFnGenerator,
                           EncodedLenFnGenerator,
                           EncodeFnGenerator, ParseFnGenerator]

    def visitFile(self, f):
        for es in f.externStructs:
            n = es.name
            fakeStruct = trunnel.Grammar.StructDecl(n, es.contextList)
            self.w("typedef struct %s_st %s_t;" % (n, n))
            PrototypeGenerationVisitor(
                self.sort_order, self.f, docstrings=False).visit(fakeStruct)
        f.visitChildrenSorted(self.sort_order, self)

    def visitConstDecl(self, cd):
        pass

    def visitStructDecl(self, sd):
        # We invoke these sub-visitors for each structure independently, so
        # that all the methdos for a structure are produced together.
        for g in self.generators:
            g(self.w).visit(sd)


class NewFnGenerator(CodeGenerator):

    """Code-generating visitor to construct the 'typename_new' function
       for a structure.

       The generated function just constructs a new value, with all of
       its fields initialized to 0.  (This sets dynamic arrays to be
       empty, and we require that this sets pointers to NULL.)
    """

    def __init__(self, writefn):
        CodeGenerator.__init__(self, writefn)

    def visitStructDecl(self, sd):
        name = sd.name
        self.format("""
           {0}_t *
           {0}_new(void)
           {{
             {0}_t *val = trunnel_calloc(1, sizeof({0}_t));
             if (NULL == val)
               return NULL;""", name)
        self.pushIndent(2)
        sd.visitChildren(self)
        self.popIndent(2)
        self.w("  return val;")
        self.w("}\n\n")

    def visit_other(self, arg):
        pass

    def visitSMInteger(self, smi):
        minval = smi.minimum()
        if minval != 0:
            self.w("val->%s = %s;\n" % (smi.c_name, minval))


class FreeFnGenerator(CodeGenerator):

    """Code-generating visitor to construct the 'typename_clear' and
       'typename_free' functions for a structure.

       The 'typename_clear' function iterates over every member of the
       structure, including possibly unused union fields, and releases
       all the storage held by them.  It does most of the work.

       The 'typename_free' function handles NULL, invokes typename_clear,
       and then frees the space held by the object itself.
    """

    def __init__(self, writefn):
        CodeGenerator.__init__(self, writefn)

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.docstring("""Release all storage held inside 'obj',
                          but do not free 'obj'.""")
        self.format("""
             static void
             {0}_clear({0}_t *obj)
             {{
               (void) obj;""", name)
        self.pushIndent(2)
        sd.visitChildren(self)
        self.popIndent(2)
        self.format("""
             }}

             void
             {0}_free({0}_t *obj)
             {{
               if (obj == NULL)
                 return;
               {0}_clear(obj);
               trunnel_memwipe(obj, sizeof({0}_t));
               trunnel_free_(obj);
             }}\n\n\n""", name)

    def visitSMInteger(self, smi):
        # We don't need to do anything to clear an integer.
        pass

    def visitSMFixedArray(self, sfa):
        # To clear a fixed array of structures, we must free every element
        # of the array.
        if type(sfa.basetype) == str:
            body = "%s_free(obj->%s[idx]);\n" % (sfa.basetype, sfa.c_name)
            iterateOverFixedArray(self, sfa, body)

    def visitSMStruct(self, sms):
        # To clear a structure in a structure, we invoke the clear
        # function for that structure recursively.
        self.format("{0.structname}_free(obj->{0.c_name});\n"
                    "obj->{0.c_name} = NULL;\n", sms)

    def visitSMVarArray(self, sva):
        # To free a variable-length array, if it is an array of structures,
        # we must call typename_free() on every element of the array.
        #
        # Then, we call TRUNNEL_DYNARRAY_CLEAR on the array.

        if type(sva.basetype) == str:
            body = "%s_free(TRUNNEL_DYNARRAY_GET(&obj->%s, idx));\n" % (
                sva.basetype, sva.c_name)
            iterateOverVarArray(self, sva, body)

        self.w("TRUNNEL_DYNARRAY_WIPE(&obj->%s);\n" % (sva.c_name))
        self.w("TRUNNEL_DYNARRAY_CLEAR(&obj->%s);\n" % (sva.c_name))

    def visitSMString(self, ss):
        # To clear a string, we call trunnel_free() on it.  (We require that
        # trunnel_free must handle NULL.)
        self.w("trunnel_wipestr(obj->%s);\n" % (ss.c_name))
        self.w("trunnel_free(obj->%s);\n" % (ss.c_name))

    def visitSMPosition(self, smp):
        pass

    def visitSMLenConstrained(self, sml):
        sml.visitChildren(self)

    def visitSMUnion(self, smu):
        smu.visitChildren(self)

    def visitUnionMember(self, um):
        um.visitChildren(self)

    def visitSMEos(self, eos):
        pass

    def visitSMFail(self, fail):
        pass

    def visitSMIgnore(self, ignore):
        pass


class AccessorFnGenerator(CodeGenerator):

    """Code-generating visitor that generates the accessors for structure
       members.  See function documentation for a description of every
       function we generate.

       As a general note: all "set" functions that change the value or
       properties of a field can return 0 for success or -1 on failure.
       When they return -1, they also set an error code on the structure,
       so that future encode attempts will fail unless you call an
       appropriate 'clear_errors' function.  This design lets careful
       users check that set functions are successful, while preventing
       careless users from getting into too much trouble.

       General principles: It should never be necessary to look at or
       modify a structure directly.  It should be quite hard to shoot
       yourself in the foot.
    """

    def __init__(self, writefn, prototypes_only=False):
        CodeGenerator.__init__(self, writefn)
        self.prototypes_only = prototypes_only
        if self.prototypes_only:
            self.w = lambda *args: None
        else:
            self.docstring = lambda *args: None

    def declaration(self, rv, decl):
        if self.prototypes_only:
            self.w_real('%s %s;\n' % (rv, decl))
        else:
            self.w_real('%s\n%s\n' % (rv, decl))

    def visitStructDecl(self, sd):
        self.structName = sd.name
        sd.visitChildren(self)

    def visit_other(self, ast):
        pass

    def visitSMInteger(self, smi):
        """For an integer field 'FIELD' in a structure called 'TYPE', we
           generate a pair of functions:
                 TYPE_get_FIELD(x)
                 TYPE_set_FIELD(x, v)
           The 'get' function returns the current value of the field in a
           provided strutrure.  The 'set' function changes the value, after
           checking that all specified constraints on the field are met.
        """
        st = self.structName
        nm = smi.c_fn_name
        tp = "uint%d_t" % smi.inttype.width

        self.docstring(
            "Return the value of the %s field of the %s_t in 'inp'" % (nm, st))
        self.declaration(tp, "%s_get_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return inp->%s;\n"
               "}\n" % smi.c_name)

        self.docstring("Set the value of the %s field of the %s_t in 'inp' to "
                       "'val'.  Return 0 on success; return -1 and set the "
                       "error code on 'inp' on failure." % (nm, st))
        self.declaration(
            "int", "%s_set_%s(%s_t *inp, %s val)" % (st, nm, st, tp))
        self.w("{\n")
        self.pushIndent(2)
        if smi.constraints is not None:
            expr = intConstraintExpression(
                "val", smi.constraints.ranges, smi.inttype.width)
            self.w("if (! (%s)) {\n"
                   "   TRUNNEL_SET_ERROR_CODE(inp);\n"
                   "   return -1;\n"
                   "}\n" % expr)

        self.w("inp->%s = val;\n" % smi.c_name)
        self.w("return 0;")
        self.popIndent(2)
        self.w("}\n")

    def visitSMStruct(self, sms):
        """For a struct field 'FIELD' in a structure called 'TYPE', we
           generate these functions:
                 TYPE_get_FIELD(x)
                 TYPE_getconst_FIELD(x)
                 TYPE_set_FIELD(x, v)
                 TYPE_set0_FIELD(x, v)
           The 'get' function returns the current value of the field in a
           provided strutrure.  The 'set0' function changes the value.
           The 'set' function changes the value, after freeing the prvious
           value (if any).
        """
        st = self.structName
        nm = sms.c_fn_name
        tp = "struct %s_st *" % sms.structname

        self.docstring(
            "Return the value of the %s field of the %s_t in 'inp'" % (nm, st))
        self.declaration(tp, "%s_get_%s(%s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return inp->%s;\n"
               "}\n" % sms.c_name)
        self.docstring("As %s_get_%s, but take and return a const pointer"
                       %(st,nm))
        self.declaration("const %s"%tp,
                         "%s_getconst_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return %s_get_%s((%s_t*) inp);\n"
               "}\n" %(st, nm, st))

        self.docstring("Set the value of the %s field of the %s_t in 'inp' to "
                       "'val'.  Free the old value if any.  Steals the reference"
                       "to 'val'."
                       "Return 0 on success; return -1 and set the "
                       "error code on 'inp' on failure." % (nm, st))
        self.declaration(
            "int", "%s_set_%s(%s_t *inp, %sval)" % (st, nm, st, tp))
        self.format("""
             {{
               if (inp->{c_name} && inp->{c_name} != val)
                 {structname}_free(inp->{c_name});
               return {st}_set0_{nm}(inp, val);
             }}""", c_name=sms.c_name, structname=sms.structname, st=st, nm=nm)

        self.docstring("As %s_set_%s, but does not free the previous value."
                       % (st, nm))
        self.declaration(
            "int", "%s_set0_%s(%s_t *inp, %sval)" % (st, nm, st, tp))

        self.format("""
             {{
               inp->{c_name} = val;
               return 0;
             }}""", c_name=sms.c_name)

    def visitSMFixedArray(self, sfa):
        """For a fixed-length array field 'FIELD' in a structure called
           'TYPE', we generate these functions:
                 TYPE_get_FIELD(x, index)
                 TYPE_getconst_FIELD(x, index)
                 TYPE_getlen_FIELD(x)
                 TYPE_getarray_FIELD(x)
                 TYPE_getconstarray_FIELD(x)
                 TYPE_set_FIELD(x, index, v)
                 TYPE_set0_FIELD(x, index, v)

           The 'get' function returns the current value of the field
           in a provided strutrure at the index 'idx'.  The 'getlen'
           function returns the (constant) number of elements for the
           array, by analogy with the getlen function for
           variable-length arrays.  The 'getarray' function returns
           a pointer to the array itself.

           The 'set0' function changes the value at a given index.
           The 'set' function changes the value at a given index,
           after freeing the previous value (if any).

        """
        st = self.structName
        nm = sfa.c_fn_name
        extraconst = ""
        if str(sfa.basetype) == 'char':
            elttype = 'char'
        elif type(sfa.basetype) == str:
            elttype = "struct %s_st *" % sfa.basetype
            extraconst = " const "
        else:
            elttype = "uint%d_t" % sfa.basetype.width

        self.docstring(

            """Return the (constant) length of the array holding the
                          %s field of the %s_t in 'inp'.""" % (nm, st))
        self.declaration(
            "size_t", "%s_getlen_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  (void)inp;"
               "  return %s;\n"
               "}\n\n" % sfa.width)

        self.docstring("""Return the element at position 'idx' of the
                          fixed array field %s of the %s_t in 'inp'.""" %
                       (nm, st))
        self.declaration(elttype, '%s_get_%s(%s_t *inp, size_t idx)'
                         % (st, nm, st))
        self.w("{\n"
               "  trunnel_assert(idx < %s);\n"
               "  return inp->%s[idx];\n"
               "}\n\n" % (sfa.width, sfa.c_name))

        self.docstring("As %s_get_%s, but take and return a const pointer"
                       %(st,nm))
        self.declaration(extraconst+elttype,
                         "%s_getconst_%s(const %s_t *inp, size_t idx)" % (st, nm, st))
        self.w("{\n"
               "  return %s_get_%s((%s_t*)inp, idx);\n"
               "}\n" %(st, nm, st))

        freestr = ""
        if type(sfa.basetype) == str:
            freestr = "  Free the previous value, if any."
        self.docstring("""Change the element at position 'idx' of the
                          fixed array field %s of the %s_t in 'inp', so
                          that it will hold the value 'elt'.%s""" %
                       (nm, st, freestr))
        self.declaration("int", "%s_set_%s(%s_t *inp, size_t idx, %s elt)"
                         % (st, nm, st, elttype))
        self.w("{\n"
               "  trunnel_assert(idx < %s);\n" % sfa.width)

        if type(sfa.basetype) == str:
            self.format("""
                if (inp->{c_name}[idx] && inp->{c_name}[idx] != elt)
                  {basetype}_free(inp->{c_name}[idx]);
                return {st}_set0_{nm}(inp, idx, elt);
              }}""", c_name=sfa.c_name, basetype=sfa.basetype, st=st, nm=nm)

            self.docstring("As %s_set_%s, but does not free the previous value."
                           % (st, nm))
            self.declaration("int", "%s_set0_%s(%s_t *inp, size_t idx, %s elt)"
                             % (st, nm, st, elttype))
            self.w("{\n"
                   "  trunnel_assert(idx < %s);\n" % sfa.width)

        self.w(("  inp->%s[idx] = elt;\n"
                "  return 0;\n"
                "}\n\n") % (sfa.c_name))

        self.docstring("""Return a pointer to the %s-element array field %s of
                          'inp'.""" % (sfa.width, nm))
        self.declaration("%s *" % elttype,
                         "%s_getarray_%s(%s_t *inp)" % (st, nm, st))
        self.w(("{\n"
                "  return inp->%s;\n"
                "}\n") % (sfa.c_name))

        self.docstring("As %s_get_%s, but take and return a const pointer"
                       %(st,nm))
        self.declaration("const %s %s *"%(elttype,extraconst),
                         "%s_getconstarray_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return (const %s %s *)%s_getarray_%s((%s_t*)inp);\n"
               "}\n" %(elttype, extraconst, st, nm, st))

    def visitSMLenConstrained(self, sml):
        sml.visitChildren(self)

    def visitSMUnion(self, smu):
        # XXXX accessors for items that check about the tag?
        smu.visitChildren(self)

    def visitUnionMember(self, um):
        um.visitChildren(self)

    def w_no_indent(self, s):
        if not self.prototypes_only:
            self.w_(s)

    def visitSMVarArray(self, sva):
        """For a variable-length array field 'FIELD' in a structure called
           'TYPE', we generate these functions:
                 TYPE_get_FIELD(x, index)
                 TYPE_getconst_FIELD(x, index)
                 TYPE_getlen_FIELD(x)
                 TYPE_getarray_FIELD(x)
                 TYPE_getconstarray_FIELD(x)
                 TYPE_set_FIELD(x, index, v)
                 TYPE_set0_FIELD(x, index, v)

                 TYPE_add_FIELD(x, v)
                 TYPE_setlen_FIELD(x, newlen)

           The 'get', getlen, getarray, set0, and set functions are as for
           fixed-length arrays.

           The 'add' function adds a new element to the end of the
           array, expanding it as necessary.  The 'setlen' function
           expands and 0-pads the array, or contracts the array and
           frees dead elements as needed.

           Additionally, if the array is an array of char, the funtions
           described in writeVarArrayCharAccessors are generated.
        """

        st = self.structName
        nm = sva.c_fn_name
        extraconst = ""
        if type(sva.basetype) == str:
            elttype = "struct %s_st *" % sva.basetype
            extraconst = " const "
        elif str(sva.basetype) == 'char':
            elttype = 'char'
        else:
            elttype = "uint%d_t" % sva.basetype.width

        maxlen = if_overflow_possible = endif_overflow_possible = None
        if sva.widthfield is not None and sva.widthfieldmember is not None:
            maxlen = "UINT%s_MAX" % sva.widthfieldmember.inttype.width
            if_overflow_possible = "#if %s < SIZE_MAX\n" % maxlen
            endif_overflow_possible = "#endif"

        self.docstring("""Return the length of the dynamic array holding the
                          %s field of the %s_t in 'inp'.""" % (nm, st))
        self.declaration(
            "size_t", "%s_getlen_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return TRUNNEL_DYNARRAY_LEN(&inp->%s);\n"
               "}\n\n" % nm)

        self.docstring("""Return the element at position 'idx' of the
                          dynamic array field %s of the %s_t in 'inp'.""" %
                       (nm, st))
        self.declaration(elttype, '%s_get_%s(%s_t *inp, size_t idx)'
                         % (st, nm, st))
        self.w("{\n"
               "  return TRUNNEL_DYNARRAY_GET(&inp->%s, idx);\n"
               "}\n\n" % nm)

        self.docstring("As %s_get_%s, but take and return a const pointer"
                       %(st,nm))
        self.declaration(extraconst+elttype,
                         "%s_getconst_%s(const %s_t *inp, size_t idx)" % (st, nm, st))
        self.w("{\n"
               "  return %s_get_%s((%s_t*)inp, idx);\n"
               "}\n" %(st, nm, st))

        freestr = ""
        if type(sva.basetype) == str:
            freestr = "  Free the previous value, if any."
        self.docstring("""Change the element at position 'idx' of the
                          dynamic array field %s of the %s_t in 'inp', so
                          that it will hold the value 'elt'.%s""" %
                       (nm, st, freestr))
        self.declaration("int", "%s_set_%s(%s_t *inp, size_t idx, %s elt)"
                         % (st, nm, st, elttype))
        self.w("{\n")
        if type(sva.basetype) == str:
            self.format("""
               {basetype}_t *oldval = TRUNNEL_DYNARRAY_GET(&inp->{c_name}, idx);
               if (oldval && oldval != elt)
                 {basetype}_free(oldval);
               return {st}_set0_{nm}(inp, idx, elt);
             }}""", basetype=sva.basetype, c_name=sva.c_name, st=st, nm=nm)

            self.docstring("As %s_set_%s, but does not free the previous value."
                           % (st, nm))
            self.declaration("int", "%s_set0_%s(%s_t *inp, size_t idx, %s elt)"
                             % (st, nm, st, elttype))
            self.w("{\n")

        self.w("  TRUNNEL_DYNARRAY_SET(&inp->%s, idx, elt);\n" % nm)
        self.w("  return 0;\n")
        self.w("}\n")

        self.docstring("""Append a new element 'elt' to the dynamic array
                          field %s of the %s_t in 'inp'.""" %
                       (nm, st))
        self.declaration("int", "%s_add_%s(%s_t *inp, %s elt)"
                         % (st, nm, st, elttype))
        self.w("{\n")

        if maxlen is not None:
            self.format("""
               #if SIZE_MAX >= {maxlen}
                 if (inp->{c_name}.n_ == {maxlen})
                   goto trunnel_alloc_failed;
               #endif""",
                        c_name=sva.c_name, maxlen=maxlen)

        self.w("  TRUNNEL_DYNARRAY_ADD(%s, &inp->%s, elt, {});\n"
               "  return 0;\n"
               " trunnel_alloc_failed:\n"
               "  TRUNNEL_SET_ERROR_CODE(inp);\n"
               "  return -1;\n"
               "}\n\n" % (elttype, nm))

        self.docstring("""Return a pointer to the variable-length
                          array field %s of 'inp'.""" % nm)
        self.declaration("%s *" % elttype,
                         "%s_getarray_%s(%s_t *inp)" % (st, nm, st))
        self.w(("{\n"
                "  return inp->%s.elts_;\n"
                "}\n") % (sva.c_name))
        self.docstring("As %s_get_%s, but take and return a const pointer"
                       %(st,nm))
        self.declaration("const %s %s *"%(elttype,extraconst),
                         "%s_getconstarray_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return (const %s %s *)%s_getarray_%s((%s_t*)inp);\n"
               "}\n" %(elttype, extraconst, st, nm, st))

        if type(sva.basetype) == str:
            fill = "Fill extra elements with NULL; free removed elements."
        else:
            fill = "Fill extra elements with 0."

        self.docstring("""Change the length of the variable-length
                          array field %s of 'inp' to 'newlen'.%s
                          Return 0 on
                          success; return -1 and set the error code
                          on 'inp' on failure.""" % (nm, fill))
        self.declaration("int",
                         "%s_setlen_%s(%s_t *inp, size_t newlen)" % (st, nm, st))
        self.w("{\n")
        self.pushIndent(2)
        if str(sva.basetype) != 'char':
            self.w("%s *newptr;\n" % elttype)
        needFailed = False
        if maxlen is not None:
            needFailed = True
            self.w_no_indent(if_overflow_possible)
            self.w("if (newlen > %s)\n"
                   "  goto trunnel_alloc_failed;\n" % maxlen)
            self.w_no_indent(endif_overflow_possible)

        if str(sva.basetype) == 'char':
            self.w('return trunnel_string_setlen(&inp->%s, newlen,\n'
                   '          &inp->trunnel_error_code_);\n' % sva.c_name)
        else:
            needFailed = True
            if type(sva.basetype) == str:
                freefn = "(trunnel_free_fn_t) %s_free" % sva.basetype
            else:
                freefn = "(trunnel_free_fn_t) NULL"

            self.format("""
                newptr = trunnel_dynarray_setlen(&inp->{c_name}.allocated_,
                               &inp->{c_name}.n_, inp->{c_name}.elts_, newlen,
                               sizeof(inp->{c_name}.elts_[0]), {freefn},
                               &inp->trunnel_error_code_);
                if (newlen != 0 && newptr == NULL)
                  goto trunnel_alloc_failed;
                inp->{c_name}.elts_ = newptr;
                return 0;""", c_name=sva.c_name, freefn=freefn)

        self.popIndent(2)
        if needFailed:
            self.w(" trunnel_alloc_failed:\n")
            self.w("  TRUNNEL_SET_ERROR_CODE(inp);\n")
            self.w("  return -1;\n")
        self.w("}\n")

        if str(sva.basetype) == 'char':
            self.writeVarArrayCharAccessors(sva, maxlen, if_overflow_possible)

    def writeVarArrayCharAccessors(self, sva, maxlen, if_overflow_possible):
        """For a variable-length array field 'FIELD' of char in a structure
           called 'TYPE', we generate these functions:
               TYPE_getstr_FIELD(x)
               TYPE_setstr0_FIELD(x, val, len)
               TYPE_setstr_FIELD(x, val)

           The 'getstr' function returns the value as a NUL-terminated string,
           and returns NULL on allocation failure.  The 'setstr0' function
           replaces the current value with a copy of the len-byte string in
           val.  And the 'setstr' function behaves as setstr0, but uses
           strlen() to find the length of the string.
        """
        st = self.structName
        nm = sva.c_fn_name
        if if_overflow_possible != None:
            endif_overflow_possible = "#endif"

        self.docstring("""Return the value of the %s field of a %s_t as
                          a NUL-terminated string.""" % (nm, st))
        self.declaration("const char *",
                         "%s_getstr_%s(%s_t *inp)" % (st, nm, st))
        self.w(("{\n"
                "  return trunnel_string_getstr(&inp->%s);\n"
                "}\n" % nm))

        self.docstring("""Set the value of the %s field of a %s_t to
                          a given string of length  'len'. Return 0 on
                          success; return -1 and set the error code
                          on 'inp' on failure.""" % (nm, st))
        self.declaration("int",
                         "%s_setstr0_%s(%s_t *inp, const char *val, size_t len)" % (st, nm, st))
        self.w("{\n")
        if maxlen is not None:
            self.w_no_indent(if_overflow_possible)
            self.w("  if (len > %s) {\n"
                   "    TRUNNEL_SET_ERROR_CODE(inp);\n"
                   "    return -1;\n"
                   "  }\n" % maxlen)
            self.w_no_indent(endif_overflow_possible)
        self.w(("  return trunnel_string_setstr0(&inp->%s, val, len, &inp->trunnel_error_code_);\n"
                "}\n") % nm)

        self.docstring("""Set the value of the %s field of a %s_t to
                          a given NUL-terminated string. Return 0 on
                          success; return -1 and set the error code
                          on 'inp' on failure.""" % (nm, st))
        self.declaration("int",
                         "%s_setstr_%s(%s_t *inp, const char *val)" % (st, nm, st))
        self.w(("{\n"
                "  return %s_setstr0_%s(inp, val, strlen(val));\n"
                "}\n") % (st, nm))

    def visitSMString(self, sms):
        """For a nul-terminated string field 'FIELD' of char in a structure
           called 'TYPE', we generate these functions:
               TYPE_get_FIELD(x)
               TYPE_set_FIELD(x, val)

           The 'get' function returns the value as a NUL-terminated string.
           The 'set' function replaces the current value with a copy of the
           string in 'val'.
        """
        st = self.structName
        nm = sms.c_fn_name

        self.docstring(
            "Return the value of the %s field of the %s_t in 'inp'" % (nm, st))
        self.declaration("const char *", "%s_get_%s(const %s_t *inp)" % (st, nm, st))
        self.w("{\n"
               "  return inp->%s;\n"
               "}\n" % sms.c_name)

        self.docstring("Set the value of the %s field of the %s_t in 'inp' to "
                       "'val'.  Free the old value if any. Does not steal "
                       " the reference to 'val'."
                       "Return 0 on success; return -1 and set the "
                       "error code on 'inp' on failure." % (nm, st))
        self.declaration(
            "int", "%s_set_%s(%s_t *inp, const char *val)" % (st, nm, st))
        self.format("""
             {{
               trunnel_free(inp->{c_name});
               if (NULL == (inp->{c_name} = trunnel_strdup(val))) {{
                 TRUNNEL_SET_ERROR_CODE(inp);
                 return -1;
               }}
               return 0;
             }}""", c_name=sms.c_name)

    def visitSMPosition(self, smp):
        st = self.structName
        nm = smp.c_fn_name
        self.docstring("Return the position for %s when we parsed "
                       "this object"%nm)
        self.declaration("const uint8_t *",
                         "%s_get_%s(const %s_t *inp)" % (st,nm,st))
        self.format("""
              {{
                return inp->{nm};
              }}""", nm = smp.c_name)

def iterateOverFixedArray(generator, sfa, body, extraDecl=""):
    """Helper: write the code needed to iterate over every element of a
       fixed array (whose SMFixedArray is sfa), invoking the code 'body'
       on each element.  Within the code in 'body', the string {ELEMENT}
       will be replaced by the current element of the array.  To declare
       extra temporary variables, set extraDecl.

       The code is generated using the CodeGenerator in 'generator'.
    """
    element = "obj->%s[idx]" % sfa.c_name
    generator.format("""
           {{
             {extraDecl}
             unsigned idx;
             for (idx = 0; idx < {width}; ++idx) {{""",
                     width=sfa.width, extraDecl=extraDecl)
    generator.pushIndent(4)
    generator.format(body, ELEMENT=element)
    generator.popIndent(4)
    generator.format("""
             }}
           }}""")


def iterateOverVarArray(generator, sva, body, extraDecl=""):
    """Helper: write the code needed to iterate over every element of a
       variable-length array (whose SMVarArray is sva), invoking the
       code 'body' on each element.  Within the code in 'body', the
       string {ELEMENT} will be replaced by the current element of the
       array.  To declare extra temporary variables, set extraDecl.

       The code is generated using the CodeGenerator in 'generator'.
    """
    element = "TRUNNEL_DYNARRAY_GET(&obj->%s, idx)" % sva.c_name

    generator.format("""
           {{
             {extraDecl}
             unsigned idx;
             for (idx = 0; idx < TRUNNEL_DYNARRAY_LEN(&obj->{c_name}); ++idx) {{
           """, c_name=sva.c_name, extraDecl=extraDecl)
    generator.pushIndent(4)
    generator.format(body, ELEMENT=element)
    generator.popIndent(4)
    generator.format("""
             }}
           }}""")


class CheckFnGenerator(CodeGenerator):

    """Code-generating visitor to generate the 'typename_check' function
       for a given structure.

       The 'check' function is implemented by visiting every member of
       the structure, in declared order, and checking whether it meets
       every requirement on it.  If a member is invalid, we return a
       string explaining what's wrong with it.  If every member is okay,
       we return NULL at the end of the function.
    """

    def __init__(self, writefn):
        CodeGenerator.__init__(self, writefn)

    def visitStructDecl(self, sd):
        if sd.isContext():
            return
        contextFormals = formatContexts(sd.contextList, declaration=True)
        # To check a whole structure: check that the structure pointer
        # isn't NULL, then check the contents.
        self.structName = name = sd.name
        self.w("const char *\n%s_check(const %s_t *obj%s)\n{\n" % (
            name, name, contextFormals))
        self.pushIndent(2)
        self.w('if (obj == NULL)\n'
               '  return "Object was NULL";\n'
               'if (obj->trunnel_error_code_)\n'
               '  return "A set function failed on this object";\n')
        formatContextChecks(self, sd.contextList, 'return "Context was NULL";')
        sd.visitChildren(self)
        self.w("return NULL;\n")
        self.popIndent(2)
        self.w("}\n\n")

    def visitSMInteger(self, smi):
        # To check an integer: if the integer has any constraints on it,
        # then see whether they apply.  Otherwise, the integer doesn't need
        # any checking.

        if smi.constraints is not None:
            v = "obj->%s" % smi.c_name
            expr = intConstraintExpression(
                v, smi.constraints.ranges, smi.inttype.width)

            self.w(('if (! %s)\n'
                    '  return "Integer out of bounds";\n') % (expr))

    def visitSMFixedArray(self, sfa):
        # To check a fixed array of char: make sure that it's NUL-terminated.
        #
        # To check a fixed array of struct: recursively invoke the check
        # function for each item in the array.

        if type(sfa.basetype) == str:
            args = formatContexts(
                sfa.structDeclaration.contextList, declaration=False)
            body = ("if (NULL != (msg = %s_check({ELEMENT}%s)))\n"
                    "  return msg;" % (sfa.basetype, args))
            iterateOverFixedArray(self, sfa, body,
                                  extraDecl='const char *msg;\n')

        elif str(sfa.basetype) == 'char':
            self.w('if (obj->%s[%s] != 0)\n'
                   '  return "String not terminated";\n'
                   % (sfa.c_name, sfa.width))

    def visitSMStruct(self, sms):
        contextArgs = formatContexts(
            sms.structDeclaration.contextList, declaration=False)
        # To check a nested struct: recursively invoke that struct's check
        # function.
        self.format("""
                 {{
                   const char *msg;
                   if (NULL != (msg = {structname}_check(obj->{c_name}{contextArgs})))
                     return msg;
                 }}""", structname=sms.structname, c_name=sms.c_name, contextArgs=contextArgs)

    def visitSMVarArray(self, sva):
        # To check any variable-lengt array with an explicit
        # width field: make sure that the field matches the array's
        # actual length.
        #
        # Additionally, if it's an array of struct, recursively invoke
        # the check function for each of its members.

        if type(sva.basetype) == str:
            args = formatContexts(
                sva.structDeclaration.contextList, declaration=False)
            body = ("if (NULL != (msg = %s_check({ELEMENT}%s)))\n"
                    "  return msg;" % (sva.basetype, args))

            iterateOverVarArray(self, sva, body,
                                extraDecl='const char *msg;\n')

        if sva.widthfield is not None:
            if sva.widthfieldmember:
                wname = field(sva.widthfieldmember.c_name)
            else:
                wname = field(sva.widthfield)
            self.w(('if (TRUNNEL_DYNARRAY_LEN(&obj->%s) != %s)\n'
                    '  return "Length mismatch for %s";\n') % (
                        sva.c_name, wname, sva.name))

    def visitSMString(self, ss):
        # To check a nul-terminated string: make sure it isn't NULL.
        self.w('if (NULL == obj->%s)\n  return "Missing %s";\n' %
               (ss.c_name, ss.c_name))

    def visitSMPosition(self, smp):
        pass

    def visitSMLenConstrained(self, sml):
        # To check a SMlenConstrained, check its children.
        sml.visitChildren(self)

    def visitSMUnion(self, smu):
        # To check a union, look at the union's tag value, and handle all
        # the tag values separately.
        self.w('switch (%s) {\n' % field(smu.tagfield))
        smu.visitChildren(self)
        self.w("}\n")

    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w, um)
        self.pushIndent(2)
        um.visitChildren(self)
        self.popIndent(2)
        self.popIndent(2)
        self.w("    break;\n")

    def visitSMEos(self, eos):
        pass

    def visitSMIgnore(self, ignore):
        pass

    def visitSMFail(self, fail):
        self.pushIndent(2)
        self.w('return "Bad tag for union";\n')
        self.popIndent(2)


def writeUnionMemberCaseLabel(w, um):
    """Use the function 'w' to emit a case label for a given union member.
       If the union member has multiple case values, emit multiple case laels.
    """
    w("\n")
    if um.tagvalue == None:
        w("default:\n")
        return

    for lo, hi in um.tagvalue:
        if lo == hi:
            w("case %s:\n" % lo)
        else:
            for value in range(lo, hi + 1):
                w("case %s:\n" % value)


def arrayIsBytes(arry):
    """Return true if the array is an array of char or of uint8_t. Otherwise
       return false."""
    tp = arry.basetype
    if str(tp) == 'char':
        return True
    elif type(tp) == trunnel.Grammar.IntType and tp.width == 8:
        return True
    else:
        return False


class EncodedLenFnGenerator(CodeGenerator):

    def __init__(self, writefn):
        CodeGenerator.__init__(self, writefn)
        self.action = "Length of"

    def visitStructDecl(self, sd):
        if sd.isContext():
            return

        name = sd.name
        contextFormals = formatContexts(sd.contextList, declaration=True)
        contextArgs = formatContexts(sd.contextList, declaration=False)

        self.format("""
                       ssize_t
                       {name}_encoded_len(const {name}_t *obj{args})
                       {{
                         ssize_t result = 0;
                    """, name=name, args=contextFormals)
        self.pushIndent(2)
        self.w(('if (NULL != %s_check(obj%s))\n'
                '   return -1;\n\n') % (sd.name, contextArgs))
        sd.visitChildren(self)
        self.popIndent(2)
        self.format("""
                      return result;
                    }}""")

    def visitSMInteger(self, smi):
        self.eltHeader(smi)
        self.w("result += %s;\n" % (smi.inttype.width // 8))

    def visitSMStruct(self, sms):
        self.eltHeader(sms)
        contextList = sms.structDeclaration.contextList
        args = formatContexts(contextList, declaration=False)
        self.w("result += %s_encoded_len(obj->%s%s);\n" % (
            sms.structname, sms.c_name, args))

    def visitSMFixedArray(self, sfa):
        self.eltHeader(sfa)
        if arrayIsBytes(sfa):
            self.w("result += %s;\n" % sfa.width)
        elif type(sfa.basetype) != str:
            self.w("result += %s * %s;\n" % (
                   sfa.width, sfa.basetype.width // 8))
        else:
            contextList = sfa.structDeclaration.contextList
            args = formatContexts(contextList, declaration=False)
            body = "result += %s_encoded_len({ELEMENT}%s);" % (sfa.basetype,
                                                               args)
            iterateOverFixedArray(self, sfa, body)

    def visitSMVarArray(self, sva):
        self.eltHeader(sva)
        if arrayIsBytes(sva):
            self.w("result += TRUNNEL_DYNARRAY_LEN(&obj->%s);\n" % sva.c_name)
        elif type(sva.basetype) != str:
            self.w("result += %s * TRUNNEL_DYNARRAY_LEN(&obj->%s);\n" %
                   (sva.basetype.width // 8, sva.c_name))
        else:
            contextList = sva.structDeclaration.contextList
            args = formatContexts(contextList, declaration=False)
            body = "result += %s_encoded_len({ELEMENT}%s);" % (sva.basetype,
                                                               args)
            iterateOverVarArray(self, sva, body)

    def visitSMString(self, ss):
        self.eltHeader(ss)
        self.w("result += strlen(obj->%s) + 1;\n" % ss.c_name)

    def visitSMPosition(self, smp):
        pass

    def visitSMLenConstrained(self, sml):
        sml.visitChildren(self)

    def visitSMUnion(self, smu):
        self.w('switch (%s) {\n' % field(smu.tagfield))
        smu.visitChildren(self)
        self.w("}\n")

    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w, um)
        self.pushIndent(2)
        um.visitChildren(self)
        self.w("break;\n")
        self.popIndent(2)
        self.popIndent(2)

    def visitSMFail(self, smf):
        # This case should have gotten caught by the check function before
        # encoding; we shouldn't be able to reach here.
        self.w('trunnel_assert(0);\n')

    def visitSMIgnore(self, udi):
        pass

    def visitSMEos(self, eos):
        pass


class EncodeFnGenerator(CodeGenerator):

    """Code-generating visitor that generates the 'typename_encode()'
       function and 'typename_clear_errors()' function for a given structure.

       The function checks the provided object for correctness using
       typename_check(), then tries to encode each of its elements in
       order into a provided buffer of a given length.  It returns -2 if
       the buffer is too short, -1 on any other error, and returns the
       number of bytes written on success.

       The function works by maintaining a count of the number of
       bytes written so far in the local variable 'written', and a
       pointer to the next byte to write in the local variable 'ptr'.

       The generated function also uses these local variables:
         result -- to hold the temporary result of any encoding operation.
         msg -- to hold the result of a typename_check() call.
         backptr_member -- to hold a pointer to the location in the output
            where we encoded any field that represented the length of
            a length-constrained union.  (We use that to fill in the right
            value after encoding the union.)

       INVARIANTS:
            "output + written == ptr"
            "written <= avail"
    """
    #
    # curStruct -- the current StructDecl
    # structName -- the name of the current structure
    # needTruncated -- true iff we need to generate a 'truncated' label.

    def __init__(self, writefn):
        CodeGenerator.__init__(self, writefn)
        self.action = "Encode"

    def checkAvail_s(self, needed, member):
        self.needTruncated = True
        if member.after_leftover_field:
            return self.format_s("""
               trunnel_assert(written <= avail);
               if (avail - written < {0}) {{
                 if (avail_orig - written < {0})
                   goto truncated;
                 else
                   goto check_failed;
               }}
               """, needed)
        else:
            return self.format_s("""
                 trunnel_assert(written <= avail);
                 if (avail - written < {0})
                   goto truncated;
                 """, needed)

    def checkAvail(self, needed, member):
        self.w(self.checkAvail_s(needed, member))

    def visitStructDecl(self, sd):
        if sd.isContext():
            return

        self.structName = name = sd.name
        self.curStruct = sd

        self.w("int\n%s_clear_errors(%s_t *obj)\n" % (name, name))
        self.w("{\n"
               "  int r = obj->trunnel_error_code_;\n"
               "  obj->trunnel_error_code_ = 0;\n"
               "  return r;\n"
               "}")

        if sd.has_leftover_field:
            optconst = ""
        else:
            optconst = "const "

        contextFormals = formatContexts(sd.contextList, declaration=True)
        contextArgs = formatContexts(sd.contextList, declaration=False)

        self.w(
            "ssize_t\n%s_encode(uint8_t *output, %ssize_t avail, const %s_t *obj%s)\n{\n" % (name, optconst, name, contextFormals))
        self.pushIndent(2)
        self.w('ssize_t result = 0;\n'
               'size_t written = 0;\n'
               'uint8_t *ptr = output;\n'
               'const char *msg;\n')
        self.format("""
                #ifdef TRUNNEL_CHECK_ENCODED_LEN
                const ssize_t encoded_len = {name}_encoded_len(obj{args});
                #endif
                """, name=sd.name, args=contextArgs)

        if sd.has_leftover_field:
            self.w('int enforce_avail = 0;\n'
                   'const size_t avail_orig = avail;\n')
        self.w('\n')
        if sd.lengthFields:
            for m in sorted(sd.lengthFields.values()):
                self.w('uint8_t *backptr_%s = NULL;\n' % (m.c_name))
            self.w('\n')
        self.w('if (NULL != (msg = %s_check(obj%s)))\n'
               '  goto check_failed;\n\n' % (sd.name, contextArgs))
        self.w_("#ifdef TRUNNEL_CHECK_ENCODED_LEN\n")
        self.w("trunnel_assert(encoded_len >= 0);\n")
        self.w_("#endif\n")
        self.needTruncated = False
        sd.visitChildren(self)

        self.w('\n'
               '\ntrunnel_assert(ptr == output + written);\n')

        if sd.has_leftover_field:
            self.w('if (enforce_avail && avail != written)\n'
                   '  goto check_failed;\n')

        self.w_("#ifdef TRUNNEL_CHECK_ENCODED_LEN")
        self.format("""
                 {{
                   trunnel_assert(encoded_len >= 0);
                   trunnel_assert((size_t)encoded_len == written);
                 }}
                    """, name=sd.name, args=contextArgs)
        self.w("#endif")

        self.w('\n'
               'return written;\n\n')

        self.popIndent(2)
        if self.needTruncated:
            self.w(" truncated:\n  result = -2;\n  goto fail;\n")
        self.w(" check_failed:\n"
               "  (void)msg;\n"
               "  result = -1;\n"
               "  goto fail;\n"
               " fail:\n"
               "  trunnel_assert(result < 0);\n"
               "  return result;\n")
        self.w("}\n\n")
        self.curStruct = None

    def visitSMInteger(self, smi):
        # To encode an integer field, we delegate to encodeInteger.
        #
        # If the field is the length of a union, we remember the
        # current position in the output buffer.
        self.eltHeader(smi)
        if smi.c_name in self.curStruct.lengthFields:
            self.w('backptr_%s = ptr;\n' % (smi.c_name))
        self.w(
            self.encodeInteger(smi, smi.inttype.width, "obj->%s" % (smi.c_name)))

    def encodeInteger(self, member, width, element, forFormat=False):
        # To encode an integer field, we make sure we have enough
        # room, then use the appropriate endian-conversion and
        # set_uintX functions to write it to the output.  Then we
        # advance the written and ptr values.
        nbytes = width // 8
        hton = HTON_FN[width]
        self.needTruncated = True
        avail = self.checkAvail_s(nbytes, member)
        if forFormat:
            avail = avail.replace("{", "{{").replace("}", "}}")
        return avail + self.format_s("""
            trunnel_set_uint{width}(ptr, {hton}({element}));
            written += {nbytes}; ptr += {nbytes};
            """, nbytes=nbytes, width=width, hton=hton, element=element)

    def visitSMStruct(self, sms):
        # To encode an structure field, we delegate to encodeStruct
        self.eltHeader(sms)
        self.w(self.encodeStruct(sms.structname, "obj->%s" % (sms.c_name),
                                 sms.structDeclaration.contextList))

    def encodeStruct(self, structtype, element_pointer, contextList):
        # To encode a struct, we delegate to that structure's typename_encode()
        # function, and check its output to see whether we succeeded.
        # On success, we advance the written and ptr values.
        args = formatContexts(contextList, declaration=False)
        return self.format_s("""
                trunnel_assert(written <= avail);
                result = {structtype}_encode(ptr, avail - written, {element}{args});
                if (result < 0)
                  goto fail; /* XXXXXXX !*/
                written += result; ptr += result;
                """, structtype=structtype, element=element_pointer, args=args)

    def visitSMFixedArray(self, sfa):
        # To encode a fixed array of char, we make sure we have enough
        # enough room in the output.  Then we copy the string into the
        # output, and zero-pad up to the length of the fixed array.
        # Then we advance the written and ptr variables.
        #
        # To encode a fixed array of uint8_t, we make sure we have
        # enough enough room in the output.  Then we copy the array
        # into the output, and zero-pad up to the length of the fixed
        # array. Then we advance the written and ptr variables.
        #
        # To encode a fixed array of anything else, we iterate over
        # the array with a for loop, and encode each member as
        # appropriate (see encodeInteger and encodeStruct.)

        self.eltHeader(sfa)
        if arrayIsBytes(sfa):
            self.needTruncated = True
            if str(sfa.basetype) == 'char':
                self.checkAvail(sfa.width, sfa)
                self.format("""
                        {{
                          size_t len = strlen(obj->{c_name});
                          trunnel_assert(len <= {width});
                          memcpy(ptr, obj->{c_name}, len);
                          memset(ptr + len, 0, {width} - len);
                          written += {width}; ptr += {width};
                        }}
                        """, c_name=sfa.c_name, width=sfa.width)
            else:
                self.checkAvail(sfa.width, sfa)
                self.format("""
                        memcpy(ptr, obj->{c_name}, {width});
                        written += {width}; ptr += {width};
                        """, c_name=sfa.c_name, width=sfa.width)
            return

        if type(sfa.basetype) == str:
            body = self.encodeStruct(sfa.basetype, "{ELEMENT}",
                                     sfa.structDeclaration.contextList)
        else:
            body = self.encodeInteger(sfa, sfa.basetype.width, "{ELEMENT}")
        iterateOverFixedArray(self, sfa, body)

    def visitSMVarArray(self, sva):
        # To encode a variable-length array of bytes, we double-check
        # consistency of the length value, ensure that we have enough
        # space, and then memcpy the array into the output buffer.
        # Then we advance the written and ptr variables.
        #
        # To encode a variable-length array of anything else, we
        # iterate over the array with a for loop, and encode each
        # member as appropriate (see encodeInteger and encodeStruct.)

        self.eltHeader(sva)
        if arrayIsBytes(sva):
            self.needTruncated = True
            self.format("""
                   {{
                     size_t elt_len = TRUNNEL_DYNARRAY_LEN(&obj->{c_name});
                   """, c_name=sva.c_name)
            if sva.widthfield is not None:
                if sva.widthfieldmember is not None:
                    wname = field(sva.widthfieldmember.c_name)
                else:
                    wname = field(sva.widthfield)
                self.w('  trunnel_assert(%s == elt_len);' % wname)
            self.pushIndent(2)
            self.checkAvail("elt_len", sva)
            self.popIndent(2)
            self.format("""
                    if (elt_len)
                      memcpy(ptr, obj->{c_name}.elts_, elt_len);
                    written += elt_len; ptr += elt_len;
                  }}""", c_name=sva.c_name)
            return

        if type(sva.basetype) == str:
            body = self.encodeStruct(
                sva.basetype, "{ELEMENT}", sva.structDeclaration.contextList)
        else:
            body = self.encodeInteger(
                sva, sva.basetype.width, "{ELEMENT}", True)
        iterateOverVarArray(self, sva, body)

    def visitSMString(self, ss):
        # To encode a nul-terminated string, we find its length, make sure
        # that there's enough length in the output to whole the whole thing
        # (plus a terminating NUL), and then memcpy it into the output.
        # Then we advance the written and ptr variables.

        self.eltHeader(ss)
        self.needTruncated = True
        self.format("""
                {{
                  size_t len = strlen(obj->{c_name});""", c_name=ss.c_name)
        self.pushIndent(2)
        self.checkAvail("len + 1", ss)
        self.popIndent(2)
        self.format("""
                  memcpy(ptr, obj->{c_name}, len + 1);
                  ptr += len + 1; written += len + 1;
                }}""", c_name=ss.c_name)

    def visitSMPosition(self, smp):
        pass

    def visitSMLenConstrained(self, sml):
        # To encode a length-constained field of a structure,
        # remember the position at which we began writing to the union.
        # Once we're done encoding the union members, we check to make
        # sure that the number of bytes written will fit in the length
        # field, and then use the appropriate backptr value to encode the
        # actual length.
        self.w("{\n")
        self.pushIndent(2)
        m = sml.lengthfieldmember
        if sml.lengthfield is not None:
            self.w("size_t written_before_union = written;\n")

        sml.visitChildren(self)

        if sml.lengthfield and '.' in sml.lengthfield:
            self.format("""
                trunnel_assert(written >= written_before_union);
                if (written - written_before_union != {0})
                  goto check_failed;
             """, field(sml.lengthfield))
            self.popIndent(2)
            self.w("}\n")
            return

        if m is not None:
            width = m.inttype.width
            hton = HTON_FN[width]
            self.comment('Write the length field back to %s' % sml.lengthfield)
            # We do this CPP check so that we don't generate any code
            # to check whether a size_t fits inside a uint64_t: compilers
            # don't like that.
            self.format("""
              trunnel_assert(written >= written_before_union);
              #if UINT{width}_MAX < SIZE_MAX
              if (written - written_before_union > UINT{width}_MAX)
                goto check_failed;
              #endif
              trunnel_set_uint{width}(backptr_{c_name}, {hton}(written - written_before_union));
              """, width=width, hton=hton, c_name=m.c_name)
        else:
            self.checkAvail(sml.leftoverbytes, sml)
            self.format("""
                  avail = written + {leftover};
                  enforce_avail = 1;
                  """, leftover=sml.leftoverbytes)

        self.popIndent(2)
        self.w("}\n")

    def visitSMUnion(self, smu):
        # To encode a union without a length field, we switch on the value
        # of its tag field, and handle each case appropriately.

        self.eltHeader(smu)
        self.w('trunnel_assert(written <= avail);\n')
        self.w('switch (%s) {\n' % field(smu.tagfield))
        smu.visitChildren(self)
        self.w("}\n")

    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w, um)
        self.pushIndent(2)
        um.visitChildren(self)
        self.w("break;\n")
        self.popIndent(2)
        self.popIndent(2)

    def visitSMFail(self, udf):
        # This case should have gotten caught by the check function before
        # encoding; we shouldn't be able to reach here.
        self.w('trunnel_assert(0);\n')

    def visitSMIgnore(self, udi):
        pass

    def visitSMEos(self, eos):
        pass


def intConstraintExpression(v, ranges, width):
    """Return a C expression that is true if the value 'v' is within the
       integer-constraint ranges in 'ranges', for a type of width
       'width' in bits.

       Avoid generating any checks that are always true (like u8 >= 0
       or u8 <= 255).
    """
    tests = []
    maximum = TYPE_MAXIMA[width]
    for lo, hi in ranges:
        if lo == hi:
            tests.append('%s == %s' % (v, lo))
        elif lo == 0:
            tests.append('%s <= %s' % (v, hi))
        elif hi == maximum:
            tests.append('%s >= %s' % (v, lo))
        else:
            tests.append('(%s >= %s && %s <= %s)' % (v, lo, v, hi))

    return "(%s)" % (" || ".join(tests))


class ParseFnGenerator(CodeGenerator):

    """Code-generating visitor that generates the 'typename_parse()' and
       'typename_parse_into()' functions for a given structure.

       The typename_parse_into(typename_t *, const uint8_t *, size_t)
       function takes a buffer of a given length, and attempts to
       parse it into an already-allocated object.  It returns the number of
       bytes parsed on success, -2 if the input was possibly truncated, and
       -1 if the input is invalid.  It may leave its input object in a
       half-filled state.

       The typename_parse(typename_t **, const uint8_t *, size_t)
       function behaves the same, except that instead of taking a
       pointer to an already-allocated object, it allocates a new
       object and sets the provided point to point to that object on
       success.  It is a thin wrapper.

       The generated function works by maintaining a count of the number of
       bytes remaining to parse in 'remaining', and a pointer to the next
       parseable byte in 'ptr'.  When parsing a length-constrained area,
       we temporarily reduce 'remaining'.

       INVARIANTS:
             ptr + remaining <= input + len_in
             ptr >= input
             remaining <= len_in

       It also uses these local variables:
          result -- holds the temporary value of a recursively-invoked
             parse function.
    """
    #
    # needLabels -- a set of all the labels that we have used 'goto'
    #    to reach.
    # truncatedLabel -- the label that we should goto if we find the
    #    input truncated.  This is usually 'truncated', but see below.
    # structFailLabel -- the label that we should goto if we find the
    #    input truncated.  This is usually 'relay_fail', but see below.

    def __init__(self, writefn):
        CodeGenerator.__init__(self, writefn)
        self.action = "Parse"

    def visitStructDecl(self, sd):
        if sd.isContext():
            return

        contextFormals = formatContexts(sd.contextList, declaration=True)
        contextArgs = formatContexts(sd.contextList, declaration=False)
        self.structName = name = sd.name
        self.docstring("""As %s_parse(), but do not allocate the
                          output object.""" % name)
        self.format("""
            static ssize_t
            {name}_parse_into({name}_t *obj, const uint8_t *input, const size_t len_in{formals})
            {{
              const uint8_t *ptr = input;
              size_t remaining = len_in;
              ssize_t result = 0;
              (void)result;
            """, name=name, formals=contextFormals)
        self.pushIndent(2)

        formatContextChecks(self, sd.contextList, 'return -1;')

        self.needLabels = set()
        self.truncatedLabel = "truncated"
        self.structFailLabel = "relay_fail"
        sd.visitChildren(self)

        self.w('trunnel_assert(ptr + remaining == input + len_in);\n')

        self.w('return len_in - remaining;\n\n')

        self.popIndent(2)
        if 'truncated' in self.needLabels:
            self.w(' truncated:\n  return -2;\n')
        if 'relay_fail' in self.needLabels:
            self.w(
                ' relay_fail:\n  trunnel_assert(result < 0);\n  return result;\n')
        if 'trunnel_alloc_failed' in self.needLabels:
            self.w(" trunnel_alloc_failed:\n  return -1;\n")
        if 'fail' in self.needLabels:
            self.w(' fail:\n  result = -1;\n  return result;\n')
        self.w("}\n\n")

        self.format("""
              ssize_t
              {name}_parse({name}_t **output, const uint8_t *input, const size_t len_in{formals})
              {{
                ssize_t result;
                *output = {name}_new();
                if (NULL == *output)
                  return -1;
                result = {name}_parse_into(*output, input, len_in{args});
                if (result < 0) {{
                  {name}_free(*output);
                  *output = NULL;
                }}
                return result;
              }}
              """, name=name, formals=contextFormals, args=contextArgs)

    def visitSMInteger(self, smi):
        # To parse an integer, delegate to parseInteger.
        #
        # If the integer has constraints, check them after reading its value.

        self.eltHeader(smi)
        v = "obj->%s" % (smi.c_name)
        self.parseInteger(smi.inttype.width, v)

        if smi.constraints is not None:
            expr = intConstraintExpression(
                v, smi.constraints.ranges, smi.inttype.width)

            self.needLabels.add('fail')
            self.w(('if (! %s)\n'
                    '  goto fail;\n') % (expr))

    def parseInteger(self, width, element):
        """Generate code to parse a width-bit integer into element."""
        # First, check whether we have enough bytes left.  If we do, use
        # the appropriate ntoh function and get_uint function to read from
        # the input, and adjust 'remaining' and 'ptr' appropriately.
        nbytes = width // 8
        ntoh = NTOH_FN[width]
        self.needLabels.add(self.truncatedLabel)
        self.format("""
                CHECK_REMAINING({nbytes}, {truncated});
                {element} = {ntoh}(trunnel_get_uint{width}(ptr));
                remaining -= {nbytes}; ptr += {nbytes};
                """, nbytes=nbytes, truncated=self.truncatedLabel,
                    ntoh=ntoh, width=width, element=element)

    def visitSMStruct(self, sms):
        # To generate code to parse a struture, delegate to parseStruct
        self.eltHeader(sms)
        self.w(self.parseStructInto(sms.structname, "obj->%s" %
               (sms.c_name), sms.structDeclaration.contextList))

    def parseStructInto(self, structtype, target_pointer, contextList):
        """Generate code to parse a structure from the input into
           structure pointer.
        """
        # Recursively call the appropriate parse() function, and
        # see whether it gave us an error.  If not, adjust 'remaining'
        # and 'ptr' appropriately.

        args = formatContexts(contextList, declaration=False)
        self.needLabels.add(self.structFailLabel)
        return self.format_s("""
                result = {structtype}_parse(&{target}, ptr, remaining{args});
                if (result < 0)
                  goto {fail};
                trunnel_assert((size_t)result <= remaining);
                remaining -= result; ptr += result;
                """, structtype=structtype, target=target_pointer,
                             fail=self.structFailLabel, args=args)

    def visitSMFixedArray(self, sfa):
        # To parse a fixed array of non-struct, we can precompute its
        # length by multiplying its width by the array length.  We
        # make sure that we have at least that many bytes left in the
        # input, and then we can just memcpy them into the object.
        # Then, if we're parsing uint16_t, uint32_t, or uint64_t, we need
        # to iterate over them and call the appropriate ntoh function on
        # each. Finally, we adjust the remaining and ptr fields.
        #
        # To parse a fixed array of struct, we write a for loop to
        # call the appropriate typename_parse() function repeatedly.
        #
        # (We assume that the compiler will catch it if we make any
        # fixed array too big to fit into a size_t.  Also, don't do that;
        # what kind of protocol are you implementing?)

        self.eltHeader(sfa)
        if type(sfa.basetype) != str:
            self.needLabels.add(self.truncatedLabel)
            bytesPerElt = 1
            multiplier = ""
            if type(sfa.basetype) == trunnel.Grammar.IntType:
                bytesPerElt = sfa.basetype.width // 8
                if bytesPerElt > 1:
                    multiplier = "%s * " % bytesPerElt
            self.format("""
                        CHECK_REMAINING({multiplier}{width}, {truncated});
                        memcpy(obj->{c_name}, ptr, {multiplier}{width});
                        """, c_name=sfa.c_name, multiplier=multiplier,
                        width=sfa.width, truncated=self.truncatedLabel)
            if type(sfa.basetype) == trunnel.Grammar.IntType and sfa.basetype.width > 8:
                self.format("""
                         {{
                           unsigned idx;
                           for (idx = 0; idx < {width}; ++idx)
                             obj->{c_name}[idx] = {ntoh}(obj->{c_name}[idx]);
                         }}""", width=sfa.width, c_name=sfa.c_name,
                            ntoh=NTOH_FN[sfa.basetype.width])

            self.format("remaining -= {0}{1}; ptr += {0}{1};", multiplier,
                        sfa.width)
            return

        else:
            iterateOverFixedArray(self, sfa,
                                  self.parseStructInto(sfa.basetype,
                                                       "obj->%s[idx]" % (
                                                           sfa.c_name),
                                                       sfa.structDeclaration.contextList))

    def visitSMVarArray(self, sva):
        # There are quite a few cases here. Sorry!
        #
        # To parse a variable-length array of any byte type (uint8_t
        # or char) check whether the value in the width field (if any)
        # is longer than the number of remaining bytes.  Assuming it
        # isn't, for a char array, you need to check whether it's
        # SIZE_MAX, since we're about to add 1 to it in order to
        # malloc enough space.  After that, we can use malloc (for
        # char) or TRUNNEL_DYNARRAY_EXPAND (for uint8_t) to make the
        # destination array big enough, and use memcpy to read from
        # the input.  If it's a char array, nul-terminate it and set
        # the synthetic len field if necessary.  Finally, advance the
        # remaining and ptr variables.
        #
        # For a variable-length array of some other type (uint16_t,
        # uint32_t, uint64_t, or struct), we use
        # TRUNNEL_DYNARRAY_EXPAND to make sure there's enough space.
        # Then use use a for-loop (if this is a vararray with a width
        # field) or a while-loop (if this vararray extends to the end
        # of the enclosing structure) to iteratively call the code
        # from parseInteger or parseStructInto and then place the
        # results of that call into the array with
        # TRUNNEL_DYNARRAY_ADD.  Last we advance the remaining and ptr
        # variables.

        if sva.widthfield != None:
            if sva.widthfieldmember:
                w = field(sva.widthfieldmember.c_name)
            else:
                w = field(sva.widthfield)

        self.eltHeader(sva)
        # FFFF some of this is kinda cut-and-paste
        if arrayIsBytes(sva):
            if sva.widthfield != None:
                self.w('CHECK_REMAINING(%s, %s);\n' % (
                    w, self.truncatedLabel))
            else:
                w = "remaining"

            elt = "obj->%s.elts_" % sva.c_name

            self.needLabels.add(self.truncatedLabel)

            if str(sva.basetype) == 'char':
                tp = "char"
                self.needLabels.add('fail')
                self.w(("if (%s_setstr0_%s(obj, (const char*)ptr, %s))\n"
                        "  goto fail;") % (self.structName, sva.c_fn_name, w))

            else:
                tp = "uint8_t"
                self.needLabels.add('trunnel_alloc_failed')
                self.format("""
                    TRUNNEL_DYNARRAY_EXPAND({tp}, &obj->{c_name}, {w}, {{}});
                    obj->{c_name}.n_ = {w};
                    if ({w})
                      memcpy({elt}, ptr, {w});
                    """, w=w, elt=elt, tp=tp, c_name=sva.c_name)

            self.format('ptr += {w}; remaining -= {w};\n', w=w)
            return

        else:
            self.needLabels.add('trunnel_alloc_failed')

            if type(sva.basetype) == str:
                elttype = "%s_t *" % sva.basetype
            else:
                elttype = "uint%d_t" % sva.basetype.width

            if sva.widthfield is not None:
                self.w('TRUNNEL_DYNARRAY_EXPAND(%s, &obj->%s, %s, {});\n'
                       % (elttype, sva.c_name, w))

            self.w('{\n'
                   '  %s elt;\n' % (elttype))
            if sva.widthfield is not None:
                self.w('  unsigned idx;\n')
                self.w('  for (idx = 0; idx < %s; ++idx) {\n' % w)
            else:
                self.w('  while (remaining > 0) {\n')
                # This is a bit subtle.  But if a member is truncated inside
                # a continues-to-end item, the input isn't truncated: it's
                # corrupt. (I think).  That's because if you don't really
                # know where the input ends, you can't be using continues-to-
                # end vararrays.
                oldFail = self.structFailLabel
                oldTrunc = self.truncatedLabel
                self.structFailLabel = "fail"
                self.truncatedLabel = "fail"

            self.pushIndent(4)
            if type(sva.basetype) == str:
                self.w(self.parseStructInto(
                    sva.basetype, "elt", sva.structDeclaration.contextList))
                on_fail = "{%s_free(elt);}" % sva.basetype
            else:
                self.parseInteger(sva.basetype.width, "elt")
                on_fail = "{}"

            self.w("TRUNNEL_DYNARRAY_ADD(%s, &obj->%s, elt, %s);" %
                   (elttype, sva.c_name, on_fail))

            self.popIndent(2)
            self.w('}\n')
            if sva.widthfield is None:
                self.structFailLabel = oldFail
                self.truncatedLabel = oldTrunc

            self.popIndent(2)
            self.w('}\n')

    def visitSMString(self, ss):
        # To parse a nul-terminated string, we use memchr to find the first
        # NUL in the input.  If there is no NUL, we're truncated.  We assert
        # that we're not about to overflow size_t by allocating too much,
        # and then use malloc and memcpy to grab the nul-terminated string.
        # finally, we advance the remaining and ptr variables.
        self.eltHeader(ss)
        self.needLabels.add(self.truncatedLabel)
        self.needLabels.add('fail')
        self.format("""
                {{
                  uint8_t *eos = (uint8_t*)memchr(ptr, 0, remaining);
                  size_t memlen;
                  if (eos == NULL)
                    goto {truncated};
                  trunnel_assert(eos >= ptr);
                  trunnel_assert((size_t)(eos - ptr) < SIZE_MAX - 1);
                  memlen = ((size_t)(eos - ptr)) + 1;
                  if (!(obj->{c_name} = trunnel_malloc(memlen)))
                    goto fail;
                  memcpy(obj->{c_name}, ptr, memlen);
                  remaining -= memlen; ptr += memlen;
                }}""", c_name=ss.c_name, truncated=self.truncatedLabel)

    def visitSMPosition(self, smp):
        self.format("obj->{c_name} = ptr;", c_name=smp.c_name);

    def visitSMLenConstrained(self, sml):
        # To parse a length-constrained region, make sure that at
        # least that many bytes remain in the structure.  Then,
        # temporarily set "remaining" to the value of the length
        # field, and "remaining_after" to the value that 'remaining'
        # will have after we're done parsing this region.  Then we parse
        # the region.  Finally, we check that 'remaining' is now 0.  If it
        # is, we restore it to remaining_after.  If not, we fail.

        if sml.lengthfieldmember != None:
            field_ = field(sml.lengthfieldmember.c_name)
        elif sml.lengthfield != None:
            field_ = field(sml.lengthfield)
        else:
            field_ = None

        if field_ != None:
            self.format("""
                    {{
                      size_t remaining_after;
                      CHECK_REMAINING({field}, {truncated});
                      remaining_after = remaining - {field};
                      remaining = {field};
                    """, field=field_, truncated=self.truncatedLabel)
        else:
            self.format("""
                    {{
                      size_t remaining_after;
                      CHECK_REMAINING({leftafter}, {truncated});
                      remaining_after = {leftafter};
                      remaining = remaining - {leftafter};
                    """, leftafter=sml.leftoverbytes,
                        truncated=self.truncatedLabel)

        self.pushIndent(2)
        self.needLabels.add(self.truncatedLabel)
        oldFail = self.structFailLabel
        oldTrunc = self.truncatedLabel
        self.structFailLabel = "fail"
        self.truncatedLabel = "fail"

        sml.visitChildren(self)

        self.structFailLabel = oldFail
        self.truncatedLabel = oldTrunc

        self.needLabels.add('fail')
        self.popIndent(2)
        self.format("""
                     if (remaining != 0)
                       goto fail;
                     remaining = remaining_after;
                   }}""")

    def visitSMUnion(self, smu):
        # To parse a union, we switch depending on the value of the already-
        # parsed tag field.
        self.eltHeader(smu)

        self.w('switch (%s) {\n' % field(smu.tagfield))
        self.curunion = smu

        smu.visitChildren(self)

        self.w("}\n")

    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w, um)
        self.pushIndent(2)
        um.visitChildren(self)
        self.w("break;\n")
        self.popIndent(2)
        self.popIndent(2)

    def visitSMEos(self, eos):
        # To parse an EOS assertion, we fail if "remaining" is nonzero.
        self.needLabels.add('fail')
        self.w('if (remaining)\n  goto fail;\n')

    def visitSMFail(self, udf):
        # To parse a 'fail' assertion, we fail.
        self.needLabels.add('fail')
        self.w('goto fail;\n')

    def visitSMIgnore(self, udi):
        # To parse an 'ignore' assertion, we skip to the end of 'remaining'.
        self.w('/* Skip to end of union */\n')
        self.w('ptr += remaining; remaining = 0;\n')

HEADER_BOILERPLATE = """\
/* %(h_fname)s -- generated by Trunnel v%(version)s.
 * https://gitweb.torproject.org/trunnel.git
 * You probably shouldn't edit this file.
 */
#ifndef %(guard_macro)s
#define %(guard_macro)s

#include <stdint.h>
#include "trunnel.h"

"""

HEADER_FOOTER = """

#endif
"""

MODULE_BOILERPLATE = """\
/* %(c_fname)s -- generated by Trunnel v%(version)s.
 * https://gitweb.torproject.org/trunnel.git
 * You probably shouldn't edit this file.
 */
#include <stdlib.h>
#include "trunnel-impl.h"
%(expose_definitions)s
#include "%(h_fname)s"

#define TRUNNEL_SET_ERROR_CODE(obj) \\
  do {                              \\
    (obj)->trunnel_error_code_ = 1; \\
  } while (0)

#if defined(__COVERITY__) || defined(__clang_analyzer__)
/* If we're running a static analysis tool, we don't want it to complain
 * that some of our remaining-bytes checks are dead-code. */
int %(csafe_fname)s_deadcode_dummy__ = 0;
#define OR_DEADCODE_DUMMY || %(csafe_fname)s_deadcode_dummy__
#else
#define OR_DEADCODE_DUMMY
#endif

#define CHECK_REMAINING(nbytes, label)                           \\
  do {                                                           \\
    if (remaining < (nbytes) OR_DEADCODE_DUMMY) {                \\
      goto label;                                                \\
    }                                                            \\
  } while (0)

"""


def generate_code(input_fname, extra_options=[], target_dir=None):
    """Read a trunnel file from 'input_fname' and write the result to
       appropriate output files.  If 'extra_options' is set, add those
       options as though they had been specified in the file with
       "trunnel options ..."
    """
    basename = input_fname
    if basename.endswith(".trunnel"):
        basename = basename[:-len(".trunnel")]
    if target_dir != None:
        basename = os.path.join(target_dir, os.path.split(basename)[1])

    c_fname = basename + ".c"
    h_fname = basename + ".h"
    csafe_fname = re.sub(r'[^a-zA-Z]', '', os.path.split(basename)[1])

    inp = open(input_fname, 'r')
    t = trunnel.Grammar.Lexer().tokenize(inp.read())
    inp.close()
    parsed = trunnel.Grammar.Parser().parse(t)
    parsed.options.extend(extra_options)
    c = Checker()
    c.visit(parsed)

    Annotator().visit(parsed)

    guard_macro = "TRUNNEL_" + \
        os.path.split(h_fname)[1].upper().replace(".", "_")
    expose_definitions = []
    if "opaque" in parsed.options:
        for n in c.sortedStructs:
            expose_definitions.append(
                "#define TRUNNEL_EXPOSE_%s_\n" % (n.upper()))
    boilerplate_vars = {
        'guard_macro': guard_macro,
        'h_fname': os.path.split(h_fname)[1],
        'c_fname': os.path.split(c_fname)[1],
        'csafe_fname': csafe_fname,
        'expose_definitions': "".join(expose_definitions),
        'version': trunnel.__version__
    }

    out_h = open(h_fname, 'w')
    out_h.write(HEADER_BOILERPLATE % boilerplate_vars)
    DeclarationGenerationVisitor(c.sortedStructs, out_h).visit(parsed)
    PrototypeGenerationVisitor(c.sortedStructs, out_h).visit(parsed)
    out_h.write(HEADER_FOOTER)
    out_h.close()

    out_c = open(c_fname, 'w')
    out_c.write(MODULE_BOILERPLATE % boilerplate_vars)
    if "very_opaque" in parsed.options:
        DeclarationGenerationVisitor(
            c.sortedStructs, out_c, inCFile=True).visit(parsed)
    CodeGenerationVisitor(c.sortedStructs, out_c).visit(parsed)
    out_c.close()

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
