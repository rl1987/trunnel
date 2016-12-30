# Grammar.py -- lexer, parser, and ADTs for for trunnel
#
# Copyright 2014, The Tor Project, Inc.
# See license at the end of this file for copying information.

"""
   Parser and AST for trunnel.



"""

import trunnel.spark
pattern = trunnel.spark.pattern
rule = trunnel.spark.rule

#
#
#  These are our token types. They represent a single lexeme.  They're
#  generated below by the 'Lexer' class.
#
#


class Token(object):

    """Base class for tokens. The 'type' is a string that represents the
       type of the string; the token appears on 'lineno'.
    """

    def __init__(self, type, lineno):
        self.type = type
        self.lineno = lineno

    def __str__(self):
        return self.type


class Identifier(Token):

    """A non-const C identifier"""

    def __init__(self, value, lineno):
        Token.__init__(self, "ID", lineno)
        self.value = value

    def __str__(self):
        return self.value


class ConstIdentifier(Token):

    """A const C identifier"""

    def __init__(self, value, lineno):
        Token.__init__(self, "CONST_ID", lineno)
        self.value = value

    def __str__(self):
        return self.value


class IntLiteral(Token):

    """An integer literal"""

    def __init__(self, value, lineno):
        Token.__init__(self, "INT", lineno)
        self.value = int(value, 0)


class Annotation(Token):

    """A doxygen-style comment."""

    def __init__(self, value, lineno):
        Token.__init__(self, "ANNOTATION", lineno)
        self.value = value

    def __str__(self):
        return self.value + "\n"

# Set of reserved keywords.
KEYWORDS = set("""
  union struct extern trunnel context
  u8 u16 u32 u64 char
  IN const nulterm with default fail ignore eos
""".split())


#
#
# Lexer
#
#


class Lexer(trunnel.spark.GenericScanner, object):

    """Scanner class based on trunnel.spark.GenericScanner.  Its job is to turn
       a string into a list of Token.

       Note that spark does most of the work for us here: under the
       hood, it builds a big regex out of all the @pattern decorations
       for the t_* methods, and uses that to do the scanning and
       decide which function to invoke.

    """

    def tokenize(self, input):
        self.rv = []
        self.lineno = 1
        trunnel.spark.GenericScanner.tokenize(self, input)
        return self.rv

    @pattern(r"(?:[;{}@\[\]\-=,:]|\.\.\.|\.\.|\.)")
    def t_punctuation(self, s):
        self.rv.append(Token(s, self.lineno))

    @pattern(r"[a-zA-Z_][a-zA-Z_0-9]*")
    def t_id(self, s):
        if s in KEYWORDS:
            self.rv.append(Token(s, self.lineno))
        elif s.isupper():
            self.rv.append(ConstIdentifier(s, self.lineno))
        else:
            self.rv.append(Identifier(s, self.lineno))

    @pattern(r"0x[0-9a-fA-F]+ | [0-9]+ ")
    def t_int(self, s):
        self.rv.append(IntLiteral(s, self.lineno))

    @pattern(r"[ \t]+")
    def t_space(self, s):
        pass

    @pattern(r"\/\/.*")
    def t_comment1(self, s):
        pass

    @pattern(r'/\*\*(?:[^\*]|\*+[^*/])*\*/')
    def t_annotation(self, s):
        self.rv.append(Annotation(s, self.lineno))
        self.lineno += (s.count("\n"))

    @pattern(r'/\*[^\*](?:[^\*]|\*+[^*/])*\*/')
    def t_comment2(self, s):
        self.lineno += (s.count("\n"))

    @pattern(r"\n")
    def t_newline(self, s):
        self.lineno += 1

    @pattern(r".")
    def t_default(self, s):
        raise ValueError("unmatched input: %r on line %r" % (s, self.lineno))

#
#
# AST types
#
#


class AST(object):

    """Abstract type. Base type for our abstract syntax tree structure.
    """

    def visitChildren(self, visitor, *args):
        """Invokes a visitor recursively on every sub-element of this AST
           node.
        """
        raise NotImplemented()


