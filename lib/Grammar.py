
import spark

class Token(object):
    def __init__(self, type, lineno):
        self.type = type
        self.lineno = lineno

    def typestring(self):
        return self.type

    def __str__(self):
        return self.type

    def __repr__(self):
        return "Token(%r,%r)"%(self.type, self.lineno)

class Identifier(Token):
    def __init__(self, value, lineno):
        Token.__init__(self, "ID", lineno)
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return "Identifier(%r,%r)"%(self.value, self.lineno)

class ConstIdentifier(Token):
    def __init__(self, value, lineno):
        Token.__init__(self, "CONST_ID", lineno)
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return "ConstIdentifier(%r,%r)"%(self.value, self.lineno)

class IntLiteral(Token):
    def __init__(self, value, lineno):
        Token.__init__(self, "INT", lineno)
        self.value = int(value)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "IntLiteral(%r,%r)"%(self.value, self.lineno)

class Annotation(Token):
    def __init__(self, value, lineno):
        Token.__init__(self, "ANNOTATION", lineno)
        self.value = value

    def __str__(self):
        return self.value + "\n"

KEYWORDS = set("""
  union struct
  u8 u16 u32 u64 char
  IN const nulterm WITH LENGTH default fail ignore
""".split())

class Lexer(spark.GenericScanner, object):
    def tokenize(self, input):
        self.rv = []
        self.lineno = 1
        spark.GenericScanner.tokenize(self, input)
        return self.rv

    def t_punctuation(self, s):
        r"(?:[;{}\[\]=,:]|\.\.\.|\.\.)"
        self.rv.append(Token(s, self.lineno))

    def t_const_id(self, s):
        r"[A-Z_][A-Z_0-9]*"
        if s in KEYWORDS:
            self.rv.append(Token(s, self.lineno))
        else:
            self.rv.append(ConstIdentifier(s, self.lineno))

    def t_id(self, s):
        r"[a-z_][a-z_0-9]*"
        if s in KEYWORDS:
            self.rv.append(Token(s, self.lineno))
        else:
            self.rv.append(Identifier(s, self.lineno))

    def t_int(self, s):
        r"[0-9]+"
        self.rv.append(IntLiteral(s, self.lineno))

    def t_space(self, s):
        r"[ \t]+"
        pass

    def t_comment(self, s):
        r"\/\/.*"
        pass

    def t_annotation(self, s):
        r'/\*\*(?:[^\*]|\*+[^*/])*\*/'
        self.rv.append(Annotation(s, self.lineno))

    def t_newline(self, s):
        r"\n"
        self.lineno += 1


    def t_default(self, s):
        r"."
        raise ValueError("unmatched input: %r on line %r" % (s,self.lineno))


class AST(object):
    def visitChildren(self, visitor, *args):
        raise NotImplemented()

class File(AST):
    def __init__(self, members):
        self.constants = []
        self.declarations = []
        self.declarationsByName = {}
        for m in members:
            self.add(m)

    def add(self, m):
        if isinstance(m, ConstDecl):
            self.constants.append(m)
        else:
            self.declarations.append(m)
            self.declarationsByName[m.name] = m

    def visitChildren(self, v, *args):
        for c in self.constants:
            v.visit(c, *args)
        for d in self.declarations:
            v.visit(d, *args)

    def visitChildrenSorted(self, sort_order, v, *args):
        if set(sort_order) != set(self.declarationsByName.keys()):
            raise ValueError("sort_order does not match actual list "
                             "of declartions")
        for c in self.constants:
            v.visit(c, *args)

        for name in sort_order:
            v.visit(self.declarationsByName[name], *args)

class StructDecl(AST):
    def __init__(self, name, members):
        self.name = name
        self.members = members
        self.annotation = None

    def visitChildren(self, v, *args):
        for m in self.members:
            v.visit(m, *args)

class ConstDecl(AST):
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.annotation = None

