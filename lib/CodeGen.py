
import Grammar

class ASTVisitor(object):
    def __init__(self):
        pass
    def visit(self, ast, *args):
        name = "visit" + ast.__class__.__name__
        method = getattr(self, name, self.visit_other)
        return method(ast, *args)

    def visit_other(self, ast, *args):
        raise ValueError("visit" + ast.__class__.__name__)

class CheckError(Exception):
    pass

TYPE_MAXIMA = {
    8  : (1<<8) -1,
    16 : (1<<16)-1,
    32 : (1<<32)-1,
    64 : (1<<64)-1,
}

HTON_FN = {
    8 : '',
    16 : 'htons',
    32 : 'htonl',
    64 : 'trunnel_htonll'
}
NTOH_FN = {
    8 : '',
    16 : 'ntohs',
    32 : 'ntohl',
    64 : 'trunnel_ntohll'
}


class Checker(ASTVisitor):
    def __init__(self):
        ASTVisitor.__init__(self)
        self.structNames = set()
        self.constNames = set()
        self.constValues = {}
        self.structFieldNames = None
        self.structUses = {}
        self.memberPrefix = ""

    def visitFile(self, f):
        for c in f.constants:
            if c.name in self.constNames:
                raise CheckError("duplicate constant name %s"%c.name)
            self.constNames.add(c.name)
        for d in f.declarations:
            if d.name in self.structNames:
                raise CheckError("duplicate structure name %s"%d.name)
            self.structNames.add(d.name)
        f.visitChildren(self)

        # Compute the transitive closure of self.structUses
        while True:
            changed = False
            for structname, uses in self.structUses.items():
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
        for structname, uses in self.structUses.items():
            if structname in uses:
                raise CheckError("There is a cycle in the %s structure"%structname)

        # Perform a topological sort.
        sorted_structs = []
        removed = set()
        while len(self.structUses):
            removed_this_time = []
            for structname, uses in self.structUses.items():
                uses.difference_update(removed)
                if len(uses) == 0:
                    removed_this_time.append(structname)

            removed_this_time.sort()
            sorted_structs.extend(removed_this_time)
            removed.update(removed_this_time)

            for s in removed_this_time:
                del self.structUses[s]

        self.sortedStructs = sorted_structs

    def visitConstDecl(self, cd):
        self.constValues[cd.name] = cd.value.value

    def visitStructDecl(self, sd):
        self.structFieldNames = set()
        self.structIntFieldNames = { }
        self.structName = sd.name
        self.structUses[sd.name] = set()
        sd.visitChildren(self)
        self.structFieldNames = None
        self.structIntFieldNames = None

    def addMemberName_(self, m):
        if m in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,m))
        self.structFieldNames.add(m)

    def addMemberName(self, m):
        self.addMemberName_(m)

        if self.memberPrefix != "":
            m = self.addMemberName_("%s%s"%(self.memberPrefix, m))

    def visitSMInteger(self, smi):
        self.addMemberName(smi.name)

        self.structIntFieldNames[smi.name] = smi.inttype.width

        self.containing = "%s.%s"%(self.structName,smi.name)
        self.containingType = smi.inttype
        smi.visitChildren(self)
        self.containing = None
        self.containingType = None

    def visitIntConstraint(self, ic):
        maximum = TYPE_MAXIMA[self.containingType.width]
        self.checkIntegerList(ic.ranges, maximum, None)

    def visitSMStruct(self, sms):
        self.addMemberName(sms.name)

        if sms.structname not in self.structNames:
            raise CheckError("Unrecognized structure %s used in %s"%(
                sms.structname,self.structName))

        self.structUses[self.structName].add(sms.structname)

    def visitSMFixedArray(self, sfa):
        self.addMemberName(sfa.name)

        if type(sfa.width) == str:
            self.expandConstant(sfa.width)

        if type(sfa.basetype) == str:
            if sfa.basetype not in self.structNames:
                raise CheckError("Unrecognized structure %s used in %s.%s"%(
                    sfa.basetype,self.structName,sfa.name))

            self.structUses[self.structName].add(sfa.basetype)

    def visitSMVarArray(self, sva):
        self.addMemberName(sva.name)

        self.checkIntField(sva.widthfield, "length", "%s.%s"%
                           (self.structName,sva.name))

        if type(sva.basetype) == str:
            if sva.basetype not in self.structNames:
                raise CheckError("Unrecognized structure %s used in %s.%s"%(
                    sva.basetype,self.structName,sva.name))

            self.structUses[self.structName].add(sva.basetype)

    def visitSMString(self, sms):
        self.addMemberName(sms.name)

    def visitSMRemainder(self, smr):
        self.addMemberName(smr.name)
        self.addMemberName(smr.name+"_len")

    def visitSMUnion(self, smu):
        self.addMemberName(smu.name)

        self.checkIntField(smu.tagfield, "tag", "%s.%s"%
                           (self.structName,smu.name))
        if smu.lengthfield is not None:
            self.checkIntField(smu.lengthfield, "length", "%s.%s"%
                               (self.structName,smu.name))

        self.curunion = smu
        self.unionHasLength = smu.lengthfield is not None
        self.unionName = smu.name
        self.unionMatching = []
        self.unionTagMax = TYPE_MAXIMA[self.structIntFieldNames[smu.tagfield]]
        self.containing = "%s.%s"%(self.structName,smu.name)
        self.memberPrefix = smu.name+"_"
        smu.visitChildren(self)
        self.curunion = None

        self.unionMatching.sort()
        lasthi = -1
        for lo,hi in self.unionMatching:
            if lo <= lasthi:
                raise CheckError("Duplicate tag values in %s.%s"%
                                 (self.structName,smu.name))
            assert hi >= lo
            lasthi = hi

        self.memberPrefix = ""
        self.unionName = None
        self.unionMatching = None
        self.unionTagMax = None
        self.containing = None

    def visitUnionMember(self, um):
        if um.tagvalue is not None:
            self.checkIntegerList(um.tagvalue, self.unionTagMax, self.unionMatching)

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
        if self.curunion is not None and not self.unionHasLength:
            raise CheckError("'...' found in union %s without a length field"%
                             self.containing)

    def checkIntegerList(self, lst, maximum, expandInto=None):
        for lo, hi in lst:
            if type(lo) == str:
                lo = self.expandConstant(lo)
            if type(hi) == str:
                hi = self.expandConstant(hi)
            if lo > hi:
                raise CheckError("Bad range in %s", self.containing)
            if lo > maximum:
                raise CheckError("Tag value %s out of range in %s",
                                 lo,self.containing)
            if hi > maximum:
                raise CheckError("Tag value %s out of range in %s",
                                 hi,self.containing)

            if expandInto != None:
                expandInto.append( (lo, hi) )

    def expandConstant(self, const):
        try:
            return self.constValues[const]
        except KeyError:
            raise CheckError("Unrecognized constant %s in %s"%(
                const, self.containing))

    def checkIntField(self, fieldname, ftype, inside):
        if fieldname not in self.structFieldNames:
            raise CheckError("Unrecognized %s field %s for %s"%(
                ftype,fieldname,inside))

        if fieldname not in self.structIntFieldNames:
            raise CheckError("Non-integer %s field %s for %s"%(
                ftype,fieldname,inside))