class File(AST):

    """Top-level entry for our AST, representing a whole file.  Contains
       constants and struct declarations.
    """
    #
    # constsnts -- a list of ConstDecl.
    # declarations -- a list of StructDecl
    # declarationsByName -- a map from name to StructDecl.

    def __init__(self, members):
        self.constants = []
        self.declarations = []
        self.declarationsByName = {}
        self.externsByName = {}  # XXXX
        self.externStructs = []
        self.options = []
        for m in members:
            self.add(m)

    def add(self, m):
        if isinstance(m, ConstDecl):
            self.constants.append(m)
        elif isinstance(m, ExternStructDecl):
            self.externStructs.append(m)
            self.externsByName[m.name] = m
        elif isinstance(m, TrunnelOptionsDecl):
            self.options.extend(m.options)
        else:
            self.declarations.append(m)
            self.declarationsByName[m.name] = m

    def visitChildren(self, v, *args):
        for c in self.constants:
            v.visit(c, *args)
        for d in self.declarations:
            v.visit(d, *args)

    def visitChildrenSorted(self, sort_order, v, *args):
        """As visitChildren, but visit the constants first, and then
           the structures in the order given by sort_order."""

        if set(sort_order) != set(self.declarationsByName.keys()):
            raise ValueError("sort_order does not match actual list "
                             "of declarations")
        for c in self.constants:
            v.visit(c, *args)

        for name in sort_order:
            v.visit(self.declarationsByName[name], *args)

    def getDeclaration(self, name):
        try:
            return self.declarationsByName[name]
        except KeyError:
            pass
        return self.externsByName[name]


class StructDecl(AST):

    """The declaration for a single structure."""
    #
    # name -- the declared name of this structure
    # members -- a list of StructMember.
    # annotation -- None, or a string holding a doxygen comment describing
    #   this structure.
    #
    # Set elsewhere (in CodeGen.Annotator):
    #   lengthFields -- a map from c_name of a field to the field itself
    #     for every field that is used as the length of a SMLenConstrained
    #   has_leftover_field -- boolean: true iff this struct contains
    #     an SMLenConstrained.
    #   constrainedIntFields -- set: names of integer fields that
    #     are referenced elsewhere in the structure.

    def __init__(self, name, members, contextList=(), isContext=False):
        self.name = name
        self.members = members
        self.annotation = None
        self.contextList = list(contextList)
        self._isContext = isContext

    def visitChildren(self, v, *args):
        for m in self.members:
            v.visit(m, *args)

    def isContext(self):
        return self._isContext


class ConstDecl(AST):

    """The declaration for a single structure."""
    #
    # name -- the declared name of this constant.
    # value -- the integer value of this constant.
    # annotation -- None, or a string holding a doxygen comment describing
    #   this constant.

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.annotation = None


class ExternStructDecl(AST):

    """Declaration that a Trunnel structure is available elsewhere."""

    def __init__(self, name, contextList=()):
        self.name = str(name)
        self.contextList = list(contextList)


class TrunnelOptionsDecl(AST):

    """Pragma options to change the behavior of the trunnel code generator."""

    def __init__(self, options, lineno):
        self.options = options
        self.lineno = lineno


class StructMember(AST):

    """Abstract type. Base type for things that can be a member of a struct."""
    #
    # annotation -- None, or a string holding a doxygen comment describing
    #   this member.
    # Set elsewhere:
    #    name -- the member id of this object.
    #    c_name -- the member id of this object, as mangled for the generated
    #       C.
    #    c_name -- the member id of this object, as mangled for function names
    #       in the generated C.

    def __init__(self, name=None):
        self.annotation = None
        self.name = name

    def getName(self):
        """Return the name of this item as it will appear in C."""
        return self.c_name


class IntType(AST):

    """A fixed-width unsigned integer type."""
    #
    # width -- the width of this type in bits. Must be 8, 16, 32, or 64.

    def __init__(self, width):
        self.width = width

    def __str__(self):
        return "u%s" % self.width


class IntConstraint(AST):

    """A constraint placed on an integer value."""
    #
    # ranges -- a list of (lo,hi) tuples such that any integer conforming to
    #   this constraint has lo <= i <= hi for some tuple in the list.
    #   Sorted after we validate the containing inttype.

    def __init__(self, ranges):
        self.ranges = ranges

    def __str__(self):
        return "[%s]" % (", ".join(self._rstr(lo, hi) for lo, hi in self.ranges))

    def _rstr(self, lo, hi):
        if lo == hi:
            return str(lo)
        else:
            return "%s..%s" % (lo, hi)