class StructMember(AST):
    def __init__(self):
        self.annotation = None

    def getName(self):
        if hasattr(self, 'c_name'):
            return self.c_name
        else:
            return self.name

class IntType(AST):
    def __init__(self, width):
        self.width = width

    def __str__(self):
        return "u%s"%self.width

class IntConstraint(AST):
    def __init__(self, ranges):
        self.ranges = ranges

    def __str__(self):
        return "[%s]"%(", ".join(self._rstr(lo,hi) for lo, hi in self.ranges))

    def _rstr(self, lo, hi):
        if lo == hi:
            return str(lo)
        else:
            return "%s..%s"%(lo,hi)

class SMInteger(StructMember):
    def __init__(self, inttype, name, constraints):
        StructMember.__init__(self)
        self.inttype = inttype
        self.name = name
        self.constraints = constraints

    def visitChildren(self, v, *args):
        if self.constraints is not None:
            v.visit(self.constraints, *args)

    def __str__(self):
        cstr = ""
        if self.constraints:
            cstr = " IN %s" % self.constraints
        return "%s %s%s"%(self.inttype, self.getName(), cstr)

class SMStruct(StructMember):
    def __init__(self, structname, name):
        StructMember.__init__(self)
        self.structname = structname
        self.name = name

    def __str__(self):
        return "struct %s %s"%(self.structname, self.getName())

class SMString(StructMember):
    def __init__(self, name):
        StructMember.__init__(self)
        self.name = name

    def __str__(self):
        return "nulterm %s"%self.getName()

class SMFixedArray(StructMember):
    def __init__(self, basetype, name, width):
        StructMember.__init__(self)
        self.basetype = basetype
        self.name = name
        self.width = width

    def __str__(self):
        struct = ""
        if type(self.basetype) == str:
            struct = "struct "

        return "%s%s %s[%s]"%(struct, str(self.basetype), self.getName(), self.width)

class SMVarArray(StructMember):
    def __init__(self, basetype, name, widthfield):
        StructMember.__init__(self)
        self.basetype = basetype
        self.name = name
        self.widthfield = widthfield

    def __str__(self):
        struct = ""
        if type(self.basetype) == str:
            struct = "struct "

        return "%s%s %s[%s]"%(struct, str(self.basetype), self.getName(), self.widthfield)

class SMRemainder(StructMember):
    def __init__(self, name):
        StructMember.__init__(self)
        self.name = name

    def __str__(self):
        return "u8 %s[]"%(self.getName())

class SMUnion(StructMember):
    def __init__(self, name, tagfield, lengthfield, members):
        StructMember.__init__(self)
        self.name = name
        self.tagfield = tagfield
        self.lengthfield = lengthfield
        self.members = members

    def __str__(self):
        lenf = ""
        if self.lengthfield:
            lenf = " WITH LENGTH %s"%self.lengthfield
        return "union %s[%s]%s"%(self.getName(), self.tagfield, lenf)

    def visitChildren(self, v, *args):
        for m in self.members:
            v.visit(m, *args)

class UnionMember(AST):
    def __init__(self, tagvalue, decls):
        self.tagvalue = tagvalue
        self.decls = decls
        self.is_default = (tagvalue is None)

    def visitChildren(self, v, *args):
        for d in self.decls:
            v.visit(d, *args)

class SMFail(StructMember):
    pass

class SMEos(StructMember):
    pass

class SMIgnore(StructMember):
    pass