class Annotator(ASTVisitor):
    def __init__(self):
        ASTVisitor.__init__(self)
        self.prefix = ""
        self.memberByName = {}

    def visitFile(self, f):
        f.visitChildren(self)

    def visitConstDecl(self, cd):
        pass

    def visitStructDecl(self, sd):
        self.cur_struct_obj = sd
        self.cur_struct = sd.name
        sd.unionLengthFields = { }
        sd.visitChildren(self)
        self.cur_struct = None
        self.cur_struct_obj = None

    def annotateMember(self, member):
        member.c_name = "%s%s" % (self.prefix, member.name)
        self.memberByName[member.name] = member

    def visitSMInteger(self, smi):
        self.annotateMember(smi)
    def visitSMStruct(self, sms):
        self.annotateMember(sms)
    def visitSMFixedArray(self, sfa):
        self.annotateMember(sfa)
    def visitSMVarArray(self, sva):
        self.annotateMember(sva)
        sva.widthfieldmember = self.memberByName[sva.widthfield]
    def visitSMString(self, ss):
        self.annotateMember(ss)
    def visitSMRemainder(self, smr):
        self.annotateMember(smr)
    def visitSMUnion(self, smu):
        self.annotateMember(smu)
        self.prefix = smu.name + "_"
        smu.visitChildren(self)
        self.prefix = ""
        smu.tagfieldmember = self.memberByName[smu.tagfield]
        if smu.lengthfield is not None:
            m = self.memberByName[smu.lengthfield]
            self.cur_struct_obj.unionLengthFields[m.c_name] = m
            smu.lengthfieldmember = m
        else:
            smu.lengthfieldmember = None
    def visitUnionMember(self, um):
        um.visitChildren(self)
    def visitSMFail(self, fail):
        pass
    def visitSMEos(self, eos):
        pass
    def visitSMIgnore(self, ignore):
        pass


class IndentingGenerator(ASTVisitor):
    def __init__(self, writefn):
        self.w_ = writefn
        self.indent = ""
        self.action = "Handle"

    def w(self, string):
        lines = string.split("\n")
        if lines[-1] == "":
            del lines[-1]
        for line in lines:
            if line.isspace() or not line:
                self.w_('\n')
            else:
                self.w_("%s%s\n"%(self.indent, line))
    def pushIndent(self, n):
        self.indent += " "*n

    def popIndent(self, n):
        self.indent = self.indent[:-n]

    def comment(self, string):
        self.w('/* %s */\n'%string)

    def eltHeader(self, element, skipLine=True):
        nl = ("\n" if skipLine else "")
        self.w('%s/* %s %s */\n'%(nl, self.action, element))