class SMInteger(StructMember):

    """An unsigned integer member of a structure"""
    #
    # constraints -- an IntConstraints, or None

    def __init__(self, inttype, name, constraints):
        StructMember.__init__(self, name)
        self.inttype = inttype
        self.constraints = constraints

    def visitChildren(self, v, *args):
        if self.constraints is not None:
            v.visit(self.constraints, *args)

    def __str__(self):
        cstr = ""
        if self.constraints:
            cstr = " IN %s" % self.constraints
        return "%s %s%s" % (self.inttype, self.getName(), cstr)

    def minimum(self):
        """Return the lowest possible value for this inttype conforming
           with its constraints."""
        if self.constraints is None:
            return 0
        else:
            return self.constraints.ranges[0][0]

    def maximum(self):
        """Return the highest possible value for this inttype conforming with
           its constraints.  Return a string with a 'UINT*_MAX'
           constants if appropriate.
        """
        if self.constraints is None:
            return "UINT%d_MAX" % self.intttype.width
        else:
            return self.constraints.ranges[-1][-1]


class SMStruct(StructMember):

    """A structure member of a structure"""
    #
    # structname -- the name of the structure type for this structure.
    # structDeclaration -- the StructDecl for the struct that this refers to.
    #     Set by Annotator.

    def __init__(self, structname, name):
        StructMember.__init__(self, name)
        self.structname = structname
        self.structDeclaration = None

    def __str__(self):
        return "struct %s %s" % (self.structname, self.getName())


class SMString(StructMember):

    """A nul-terminated string member of a structure"""

    def __init__(self, name):
        StructMember.__init__(self, name)

    def __str__(self):
        return "nulterm %s" % self.getName()


class SMFixedArray(StructMember):

    """A fixed-width array member of a structure"""
    #
    # basetype -- The base type of this array.  One of IntType, Token("char"),
    #    or a string holding a struct name.
    # width -- the number of elements in this array.  Either an integer or a
    #    string representing a constant name.
    #
    # Set elsewhere (in CodeGen.Annotator):
    # structDeclaration -- the StructDecl for the struct that this
    #     refers to, if any.  Set by Annotator.

    def __init__(self, basetype, name, width):
        StructMember.__init__(self, name)
        self.basetype = basetype
        self.width = width
        self.structDeclaration = None

    def __str__(self):
        struct = ""
        if type(self.basetype) == str:
            struct = "struct "

        return "%s%s %s[%s]" % (struct, str(self.basetype), self.getName(), self.width)


class SMVarArray(StructMember):

    """A variable-width array member of a structure."""
    #
    # basetype -- The base type of this array.  One of IntType, Token("char"),
    #    or a string holding a struct name.
    # widthfield -- A string holding the name of the field that will set
    #    the number of elements in this array, or None if this array should
    #    extend to the end of the containing structure or union.
    #
    # Set elsewhere (in CodeGen.Annotator):
    #   widthfieldmember -- The StructMember corresponding to the named
    #     widthfield, or None if lengthfield is None
    # structDeclaration -- the StructDecl for the struct that this
    #     refers to, if any.  Set by Annotator.

    def __init__(self, basetype, name, widthfield):
        StructMember.__init__(self, name)
        self.basetype = basetype
        self.widthfield = widthfield
        self.structDeclaration = None

    def __str__(self):
        struct = width = ""
        if type(self.basetype) == str:
            struct = "struct "
        if self.widthfield is not None:
            width = self.widthfield

        return "%s%s %s[%s]" % (struct, str(self.basetype), self.getName(), width)


class SMLenConstrained(StructMember):

    """A length-constrained part of a structure.  Earlier in the structure,
       there hase been an integer field; the value of that field determines
       the total length of this section.  If this section extends beyond
       that length or falls short of it, this structure is invalid."""

    #
    # lengthfield -- the name of the field holding the length for this
    #    extent, or None if this is a leftover-bytes based constraint
    # leftoverbytes -- None, or an integer of the number of bytes
    #    that must be left *after* parsing the members of this item.
    #
    # Set elsewhere (in CodeGen.Annotator):
    #   lengthfieldmember -- The StructMember corresponding to the named
    #     lengthfield, or None if lengthfield is None

    def __init__(self, lengthfield, members, leftoverbytes=None):
        StructMember.__init__(self)
        self.lengthfield = lengthfield
        self.members = members
        self.leftoverbytes = leftoverbytes

    def visitChildren(self, v, *args):
        for m in self.members:
            v.visit(m, *args)