class Parser(spark.GenericParser, object):
    def __init__(self):
        spark.GenericParser.__init__(self, "File")

    def typestring(self, token):
        return token.type

    def error(self, token):
        raise SyntaxError("%s at %s" %(token, token.lineno))

    def p_File_0(self, info):
        " File ::= Declaration "
        d = info[0]
        return File([d])

    def p_File_1(self, info):
        " File ::= File Declaration "
        f, d = info
        f.add(d)
        return f

    def p_Decl_1(self, info):
        " Declaration ::= OptAnnotation ConstDecl "
        a, d = info
        if a:
            d.annotation = str(a)
        return d

    def p_Decl_2(self, info):
        " Declaration ::= OptAnnotation StructDecl "
        a,d = info
        if a:
            d.annotation = str(a)
        return d

    def p_ConstDecl(self, info):
        " ConstDecl ::= const CONST_ID = INT ; "
        _0, name, _1, val, _2 = info
        return ConstDecl(str(name), val)

    def p_StructDecl(self, info):
        " StructDecl ::= struct ID { StructMembers StructEnding } "
        _0, name, _1, members, ending, _2 = info
        if ending is not None:
            members.append(ending)

        return StructDecl(str(name), members)

    def p_StructEnding_1(self, info):
        " StructEnding ::= "
        return SMEos()

    def p_StructEnding_2(self, info):
        " StructEnding ::= ... "
        return None

    def p_StructEnding_3(self, info):
        " StructEnding ::= SMRemainder ; "
        return info[0]

    def p_SMRemainder(self, info):
        " SMRemainder ::= OptAnnotation u8 ID [ ] "
        m = SMRemainder(str(info[2]))
        if info[0]:
            m.annotation = str(info[0])
        return m

    def p_StructMembers_1(self, info):
        " StructMembers ::= OptAnnotation StructMember ; "
        a, m, _ = info
        if a:
            m.annotation = str(a)
        return [ m ]

    def p_structMembers_2(self, info):
        " StructMembers ::= StructMembers OptAnnotation StructMember ; "
        lst, a, m, _ = info
        if a:
            m.annotation = str(a)
        lst.append(m)
        return lst

    def p_Integer_1(self, info):
        " Integer ::= INT "
        return info[0].value

    def p_Integer_2(self, info):
        " Integer ::= CONST_ID"
        return info[0].value

    def p_OptAnnotation_1(self, info):
        " OptAnnotation ::= "
        return None
    def p_OptAnnotation_2(self, info):
        " OptAnnotation ::= ANNOTATION "
        return info[0]

    def p_StructMember_0(self,info):
        " StructMember ::= SMInteger "
        return info[0]
    def p_StructMember_1(self,info):
        " StructMember ::= SMStruct "
        return info[0]
    def p_StructMember_2(self,info):
        " StructMember ::= SMString "
        return info[0]
    def p_StructMember_3(self,info):
        " StructMember ::= SMArray "
        return info[0]
    def p_StructMember_4(self,info):
        " StructMember ::= SMUnion "
        return info[0]

    def p_SMInteger(self,info):
        " SMInteger ::= IntType ID OptIntConstraint "
        return SMInteger(info[0], str(info[1]), info[2])

    def p_IntType_1(self,info):
        " IntType ::= u8 "
        return IntType(8)
    def p_IntType_2(self,info):
        " IntType ::= u16 "
        return IntType(16)
    def p_IntType_3(self,info):
        " IntType ::= u32 "
        return IntType(32)
    def p_IntType_4(self,info):
        " IntType ::= u64 "
        return IntType(64)

    def p_OptIntConstraint_1(self,info):
        " OptIntConstraint ::= "
        return None
    def p_OptIntConstraint_2(self,info):
        " OptIntConstraint ::= IN [ IntList ]"
        return IntConstraint(info[2])

    def p_IntList_1(self, info):
        " IntList ::= IntListMember "
        return [ info[0] ]
    def p_IntList_2(self, info):
        " IntList ::= IntList , IntListMember "
        info[0].append(info[2])
        return info[0]

    def p_IntListMember_1(self, info):
        " IntListMember ::= Integer "
        v = info[0]
        return (v,v)
    def p_IntListMember_2(self, info):
        " IntListMember ::= Integer .. Integer "
        v1, _, v2 = info
        return (v1,v2)

    def p_SMStruct(self, info):
        " SMStruct ::= struct ID ID "
        _, structtype, mname = info
        return SMStruct(str(structtype), str(mname))

    def p_SMString(self, info):
        " SMString ::= nulterm ID "
        return SMString(info[1])

    def p_SMArray_1(self, info):
        " SMArray ::= SMFixedArray "
        return info[0]
    def p_SMArray_2(self, info):
        " SMArray ::= SMVarArray "
        return info[0]

    def p_ArrayBase_1(self, info):
        " ArrayBase ::= IntType "
        return info[0]
    def p_ArrayBase_2(self, info):
        " ArrayBase ::= struct ID "
        return str(info[1])
    def p_ArrayBase_3(self, info):
        " ArrayBase ::= char "
        return info[0]

    def p_SMVarArray(self, info):
        " SMVarArray ::= ArrayBase ID [ ID ] "
        return SMVarArray(info[0], str(info[1]), str(info[3]))

    def p_SMFixedArray(self, info):
        " SMFixedArray ::= ArrayBase ID [ Integer ] "
        return SMFixedArray(info[0], str(info[1]), info[3])

    def p_SMUnion(self, info):
        " SMUnion ::= union ID [ ID ] OptUnionLength { UnionMembers OptUMDefault } "
        _1, unionfield, _2, tagfield, _3, optlength, _4, members, optdefault, _5, = info
        members.append(optdefault)
        return SMUnion(str(unionfield), str(tagfield), optlength, members)

    def p_OptUnionLength_1(self, info):
        " OptUnionLength ::= "
        return None

    def p_OptUnionLength_2(self, info):
        " OptUnionLength ::= WITH LENGTH ID"
        return str(info[2])

    def p_UnionMembers_1(self, info):
        " UnionMembers ::= UnionMember ; "
        return [ info[0] ]

    def p_UnionMembers_2(self, info):
        " UnionMembers ::= UnionMembers UnionMember ; "
        lst, item, _ = info
        lst.append(item)
        return lst

    def p_UnionMember(self, info):
        " UnionMember ::= IntList : UnionFields OptExtentSpec "
        tagvals, _, members, extends = info
        if extends is not None:
            members.append(extends)
        return UnionMember(tagvals, members)

    def p_OptExtentSpec_1(self, info):
        " OptExtentSpec ::= "
        return None
    def p_OptExtentSpec_2(self, info):
        " OptExtentSpec ::= ... "
        return SMIgnore()
    def p_OptExtendSpec_3(self, info):
        " OptExtentSpec ::= ; SMRemainder "
        return info[1]

    def p_UnionFields_1(self, info):
        " UnionFields ::= UnionField "
        return [ info[0] ]

    def p_UnionFields_2(self, info):
        " UnionFields ::= UnionFields ; UnionField "
        fields, _, field = info
        fields.append(field)
        return fields

    def p_UnionField_1(self, info):
        " UnionField ::= SMInteger "
        return info[0]
    def p_UnionField_2(self, info):
        " UnionField ::= SMFixedArray "
        return info[0]
    def p_UnionField_3(self, info):
        " UnionField ::= SMString"
        return info[0]
    def p_UnionField_4(self, info):
        " UnionField ::= SMStruct "
        return info[0]

    def p_OptUMDefault_0(self, info):
        " OptUMDefault ::= "
        return UnionMember(None, [ SMFail() ])

    def p_OptUMDefault_1(self, info):
        " OptUMDefault ::= default : SMRemainder ; "
        return UnionMember(None, [ info[2] ])

    def p_OptUMDefault_2(self, info):
        " OptUMDefault ::= default : fail ; "
        return UnionMember(None, [ SMFail() ])

    def p_OptUMDefault_3(self, info):
        " OptUMDefault ::= default : ignore ; "
        return UnionMember(None, [ SMIgnore() ])