class DeclarationGenerationVisitor(IndentingGenerator):
    def __init__(self, sort_order, f):
        IndentingGenerator.__init__(self, f.write)
        self.sort_order = sort_order

    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)

    def visitConstDecl(self, cd):
        if cd.annotation != None:
            self.w(cd.annotation)
        self.w("#define %s %s\n"%(cd.name,cd.value.value))

    def visitStructDecl(self, sd):
        if sd.annotation != None:
            self.w(sd.annotation)
        self.w("typedef struct %s_st {\n"%sd.name)
        self.pushIndent(2)
        sd.visitChildren(self)
        self.popIndent(2)
        self.w("} %s_t;\n\n"%sd.name);

    def visitSMInteger(self, smi):
        if smi.annotation != None:
            self.w(smi.annotation)
        self.w("uint%d_t %s;\n"%(smi.inttype.width,smi.c_name))

    def visitSMStruct(self, sms):
        if sms.annotation != None:
            self.w(sms.annotation)

        self.w("%s_t %s;\n"%(sms.structname,sms.c_name))

    def visitSMFixedArray(self, sfa):
        if sfa.annotation != None:
            self.w(sfa.annotation)

        if type(sfa.basetype) == str:
            self.w("%s_t *%s[%s];\n"%(sfa.basetype, sfa.c_name, sfa.width))
        elif str(sfa.basetype) == "char":
            self.w("char %s[%s+1];\n"%(sfa.c_name, sfa.width))
        else:
            self.w("uint%d_t %s[%s];\n"%(sfa.basetype.width, sfa.c_name, sfa.width))

    def visitSMVarArray(self, sva):
        if sva.annotation != None:
            self.w(sva.annotation)

        if str(sva.basetype) == "char":
            self.w("char *%s;\n"%(sva.c_name))
        elif type(sva.basetype) == str:
            self.w("TRUNNEL_DYNARRAY_HEAD(, %s_t *) %s;\n"%(sva.basetype, sva.c_name))
        else:
            self.w("TRUNNEL_DYNARRAY_HEAD(, uint%d_t) %s;\n"%(sva.basetype.width, sva.c_name))

    def visitSMString(self, ss):
        if ss.annotation != None:
            self.w(ss.annotation)

        self.w("char *%s;\n"%(ss.c_name))

    def visitSMRemainder(self, smr):
        self.w("/** Length of %s */"%smr.c_name)
        self.w("size_t %s_len;\n"%(smr.c_name))
        if smr.annotation != None:
            self.w(smr.annotation)
        self.w("uint8_t *%s;\n"%(smr.c_name))

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

class PrototypeGenerationVisitor(IndentingGenerator):
    def __init__(self, sort_order, f, static=False):
        IndentingGenerator.__init__(self, f.write)
        self.sort_order = sort_order
        self.static = static
    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)
    def visitConstDecl(self, cd):
        pass
    def visitStructDecl(self, sd):
        name = sd.name
        if self.static:
            self.w("static ssize_t %s_parse_into(%s_t *obj, const uint8_t *input, const size_t len_in);\n"%(name,name))
            return

        self.w("%s_t *%s_new(void);\n"%(name,name))
        self.w("void %s_free(%s_t *victim);\n"%(name, name))
        self.w("ssize_t %s_parse(%s_t **output, const uint8_t *input, const size_t len_in);\n"%(name,name))
        self.w("ssize_t %s_encode(uint8_t *output, const size_t avail, const %s_t *input);\n"%(name,name))

        self.structName = name
        sd.visitChildren(self)
        self.w("\n")

    def visit_other(self, ast, *args):
        pass

    def visitSMUnion(self, smu):
        smu.visitChildren(self)

    def visitUnionMember(self, um):
        um.visitChildren(self)

    def visitSMVarArray(self, sva):
        if str(sva.basetype) == 'char':
            return

        st = self.structName
        nm = sva.c_name
        if type(sva.basetype) == str:
            elttype = "%s_t *"%sva.basetype
        else:
            elttype = "uint%d_t"%sva.basetype.width

        self.w("size_t %s_get_%s_len(const %s_t *inp);\n"%(st,nm,st))
        self.w("%s %s_get_%s(const %s_t *inp, size_t idx);\n"%(elttype,st,nm,st))
        self.w("void %s_set_%s(%s_t *inp, size_t idx, %s elt);\n"
               %(st,nm,st,elttype))
        self.w("int %s_add_%s(%s_t *inp, %s elt);\n"
               %(st,nm,st,elttype))

class CodeGenerationVisitor(IndentingGenerator):
    def __init__(self, sort_order, f):
        IndentingGenerator.__init__(self, f.write)
        self.sort_order = sort_order
        self.generators = [ NewFnGenerator, FreeFnGenerator,
                            AccessorFnGenerator, CheckFnGenerator,
                            EncodeFnGenerator, ParseFnGenerator ]
    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)
    def visitConstDecl(self, cd):
        pass
    def visitStructDecl(self, sd):
        for g in self.generators:
            g(self.w).visit(sd)

class NewFnGenerator(ASTVisitor):
    def __init__(self, writefn):
        self.w = writefn
    def visitStructDecl(self, sd):
        name = sd.name
        self.w("%s_t *\n%s_new(void)\n{\n"%(name,name))
        self.w("  return trunnel_calloc(1, sizeof(%s_t));\n"%name)
        self.w("}\n\n");

class FreeFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("static void\n%s_clear(%s_t *obj)\n{\n"%(name,name))
        self.pushIndent(2)
        self.w("if (obj == NULL)\n  return;\n")
        sd.visitChildren(self)
        self.popIndent(2)
        self.w("}\n\n")
        self.w("void\n%s_free(%s_t *obj)\n{\n"%(name,name))
        self.pushIndent(2)
        self.w("if (obj == NULL)\n  return;\n")
        self.w("%s_clear(obj);\n"%name)
        self.w("trunnel_free_(obj);\n")
        self.popIndent(2)
        self.w("}\n\n");
    def visitSMInteger(self, smi):
        pass
    def visitSMFixedArray(self, sfa):
        if type(sfa.basetype) == str:
            body = "%s_free(obj->%s[idx]);\n"%(sfa.basetype,sfa.c_name)
            iterateOverFixedArray(self, sfa, body)

    def visitSMStruct(self, sms):
        self.w("%s_clear(&obj->%s);\n"%(sms.structname, sms.c_name))
    def visitSMVarArray(self, sva):
        if type(sva.basetype) == str:
            body = "%s_free(TRUNNEL_DYNARRAY_GET(&obj->%s, idx));\n"%(sva.basetype,sva.c_name)
            iterateOverVarArray(self, sva, body)

        if str(sva.basetype) == 'char':
            self.w('trunnel_free(obj->%s);\n'%sva.c_name)
        else:
            self.w("TRUNNEL_DYNARRAY_CLEAR(&obj->%s);\n"%(sva.c_name))

    def visitSMString(self, ss):
        self.w("trunnel_free(obj->%s);\n"%(ss.c_name))
    def visitSMRemainder(self, smr):
        self.w("trunnel_free(obj->%s);\n"%(smr.c_name))
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

class AccessorFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)

    def visit_other(self, ast, *args):
        pass

    def visitStructDecl(self, sd):
        self.structName = sd.name
        sd.visitChildren(self)

    def visitSMUnion(self, smu):
        smu.visitChildren(self)

    def visitUnionMember(self, um):
        um.visitChildren(self)

    def visitSMVarArray(self, sva):
        if str(sva.basetype) == 'char':
            return

        st = self.structName
        nm = sva.c_name
        if type(sva.basetype) == str:
            elttype = "%s_t *"%sva.basetype
        else:
            elttype = "uint%d_t"%sva.basetype.width

        self.w("size_t\n%s_get_%s_len(const %s_t *inp)\n"%(st,nm,st))
        self.w("{\n"
               "  return TRUNNEL_DYNARRAY_LEN(&inp->%s);\n"
               "}\n\n"%nm)

        self.w("%s\n%s_get_%s(const %s_t *inp, size_t idx)\n"%(elttype,st,nm,st))
        self.w("{\n"
               "  return TRUNNEL_DYNARRAY_GET(&inp->%s, idx);\n"
               "}\n\n"%nm)
        self.w("void\n%s_set_%s(%s_t *inp, size_t idx, %s elt)\n"
               %(st,nm,st,elttype))
        self.w("{\n"
               "  TRUNNEL_DYNARRAY_SET(&inp->%s, idx, elt);\n"
               "}\n\n"%nm)
        self.w("int\n%s_add_%s(%s_t *inp, %s elt)\n"
               %(st,nm,st,elttype))
        self.w("{\n"
               "  TRUNNEL_DYNARRAY_ADD(%s, &inp->%s, elt);\n"
               "  return 0;\n"
               " trunnel_alloc_failed:\n"
               "  return -1;\n"
               "}\n\n"%(elttype,nm))

def iterateOverFixedArray(generator, sfa, body, extraDecl=None):
    body = body.replace("ELEMENT", "obj->%s[idx]"%sfa.c_name)
    generator.w("{\n")
    generator.pushIndent(2)
    if extraDecl:
        generator.w(extraDecl)
    generator.w("unsigned idx;\n")
    generator.w("for (idx = 0; idx < %s; ++idx) {\n"%sfa.width)
    generator.pushIndent(2)
    generator.w(body)
    generator.popIndent(2)
    generator.w("}\n")
    generator.popIndent(2)
    generator.w("}\n")

def iterateOverVarArray(generator, sva, body, extraDecl=None):
    body = body.replace("ELEMENT", "TRUNNEL_DYNARRAY_GET(&obj->%s, idx)"%sva.c_name)
    generator.w("{\n")
    generator.pushIndent(2)
    if extraDecl:
        generator.w(extraDecl)
    generator.w("unsigned idx;\n")
    generator.w("for (idx = 0; idx < TRUNNEL_DYNARRAY_LEN(&obj->%s); ++idx) {\n"%sva.c_name)
    generator.pushIndent(2)
    generator.w(body)
    generator.popIndent(2)
    generator.w("}\n")
    generator.popIndent(2)
    generator.w("}\n")

class CheckFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("static const char *\n%s_check(const %s_t *obj)\n{\n"%(name,name))
        self.pushIndent(2)
        self.w('if (obj == NULL)\n  return "Object was NULL";\n')
        sd.visitChildren(self)
        self.w("return NULL;\n")
        self.popIndent(2)
        self.w("}\n\n")
    def visitSMInteger(self, smi):
        if smi.constraints is not None:
            v = "obj->%s"%smi.c_name
            expr = intConstraintExpression(v, smi.constraints.ranges)

            self.w(('if (! %s)\n'
                    '  return "Integer out of bounds";\n')%(expr))

    def visitSMFixedArray(self, sfa):
        if type(sfa.basetype) == str:
            body = ("if (NULL != (msg = %s_check(ELEMENT)))\n"
                    "  return msg;"%(sfa.basetype))
            iterateOverFixedArray(self, sfa, body,
                                  extraDecl='const char *msg;\n')

        elif str(sfa.basetype) == 'char':
            self.w('if (obj->%s[%s] != 0)\n'
                   '  return "String not terminated";\n'
                   %(sfa.c_name,sfa.width))

    def visitSMStruct(self, sms):
        self.w(("{\n"
                "  const char *msg;\n"
                "  if (NULL != (msg = %s_check(&obj->%s)))\n"
                "    return msg;\n"
                "}\n")%(
                    sms.structname, sms.c_name))
    def visitSMVarArray(self, sva):
        if type(sva.basetype) == str:
            body = ("if (NULL != (msg = %s_check(ELEMENT)))\n"
                    "  return msg;"%(sva.basetype))

            iterateOverVarArray(self, sva, body,
                                extraDecl='const char *msg;\n')

        if str(sva.basetype) != 'char':
            self.w(('if (TRUNNEL_DYNARRAY_LEN(&obj->%s) != obj->%s)\n'
                    '  return "Length mismatch for %s";\n')%(
                        sva.c_name, sva.widthfield, sva.name))


    def visitSMString(self, ss):
        self.w('if (NULL == obj->%s)\n  return "Missing %s";\n'%(ss.c_name, ss.c_name))

    def visitSMRemainder(self, smr):
        self.w('if (NULL == obj->%s)\n  return "Missing %s";\n'%(smr.c_name, smr.c_name))

    def visitSMUnion(self, smu):
        self.w('switch (obj->%s) {\n'%smu.tagfield)
        smu.visitChildren(self)
        self.w("}\n")

    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w,um)
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
    w("\n")
    if um.tagvalue == None:
        w("default:\n")
        return

    for lo, hi in um.tagvalue:
        if lo == hi:
            w("case %s:\n"%lo)
        else:
            for value in range(lo, hi+1):
                w("case %s:\n"%value)