class SMUnion(StructMember):

    """A tagged-union member of a structure"""
    #
    # tagfield -- the name of the field holding the tag for this union (str)
    # members -- a list of UnionMember.
    #
    # Set elsewhere (in CodeGen.Annotator):
    #   tagfieldmember -- The StructMember corresponding to the named
    #     tagfield.

    def __init__(self, name, tagfield, members):
        StructMember.__init__(self, name)
        self.tagfield = tagfield
        self.members = members

    def __str__(self):
        return "union %s[%s]" % (self.getName(), self.tagfield)

    def visitChildren(self, v, *args):
        for m in self.members:
            v.visit(m, *args)


class UnionMember(AST):

    """A tagged member of a union."""
    #
    # tagvalue -- an IntConstraints saying which tag values correspond to this
    #    member, or None if this is a default case.
    # decls -- an array of StructMember.
    # is_default -- true iff this is a defautl case.

    def __init__(self, tagvalue, decls):
        self.tagvalue = tagvalue
        self.decls = decls
        self.is_default = (tagvalue is None)

    def visitChildren(self, v, *args):
        for d in self.decls:
            v.visit(d, *args)


class SMFail(StructMember):

    """A struct member: denotes that parsing should never succeed on a given
       union tag.
    """
    pass


class SMEos(StructMember):

    """A struct member: denotes that additional data is not allowed."""
    pass


class SMIgnore(StructMember):

    """A struct member: denotes that additional data should be consumed and
       ignored."""
    pass

class SMPosition(StructMember):
    """ A struct member: notes that we should store a pointer to this point
        in the input when we """
    def __init__(self, name):
        StructMember.__init__(self, name)

    def __str__(self):
        return "@" + self.name


class IDReference(AST):

    """A reference to an identity in a given context."""
    # context -- the name of the context
    # ident -- the name within the context

    def __init__(self, context, ident):
        self.context = context
        self.ident = ident

    def __str__(self):
        return "%s.%s" % (self.context, self.ident)

#
#
# Parser
#
#


class Parser(trunnel.spark.GenericParser, object):

    """A parser for trunnel's grammar.  Uses trunnel.spark.GenericParser for the
       heavy lifting.

       (trunnel.spark.GenericParser is an Earley parse, with O(n^3) worst-case
       performance, but we don't care.)

       Each p_* method represents a single grammar rule in its @rule
       decoration: it gets invoked in order to reduce the items listed
       to the lhs of the rule.

    """
    #
    # lingering_structs -- a list of StructDecl for structs declared
    #    inside of other structs.  These are lifted out of their
    #    corresponding structs and treated as top-level when we
    #    build the File object.

    def __init__(self):
        trunnel.spark.GenericParser.__init__(self, "File")
        self.lingering_structs = []

    def typestring(self, token):
        return token.type

    def error(self, token):
        raise SyntaxError("%s at %s" % (token, token.lineno))

    @rule(" File ::= Declarations ")
    def p_File_0(self, info):
        d = info[0]
        d.extend(self.lingering_structs)
        return File(d)

    @rule(" Declarations ::= Declaration ")
    def p_Declarations_1(self, info):
        d = info[0]
        return [d]

    @rule(" Declarations ::= Declarations Declaration ")
    def p_Declarations_2(self, info):
        ds, d = info
        ds.append(d)
        return ds

    @rule(" Declaration ::= OptAnnotation ConstDecl ")
    def p_Decl_1(self, info):

        a, d = info
        if a:
            d.annotation = str(a)
        return d

    @rule(" Declaration ::= OptAnnotation StructDecl OptSemi ")
    def p_Decl_2(self, info):
        a, d, _1 = info
        if a:
            d.annotation = str(a)
        return d

    @rule(" Declaration ::= extern struct ID OptWithContext ; ")
    def p_Decl_3(self, info):
        return ExternStructDecl(info[2], info[3])

    @rule(" OptWithContext ::= ")
    def p_OptWithContext_1(self, info):
        return ()

    @rule(" OptWithContext ::= with context IDList")
    def p_OptWithContext_2(self, info):
        return info[2]

    @rule(" Declaration ::= trunnel ID IDList ; ")
    def p_Decl_4(self, info):
        _1, opt, options, _2 = info
        if str(opt) not in ("option", "options"):
            raise ValueError("Bad syntax for 'trunnel options' on line %d"
                             % opt.lineno)
        return TrunnelOptionsDecl(options, opt.lineno)

    @rule(" IDList ::= ID ")
    def p_IDList_1(self, info):
        return [str(info[0])]

    @rule(" IDList ::= IDList , ID ")
    def p_IDList_2(self, info):
        lst, _, item = info
        lst.append(str(item))
        return lst

    @rule(" Declaration ::= OptAnnotation ContextDecl OptSemi")
    def p_Decl_5(self, info):
        a, decl, _1 = info
        if a:
            decl.annotation = str(a)
        return decl

    @rule(" ConstDecl ::= const CONST_ID = INT ; ")
    def p_ConstDecl(self, info):
        _0, name, _1, val, _2 = info
        return ConstDecl(str(name), val)

    @rule(" StructDecl ::= struct ID OptWithContext "
           "{ StructMembers StructEnding } ")
    def p_StructDecl(self, info):
        _0, name, contexts, _1, members, ending, _2 = info
        if ending is not None:
            members.append(ending)

        return StructDecl(str(name), members, contexts)

    @rule(" OptSemi ::= ")
    def p_OptSemi_1(self, info):
             pass

    @rule(" OptSemi ::= ; ")
    def p_OptSemi_2(self, info):
             pass

    @rule(" StructEnding ::= ")
    def p_StructEnding_1(self, info):
        return None

    @rule(" StructEnding ::= eos ; ")
    def p_StructEnding_2(self, info):
        return SMEos()

    @rule(" StructEnding ::= SMRemainder ; ")
    def p_StructEnding_3(self, info):
        return info[0]

    @rule(" SMRemainder ::= OptAnnotation ArrayBase ID [ ] ")
    def p_SMRemainder(self, info):
        m = SMVarArray(info[1], info[2], None)
        if info[0]:
            m.annotation = str(info[0])
        return m

    @rule(" StructMembers ::= ")
    def p_StructMembers_1(self, info):
        return []

    @rule(" StructMembers ::= StructMembers OptAnnotation StructMember ; ")
    def p_structMembers_2(self, info):
        lst, a, m, _ = info
        if a:
            m.annotation = str(a)
        lst.append(m)
        return lst

    @rule(" Integer ::= INT ")
    def p_Integer_1(self, info):
        return info[0].value

    @rule(" Integer ::= CONST_ID")
    def p_Integer_2(self, info):
        return info[0].value

    @rule(" OptAnnotation ::= ")
    def p_OptAnnotation_1(self, info):
        return None

    @rule(" OptAnnotation ::= ANNOTATION ")
    def p_OptAnnotation_2(self, info):
        return info[0]

    @rule(" StructMember ::= SMInteger ")
    def p_StructMember_0(self, info):
        return info[0]

    @rule(" StructMember ::= SMStruct ")
    def p_StructMember_1(self, info):
        return info[0]

    @rule(" StructMember ::= SMString ")
    def p_StructMember_2(self, info):
        return info[0]

    @rule(" StructMember ::= SMArray ")
    def p_StructMember_3(self, info):
        return info[0]

    @rule(" StructMember ::= SMUnion ")
    def p_StructMember_4(self, info):
        return info[0]

    @rule(" StructMember ::= SMPosition ")
    def p_StructMember_5(self, info):
        return info[0]

    @rule(" SMInteger ::= IntType ID OptIntConstraint ")
    def p_SMInteger(self, info):
        return SMInteger(info[0], str(info[1]), info[2])

    @rule(" IntType ::= u8 ")
    def p_IntType_1(self, info):
        return IntType(8)

    @rule(" IntType ::= u16 ")
    def p_IntType_2(self, info):
        return IntType(16)

    @rule(" IntType ::= u32 ")
    def p_IntType_3(self, info):
        return IntType(32)

    @rule(" IntType ::= u64 ")
    def p_IntType_4(self, info):
        return IntType(64)

    @rule(" OptIntConstraint ::= ")
    def p_OptIntConstraint_1(self, info):
        return None

    @rule(" OptIntConstraint ::= IN [ IntList ]")
    def p_OptIntConstraint_2(self, info):
        return IntConstraint(info[2])

    @rule(" IntList ::= IntListMember ")
    def p_IntList_1(self, info):
        return [info[0]]

    @rule(" IntList ::= IntList , IntListMember ")
    def p_IntList_2(self, info):
        info[0].append(info[2])
        return info[0]

    @rule(" IntListMember ::= Integer ")
    def p_IntListMember_1(self, info):
        v = info[0]
        return (v, v)

    @rule(" IntListMember ::= Integer .. Integer ")
    def p_IntListMember_2(self, info):
        v1, _, v2 = info
        return (v1, v2)

    @rule(" SMStruct ::= struct ID ID ")
    def p_SMStruct_1(self, info):
        _, structtype, mname = info
        return SMStruct(str(structtype), str(mname))

    @rule(" SMStruct ::= StructDecl ID ")
    def p_SMStruct_2(self, info):
        decl, mname = info
        self.lingering_structs.append(decl)
        return SMStruct(decl.name, str(mname))

    @rule(" SMString ::= nulterm ID ")
    def p_SMString(self, info):
        return SMString(info[1])

    @rule(" SMArray ::= SMFixedArray ")
    def p_SMArray_1(self, info):
        return info[0]

    @rule(" SMArray ::= SMVarArray ")
    def p_SMArray_2(self, info):
        return info[0]

    @rule(" ArrayBase ::= IntType ")
    def p_ArrayBase_1(self, info):
        return info[0]

    @rule(" ArrayBase ::= struct ID ")
    def p_ArrayBase_2(self, info):
        return str(info[1])

    @rule(" ArrayBase ::= StructDecl ")
    def p_ArrayBase_3(self, info):
        decl = info[0]
        self.lingering_structs.append(decl)
        return decl.name

    @rule(" ArrayBase ::= char ")
    def p_ArrayBase_4(self, info):
        return info[0]

    @rule(" SMVarArray ::= ArrayBase ID [ IDRef ] ")
    def p_SMVarArray_1(self, info):
        return SMVarArray(info[0], str(info[1]), str(info[3]))

    @rule(" SMVarArray ::= ArrayBase ID [ .. - Integer ] ")
    def p_SMVarArray_2(self, info):
        array = SMVarArray(info[0], str(info[1]), None)
        return SMLenConstrained(None, [array], info[5])

    @rule(" SMFixedArray ::= ArrayBase ID [ Integer ] ")
    def p_SMFixedArray(self, info):
        return SMFixedArray(info[0], str(info[1]), info[3])

    @rule(" IDRef ::= ID ")
    def p_IDRef_1(self, info):
        return info[0]

    @rule(" IDRef ::= ID . ID")
    def p_IDRef_2(self, info):
        return IDReference(info[0], info[2])

    @rule(" SMUnion ::= union ID [ IDRef ] OptUnionLength { UnionMembers } ")
    def p_SMUnion(self, info):
        _1, unionfield, _2, tagfield, _3, optlength, _4, members, _5 = info
        union = SMUnion(str(unionfield), str(tagfield), members)
        if optlength is not None:
            if type(optlength) == str:
                union = SMLenConstrained(optlength, [union])
            else:
                union = SMLenConstrained(None, [union], optlength)
        return union

    @rule(" OptUnionLength ::= ")
    def p_OptUnionLength_1(self, info):
        return None

    @rule(" OptUnionLength ::= with LengthKW IDRef")
    def p_OptUnionLength_2(self, info):
        return str(info[2])

    @rule(" OptUnionLength ::= with LengthKW .. - Integer")
    def p_OptUnionLength_3(self, info):
        return info[4]

    @rule(" LengthKW ::= ID ")
    def p_LengthKW(self, info):
        if str(info[0]) != 'length':
            raise SyntaxError("Expected 'length' at %s" % info[0].lineno)
        return None

    @rule(" UnionMembers ::= UnionMember ")
    def p_UnionMembers_1(self, info):
        return [info[0]]

    @rule(" UnionMembers ::= UnionMembers UnionMember ")
    def p_UnionMembers_2(self, info):
        lst, item = info
        lst.append(item)
        return lst

    @rule(" UnionMember ::= UnionCase : UnionFields OptExtentSpec ")
    def p_UnionMember(self, info):
        tagvals, _, members, extends = info
        return UnionMember(tagvals, members + extends)

    @rule(" UnionCase ::= IntList ")
    def p_UnionCase_0(self, info):
        return info[0]

    @rule(" UnionCase ::= default ")
    def p_UnionCase_1(self, info):
        return None

    @rule(" OptExtentSpec ::= ")
    def p_OptExtentSpec_1(self, info):
        return []

    @rule(" OptExtentSpec ::= ... ; ")
    def p_OptExtentSpec_2(self, info):
        return [SMIgnore()]

    @rule(" OptExtentSpec ::= SMRemainder ; ")
    def p_OptExtentSpec_3(self, info):
        return [info[0]]

    @rule(" UnionFields ::= ; ")
    def p_UnionFields_0(self, info):
        return []

    @rule(" UnionFields ::= UnionField ; ")
    def p_UnionFields_1(self, info):
        return [info[0]]

    @rule(" UnionFields ::= UnionFields UnionField ; ")
    def p_UnionFields_2(self, info):
        fields, field, _ = info
        fields.append(field)
        return fields

    @rule(" UnionFields ::= fail ; ")
    def p_UnionFields_3(self, info):
        return [SMFail()]

    @rule(" UnionFields ::= ignore ; ")
    def p_UnionFields_4(self, info):
        return [SMIgnore()]

    @rule(" UnionFields ::= SMRemainder ; ")
    def p_UnionFields_5(self, info):
        return [info[0]]

    @rule(" UnionField ::= SMInteger ")
    def p_UnionField_1(self, info):
        return info[0]

    @rule(" UnionField ::= SMFixedArray ")
    def p_UnionField_2(self, info):
        return info[0]

    @rule(" UnionField ::= SMVarArray ")
    def p_UnionField_3(self, info):
        return info[0]

    @rule(" UnionField ::= SMString")
    def p_UnionField_4(self, info):
        return info[0]

    @rule(" UnionField ::= SMStruct ")
    def p_UnionField_5(self, info):
        return info[0]

    @rule(" UnionField ::= SMSPosition ")
    def p_UnionField_6(self, info):
        return info[0]

    @rule(" ContextDecl ::= context ID { ContextMembers } ")
    def p_ContextDecl(self, info):
        return StructDecl(str(info[1]), info[3], isContext=True)

    @rule(" ContextMembers ::= ")
    def p_ContextMembers_1(self, info):
        return []

    @rule(" ContextMembers ::= ContextMembers OptAnnotation ContextMember ")
    def p_ContextMembers_2(self, info):
        lst, a, m = info
        if a:
            m.annotation = str(a)
        lst.append(m)
        return lst

    @rule(" ContextMember ::= IntType ID ; ")
    def p_ContextMember(self, info):
        return SMInteger(info[0], str(info[1]), None)

    @rule(" SMPosition ::= @ PtrKW ID ")
    def p_SMPosition(self, info):
        return SMPosition(str(info[2]))

    @rule(" PtrKW ::= ID ")
    def p_PtrKW(self, info):
        if str(info[0]) != 'ptr':
            raise SyntaxError("Expected 'ptr' at %s" % info[0].lineno)
        return None

if __name__ == '__main__':
    print ("===== Here is our actual grammar, extracted from Grammar.py\n")

    ordering = {'File': 0, 'Declarations': 0,
                'Declaration': 1, 'StructDecl': 2, 'ConstDecl': 2,
                'StructMember': 3, 'SMInteger': 4,
                'SMArray': 4, 'SMString': 4, 'SMStruct': 4, 'SMUnion': 4
                }
    docs = []
    for item in Parser.__dict__.values():
        if not getattr(item, '__name__', '').startswith("p_"):
            continue
        doc = item.rule
        docs.append((ordering.get(doc.split()[0], 9999), doc))

    lasto = 0
    for o, d in sorted(docs):
        if o != lasto:
            print("")
            lasto = o
        print(d.rstrip())

    print("""

Additional constraints:

   Structure declarations form a DAG.

   Field references in SMVarArray and SMUnion and SMUnionLength refer
   only to earlier-occurring fields in the same structure.

   No ExtentSpec unless the union has a UnionLength.""")

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