def arrayIsBytes(arry):
    tp = arry.basetype
    if str(tp) == 'char':
        return True
    elif type(tp) == Grammar.IntType and tp.width == 8:
        return True
    else:
        return False

class EncodeFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)
        self.action = "Encode"

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.curStruct = sd
        self.w("ssize_t\n%s_encode(uint8_t *output, const size_t avail, const %s_t *obj)\n{\n"%(name,name))
        self.pushIndent(2)
        self.w('ssize_t result = 0;\n'
               'size_t written = 0;\n'
               'uint8_t *ptr = output;\n'
               'const char *msg;\n')
        self.w('\n')
        if sd.unionLengthFields:
            for m in sorted(sd.unionLengthFields.values()):
                self.w('uint8_t *backptr_%s = NULL;\n'%(m.c_name))
            self.w('\n')
        self.w(('if (NULL != (msg = %s_check(obj)))\n'
               '  goto check_failed;\n\n')%sd.name)
        self.needTruncated = False
        sd.visitChildren(self)

        self.w('\n'
               'return written;\n\n')

        self.popIndent(2)
        if self.needTruncated:
            self.w(" truncated:\n  result = -2;\n  goto fail;\n")
        self.w(" check_failed:\n  (void)msg;\n  result = -1;\n  goto fail;\n"
               " fail:\n  trunnel_assert(result < 0);\n  return result;\n")
        self.w("}\n\n")
        self.curStruct = None

    def visitSMInteger(self, smi):
        self.eltHeader(smi)
        if smi.c_name in self.curStruct.unionLengthFields:
            self.w('backptr_%s = ptr;\n'%(smi.c_name));
        self.w(self.encodeInteger(smi.inttype.width, "obj->%s"%(smi.c_name)))

    def encodeInteger(self, width, element):
        nbytes = width // 8
        hton = HTON_FN[width]
        self.needTruncated = True
        x = [
            'trunnel_assert(written <= avail);\n',
            ('if (avail - written < %s)\n'
            '  goto truncated;\n') % nbytes,
        'trunnel_set_uint%d(ptr, %s(%s));\n'%(width,hton,element),
        'written += %s; ptr += %s;\n' % (nbytes, nbytes) ]
        return "".join(x)

    def visitSMStruct(self, sms):
        self.eltHeader(sms)
        self.w(self.encodeStruct(sms.structname, "&obj->%s"%(sms.c_name)))

    def encodeStruct(self, structtype, element_pointer):
        return ("trunnel_assert(written <= avail);\n"
                "result = %s_encode(ptr, avail - written, %s);\n"
                "if (result < 0)\n"
                "  goto fail;\n"
                "written += result; ptr += result;\n")%(
                    structtype, element_pointer)

    def visitSMFixedArray(self, sfa):
        self.eltHeader(sfa)
        if arrayIsBytes(sfa):
            self.needTruncated = True
            if str(sfa.basetype) == 'char':
                self.w('trunnel_assert(written <= avail);\n')
                self.w('if (avail - written < %s)\n  goto truncated;\n'
                       %(sfa.width))
                self.w('{\n')
                self.pushIndent(2)
                self.w('size_t len = strlen(obj->%s);\n'
                       %(sfa.c_name))

                self.w('trunnel_assert(len <= %s);\n'%sfa.width)
                self.w('memcpy(ptr, obj->%s, len);\n'
                       %(sfa.c_name))
                self.w('memset(ptr + len, 0, %s - len);\n'%sfa.width)
                self.w('written += %s; ptr += %s;\n'%(sfa.width,sfa.width))
                self.popIndent(2)
                self.w('}\n')
            else:
                self.w('trunnel_assert(written <= avail);\n')
                self.w('if (avail - written < %s)\n  goto truncated;\n'
                   %(sfa.width))
                self.w('memcpy(ptr, obj->%s, %s);\n'
                       %(sfa.c_name,sfa.width))
                self.w('written += %s; ptr += %s;\n'%(sfa.width,sfa.width))
            return

        if type(sfa.basetype) == str:
            body = self.encodeStruct(sfa.basetype, "ELEMENT")
        else:
            body = self.encodeInteger(sfa.basetype.width, "ELEMENT")
        iterateOverFixedArray(self, sfa, body)

    def visitSMVarArray(self, sva):
        self.eltHeader(sva)
        if arrayIsBytes(sva):
            if str(sva.basetype) == 'char':
                arry = "obj->%s"%sva.c_name
            else:
                arry = "obj->%s.elts_"%sva.c_name
            self.needTruncated = True
            self.w('trunnel_assert(written <= avail);\n')
            self.w('if (avail - written < obj->%s) goto truncated;\n'
                   %(sva.widthfield))
            self.w('memcpy(ptr, %s, obj->%s);\n'
                   %(arry,sva.widthfield))
            self.w('written += obj->%s; ptr += obj->%s;\n'
                   %(sva.widthfield,sva.widthfield))
            return
        if type(sva.basetype) == str:
            body = self.encodeStruct(sva.basetype, "ELEMENT")
        else:
            body = self.encodeInteger(sva.basetype.width, "ELEMENT")
        iterateOverVarArray(self, sva, body)

    def visitSMString(self, ss):
        self.eltHeader(ss)
        self.needTruncated = True
        self.w('trunnel_assert(written <= avail);\n')
        self.w('{\n')
        self.pushIndent(2)
        self.w('size_t len = strlen(obj->%s);\n'%(ss.c_name))
        self.w('if (len >= avail - written)\n'
               '  goto truncated;\n')
        self.w('memcpy(ptr, obj->%s, len + 1);\n'%(ss.c_name))
        self.w('ptr += len + 1; written += len + 1;\n')
        self.popIndent(2)
        self.w('}\n')

    def visitSMRemainder(self, smr):
        self.eltHeader(smr)
        self.needTruncated = True
        self.w('trunnel_assert(written <= avail);\n')
        self.w(('if (obj->%s_len > avail - written)\n'
                '  goto truncated;\n')%(smr.c_name))
        self.w(('if (obj->%s_len)\n'
                '  memcpy(ptr, obj->%s, obj->%s_len);\n')
               %(smr.c_name, smr.c_name, smr.c_name))
        self.w('ptr += obj->%s_len; written += obj->%s_len;\n'%(smr.c_name, smr.c_name))

    def visitSMUnion(self, smu):
        self.eltHeader(smu)
        self.w('trunnel_assert(written <= avail);\n')
        if smu.lengthfield is not None:
            self.w("{\n")
            self.pushIndent(2)
            self.w("size_t written_before_union = written;\n")
        self.w('switch (obj->%s) {\n'%smu.tagfield)
        smu.visitChildren(self)
        self.w("}\n")

        if smu.lengthfield is not None:
            self.comment('Write the length field back to %s'%smu.lengthfield)
            m = smu.lengthfieldmember
            width = m.inttype.width
            hton = HTON_FN[width]
            self.w('trunnel_assert(written >= written_before_union);\n')
            self.w_('#if UINT%s_MAX < SIZE_MAX\n'%width)
            self.w(('if (written - written_before_union > UINT%s_MAX)\n'
                    '  goto check_failed;\n')%width)
            self.w_('#endif\n')
            self.w('trunnel_set_uint%d(backptr_%s, %s(written - written_before_union));\n'%(width,m.c_name,hton))
            self.popIndent(2)
            self.w("}\n")

    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w,um)
        self.pushIndent(2)
        um.visitChildren(self)
        self.w("break;\n")
        self.popIndent(2)
        self.popIndent(2)

    def visitSMFail(self, udf):
        self.w('trunnel_assert(0);\n');
    def visitSMIgnore(self, udi):
        pass
    def visitSMEos(self, eos):
        pass

def intConstraintExpression(v, ranges):
    tests = []
    for lo,hi in ranges:
        if lo == hi:
            tests.append('%s == %s'%(v, lo))
        else:
            tests.append('(%s >= %s && %s <= %s)'%(v,lo,v,hi))

    return "(%s)"%(" || ".join(tests))


class ParseFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)
        self.action = "Parse"

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("static ssize_t\n%s_parse_into(%s_t *obj, const uint8_t *input, const size_t len_in)\n{\n"%(name,name))
        self.pushIndent(2)
        self.w('const uint8_t *ptr = input;\n'
               'size_t remaining = len_in;\n'
               'ssize_t result = 0;\n\n')

        self.needOverflow = False
        self.needTruncated = False
        self.needAllocFailed = False
        sd.visitChildren(self)

        self.w('return len_in - remaining;\n\n')

        self.popIndent(2)
        if self.needOverflow:
            self.w(' overflow:\n  result = -1;\n  goto fail;\n')
        if self.needTruncated:
            self.w(' truncated:\n  result = -2;\n  goto fail;\n')
        if self.needAllocFailed:
            self.w(" trunnel_alloc_failed:\n  result = -1;\n  goto fail;\n")
        self.w(' fail:\n  if (result >= 0) result = -1;\n  return result;\n')
        self.w("}\n\n")

        self.w("ssize_t\n%s_parse(%s_t **output, const uint8_t *input, const size_t len_in)\n{\n"%(name,name))
        self.w('  ssize_t result;\n')
        self.w('  *output = %s_new();\n'%name)
        self.w('  result = %s_parse_into(*output, input, len_in);'%name)
        self.w('  if (result < 0) {\n'
               '    %s_free(*output);\n'
               '    *output = NULL;\n'
               '  }\n'
               '  return result;\n'
               '}\n'%(name))

    def visitSMInteger(self, smi):
        self.eltHeader(smi)
        v = "obj->%s" % (smi.c_name)
        self.parseInteger(smi.inttype.width, v)

        if smi.constraints is not None:
            expr = intConstraintExpression(v, smi.constraints.ranges)

            self.w(('if (! %s)\n'
                    '  goto fail;\n')%(expr))


    def parseInteger(self, width, element):
        nbytes = width // 8
        ntoh = NTOH_FN[width]
        self.needTruncated = True
        self.w('if (remaining < %s)\n  goto truncated;\n'%nbytes)
        self.w('%s = %s(trunnel_get_uint%d(ptr));\n'%(element, ntoh, width))
        self.w('remaining -= %s; ptr += %s;\n' % (nbytes, nbytes))


    def visitSMStruct(self, sms):
        self.eltHeader(sms)
        self.w(self.parseStruct(sms.structname, "&obj->%s"%(sms.c_name)))

    def parseStruct(self, structtype, element_pointer):
        return ("result = %s_parse_into(%s, ptr, remaining);\n"
                "if (result < 0)\n"
                "  goto fail;\n"
                "trunnel_assert((size_t)result <= remaining);\n"
                "remaining -= result; ptr += result;\n")%(
                    structtype, element_pointer)

    def parseStructInto(self, structtype, target_pointer):
        return ("result = %s_parse(&%s, ptr, remaining);\n"
                "if (result < 0)\n"
                "  goto fail;\n"
                "trunnel_assert((size_t)result <= remaining);\n"
                "remaining -= result; ptr += result;\n")%(
                    structtype, target_pointer)

    def visitSMFixedArray(self, sfa):
        self.eltHeader(sfa)
        if type(sfa.basetype) != str:
            self.needTruncated = True
            bytesPerElt = 1
            multiplier = ""
            if type(sfa.basetype) == Grammar.IntType:
                bytesPerElt = sfa.basetype.width // 8
                if bytesPerElt > 1:
                    multiplier = "%s * "%bytesPerElt
            self.w('if (remaining < (%s%s))\n  goto truncated;\n'%(multiplier, sfa.width))
            self.w('memcpy(obj->%s, ptr, %s%s);\n'%(sfa.c_name, multiplier, sfa.width))
            if type(sfa.basetype) == Grammar.IntType:
                self.w(('{\n'
                        '  unsigned idx;\n'
                        '  for (idx = 0; idx < %s; ++idx)\n'
                        '    obj->%s[idx] = %s(obj->%s[idx]);\n'
                        '}\n')%(sfa.width,
                                  sfa.c_name,
                                  NTOH_FN[sfa.basetype.width],
                                  sfa.c_name))
            self.w(('remaining -= %s%s; ptr += %s%s;\n')%(
                multiplier, sfa.width, multiplier, sfa.width))

            return

        else:
            iterateOverFixedArray(self, sfa,
                                  self.parseStructInto(sfa.basetype,
                                        "obj->%s[idx]"%(sfa.c_name)))

    def visitSMVarArray(self, sva):
        self.eltHeader(sva)
        # FFFF some of this is kinda cut-and-paste
        if arrayIsBytes(sva):
            if str(sva.basetype) == 'char':
                self.w_('#if SIZE_MAX <= UINT%d_MAX\n'%sva.widthfieldmember.inttype.width)
                self.w(('if (((size_t)obj->%s) > SIZE_MAX - 1)'
                        '  goto overflow;')%sva.widthfield)
                self.w_('#endif\n')
                plus1 = "+ 1"
                elt = "obj->%s"%sva.c_name
            else:
                elt = "obj->%s.elts_"%sva.c_name

            self.needTruncated = True
            self.w('if (remaining < obj->%s)\n  goto truncated;\n'%(
                sva.widthfield))
            self.needOverflow = True


            if str(sva.basetype) == 'char':
                self.w('if (NULL == (obj->%s = trunnel_malloc(((size_t)obj->%s) + 1)))\n  goto overflow;\n'%(
                    sva.c_name, sva.widthfield))
                self.w('obj->%s[obj->%s] = 0;\n'%(sva.c_name, sva.widthfield))
            else:
                self.w("TRUNNEL_DYNARRAY_EXPAND(uint8_t, &obj->%s, obj->%s);\n"
                       %(sva.c_name, sva.widthfield))
                self.w("obj->%s.n_ = obj->%s;"%(sva.c_name,sva.widthfield))

            self.w('memcpy(%s, ptr, obj->%s);\n'%(elt, sva.widthfield))

            self.w(('remaining -= obj->%s; ptr += obj->%s;\n')%(
                sva.widthfield, sva.widthfield))
            return

        else:
            self.needOverflow = True
            self.needAllocFailed = True

            if type(sva.basetype) == str:
                elttype = "%s_t *"%sva.basetype
            else:
                elttype = "uint%d_t"%sva.basetype.width

            self.w('TRUNNEL_DYNARRAY_EXPAND(%s, &obj->%s, obj->%s);\n'
                   %(elttype, sva.c_name, sva.widthfield))
            self.w(('{\n'
                    '  unsigned idx;\n'
                    '  %s elt;\n'
                    '  for (idx = 0; idx < obj->%s; ++idx) {\n')%(elttype,sva.widthfield))
            self.pushIndent(4)
            if type(sva.basetype) == str:
                self.w(self.parseStructInto(sva.basetype, "elt"))
            else:
                self.parseInteger(sva.basetype.width, "elt")

            self.w("TRUNNEL_DYNARRAY_ADD(%s, &obj->%s, elt);"%(elttype,sva.c_name))

            self.popIndent(4)
            self.w('  }\n'
                   '}\n')

    def visitSMString(self, ss):
        self.eltHeader(ss)
        self.needTruncated = True
        self.w('{\n')
        self.pushIndent(2)
        self.w('uint8_t *eos = (uint8_t*)memchr(ptr, 0, remaining);\n'
               'size_t memlen;\n')
        self.w('if (eos == NULL)\n'
               '  goto truncated;\n')
        self.w('trunnel_assert(eos >= ptr);\n')
        self.w('trunnel_assert((size_t)(eos - ptr) < SIZE_MAX - 1);\n')
        self.w('memlen = ((size_t)(eos - ptr)) + 1;\n')
        self.w('obj->%s = trunnel_malloc(memlen);\n'%(ss.c_name))
        self.w('memcpy(obj->%s, ptr, memlen);\n'%(ss.c_name))
        self.w('remaining -= memlen; ptr += memlen;\n')
        self.popIndent(2)
        self.w('}\n')

    def visitSMRemainder(self, smr):
        self.eltHeader(smr)
        self.w('obj->%s_len = remaining;\n'%smr.c_name)
        self.w('obj->%s = trunnel_malloc(remaining);\n'%(smr.c_name))
        self.w('memcpy(obj->%s, ptr, remaining);\n'%(smr.c_name))
        self.w('ptr += remaining; remaining = 0;\n')

    def visitSMUnion(self, smu):
        self.eltHeader(smu)
        if smu.lengthfield is not None:
            self.w('{\n')
            self.pushIndent(2)
            self.w('size_t remaining_after;\n')
            self.w('if (obj->%s > remaining)\n   goto truncated;\n'%smu.lengthfield)
            self.w('remaining_after = remaining - obj->%s;\n'%smu.lengthfield)
            self.w('remaining = obj->%s;\n'%smu.lengthfield)


        self.w('switch (obj->%s) {\n'%smu.tagfield)
        self.curunion = smu
        smu.visitChildren(self)
        self.w("}\n")
        if smu.lengthfield is not None:
            self.w('if (remaining != 0)\n'
                   '  goto fail;\n')
            self.w('remaining = remaining_after;\n')
            self.popIndent(2)
            self.w('}\n')


    def visitUnionMember(self, um):
        self.pushIndent(2)
        writeUnionMemberCaseLabel(self.w,um)
        self.pushIndent(2)
        um.visitChildren(self)
        self.w("break;\n")
        self.popIndent(2)
        self.popIndent(2)

    def visitSMEos(self, eos):
        self.w('if (remaining)\n  goto fail;\n')
    def visitSMFail(self, udf):
        self.w('goto fail;\n')
    def visitSMIgnore(self, udi):
        self.w('/* Skip to end of union */\n')
        self.w('ptr += remaining; remaining = 0;\n')

HEADER_BOILERPLATE = """
/* %(fname)s -- generated by trunnel. */
#ifndef %(macro)s
#define %(macro)s

#include <stdint.h>
#include "trunnel.h"

"""

HEADER_FOOTER = """

#endif
"""

MODULE_BOILERPLATE = """
/* %(c_fname)s -- generated by trunnel. */
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <arpa/inet.h>
#include "trunnel-impl.h"
#include "%(h_fname)s"

#define trunnel_malloc(x) (malloc((x)))
#define trunnel_free_(x) (free(x))
#define trunnel_free(x) (free(x))
#define trunnel_calloc(a,b) (calloc(a,b))
#define trunnel_assert(x) assert(x)
#define trunnel_abort() abort()

/* XXXX stick this in a file or something */
static void *trunnel_reallocarray(void *a, size_t x, size_t y)
{
   if (x > SIZE_MAX / y)
     return NULL;
   return realloc(a, x * y);
}

static void trunnel_set_uint32(void *p, uint32_t v) {
  memcpy(p, &v, 4);
}
static void trunnel_set_uint16(void *p, uint16_t v) {
  memcpy(p, &v, 2);
}
static void trunnel_set_uint8(void *p, uint8_t v) {
  memcpy(p, &v, 1);
}

static uint32_t trunnel_get_uint32(const void *p) {
  uint32_t x;
  memcpy(&x, p, 4);
  return x;
}
static uint16_t trunnel_get_uint16(const void *p) {
  uint16_t x;
  memcpy(&x, p, 2);
  return x;
}
static uint8_t trunnel_get_uint8(const void *p) {
  return *(const uint8_t*)p;
}
static uint64_t trunnel_get_uint64(const void *p) {
  uint64_t x;
  memcpy(&x, p, 8);
  return x;
}

static void trunnel_set_uint64(void *p, uint64_t v) {
  memcpy(p, &v, 8);
}

static uint64_t trunnel_htonll(uint64_t a)
{
#if BYTE_ORDER == BIG_ENDIAN
  return a;
#else
  return htonl(a>>32) | (((uint64_t)htonl(a))<<32);
#endif
}
static uint64_t trunnel_ntohll(uint64_t a)
{
  return trunnel_htonll(a);
}
"""


if __name__ == '__main__':
    import sys
    import os

    if len(sys.argv) != 2:
        sys.stderr.write("Syntax: CodeGen.py <fname>\n")
        sys.exit(1)

    input_fname = sys.argv[1]
    basename = input_fname
    if basename.endswith(".trunnel"):
        basename = basename[:-len(".trunnel")]

    c_fname = basename + ".c"
    h_fname = basename + ".h"

    inp = open(input_fname, 'r')
    t = Grammar.Lexer().tokenize(inp.read())
    inp.close()
    parsed = Grammar.Parser().parse(t)
    c = Checker()
    c.visit(parsed)

    Annotator().visit(parsed)

    out_h = open(h_fname, 'w')
    macro = "TRUNNEL_"+os.path.split(h_fname)[1].upper().replace(".","_")
    out_h.write(HEADER_BOILERPLATE % {'macro':macro, 'fname':h_fname})
    DeclarationGenerationVisitor(c.sortedStructs, out_h).visit(parsed)
    PrototypeGenerationVisitor(c.sortedStructs, out_h).visit(parsed)
    out_h.write(HEADER_FOOTER)
    out_h.close()

    out_c = open(c_fname, 'w')
    out_c.write(MODULE_BOILERPLATE % {'h_fname':os.path.split(h_fname)[1], 'c_fname':c_fname})
    PrototypeGenerationVisitor(c.sortedStructs, out_c, static=True).visit(parsed)
    CodeGenerationVisitor(c.sortedStructs, out_c).visit(parsed)
    out_c.close()

