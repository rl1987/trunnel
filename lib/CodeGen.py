
import Grammar

class ASTVisitor(object):
    def __init__(self):
        pass
    def visit(self, ast, *args):
        name = "visit" + ast.__class__.__name__
        method = getattr(self, name, self.visit_other)
        return method(ast, *args)

    def visit_other(self, ast, *args):
        raise NotImplemented(visit + ast.__class__.__name__)

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
    64 : 'htonll'
}
NTOH_FN = {
    8 : '',
    16 : 'ntohs',
    32 : 'ntohl',
    64 : 'ntohll'
}


class Checker(ASTVisitor):
    def __init__(self):
        ASTVisitor.__init__(self)
        self.structNames = set()
        self.constNames = set()
        self.constValues = {}
        self.structFieldNames = None
        self.structUses = {}

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
            for structname, uses in self.structUses.iteritems():
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
        for structname, uses in self.structUses.iteritems():
            if structname in uses:
                raise CheckError("There is a cycle in the %s structure"%structname)

        # Perform a topological sort.
        sorted_structs = []
        removed = set()
        while len(self.structUses):
            removed_this_time = []
            for structname, uses in self.structUses.iteritems():
                uses.difference_update(removed)
                if len(uses) == 0:
                    sorted_structs.append(structname)
                    removed.add(structname)
                    removed_this_time.append(structname)
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

    def visitSMInteger(self, smi):
        if smi.name in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,smi.name))

        self.structFieldNames.add(smi.name)
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
        if sms.name in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,sms.name))

        self.structFieldNames.add(sms.name)

        if sms.structname not in self.structNames:
            raise CheckError("Unrecognized structure %s used in %s"%(
                sms.structname,self.structName))

        self.structUses[self.structName].add(sms.structname)

    def visitSMFixedArray(self, sfa):
        if sfa.name in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,sfa.name))

        self.structFieldNames.add(sfa.name)

        if type(sfa.width) == str:
            self.expandConstant(sfa.width)

        if type(sfa.basetype) == str:
            if sfa.basetype not in self.structNames:
                raise CheckError("Unrecognized structure %s used in %s.%s"%(
                    sfa.basetype,self.structName,sfa.name))

    def visitSMVarArray(self, sva):
        if sva.name in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,sfa.name))

        self.structFieldNames.add(sva.name)

        self.checkIntField(sva.widthfield, "length", "%s.%s"%
                           (self.structName,sva.name))

        if type(sva.basetype) == str:
            if sva.basetype not in self.structNames:
                raise CheckError("Unrecognized structure %s used in %s.%s"%(
                    sva.basetype,self.structName,sva.name))

    def visitSMString(self, sms):
        if sms.name in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,sms.name))

        self.structFieldNames.add(sms.name)

    def visitSMUnion(self, smu):
        if smu.name in self.structFieldNames:
            raise CheckError("duplicate field %s.%s"%(self.structName,smu.name))

        self.structFieldNames.add(smu.name)

        self.checkIntField(smu.tagfield, "tag", "%s.%s"%
                           (self.structName,smu.name))
        if smu.lengthfield is not None:
            self.checkIntField(smu.lengthfield, "length", "%s.%s"%
                               (self.structName,smu.name))

        self.unionHasLength = smu.lengthfield is not None
        self.unionName = smu.name
        self.unionMatching = []
        self.unionTagMax = TYPE_MAXIMA[self.structIntFieldNames[smu.tagfield]]
        self.containing = "%s.%s"%(self.structName,smu.name)
        smu.visitChildren(self)

        self.unionMatching.sort()
        lasthi = -1
        for lo,hi in self.unionMatching:
            if lo <= lasthi:
                raise CheckError("Duplicate tag values in %s.%s"%
                                 (self.structName,smu.name))
            assert hi >= lo
            lasthi = hi

        self.unionName = None
        self.unionMatching = None
        self.unionTagMax = None
        self.containing = None

        # Check union default FFFF


    def visitUnionMember(self, um):
        self.checkIntegerList(um.tagvalue, self.unionTagMax, self.unionMatching)

        if um.allow_extra and not self.unionHasLength:
            raise CheckError("'...' found in union %s without a length field"%
                             self.containing)

        # save list of int fields so that other declarations can't
        # depend on integers declared here.
        saved = self.structIntFieldNames.copy()
        self.visit(um.decl)
        self.structIntFieldNames = saved


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
            print "<%s>"%self.constValues
            raise CheckError("Unrecognized constant %s in %s"%(
                const, self.containing))

    def checkIntField(self, fieldname, ftype, inside):
        if fieldname not in self.structFieldNames:
            raise CheckError("Unrecognized %s field %s for %s"%(
                ftype,fieldname,inside))

        if fieldname not in self.structIntFieldNames:
            raise CheckError("Non-integer %s field %s for %s"%(
                ftype,fieldname,inside))


class DeclarationGenerationVisitor(ASTVisitor):
    def __init__(self, sort_order, f):
        self.w = f.write
        self.sort_order = sort_order
        self.fieldPrefix = ""

    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)

    def visitConstDecl(self, cd):
        self.w("#define %s %s\n"%(cd.name,cd.value.value))

    def visitStructDecl(self, sd):
        self.w("typedef struct %s_st {\n"%sd.name)
        sd.visitChildren(self)
        self.w("} %s_t;\n\n"%sd.name);

    def visitSMInteger(self, smi):
        self.w("  uint%d_t %s%s;\n"%(smi.inttype.width,self.fieldPrefix,smi.name))

    def visitSMStruct(self, sms):
        self.w("  %s_t %s%s;\n"%(sms.structname,self.fieldPrefix,sms.name))

    def visitSMFixedArray(self, sfa):
        if type(sfa.basetype) == str:
            self.w("  %s_t %s%s[%s];\n"%(sfa.basetype, self.fieldPrefix, sfa.name, sfa.width))
        elif str(sfa.basetype) == "char":
            self.w("  char %s%s[%s+1];\n"%(self.fieldPrefix, sfa.name, sfa.width))
        else:
            self.w("  uint%d_t %s%s[%s];\n"%(sfa.basetype.width, self.fieldPrefix,sfa.name, sfa.width))

    def visitSMVarArray(self, sva):
        if type(sva.basetype) == str:
            self.w("  %s_t *%s%s;\n"%(sva.basetype, self.fieldPrefix, sva.name))
        elif str(sva.basetype) == "char":
            self.w("  char *%s%s;\n"%(self.fieldPrefix, sva.name))
        else:
            self.w("  uint%d_t *%s%s;\n"%(sva.basetype.width, self.fieldPrefix, sva.name))

    def visitSMString(self, ss):
        self.w("  char *%s%s;\n"%(self.fieldPrefix,ss.name))

    def visitSMUnion(self, smu):
        self.fieldPrefix = smu.name + "_"
        smu.visitChildren(self)
        if isinstance(smu.default, Grammar.UDStore):
            self.w("  uint8_t *%s%s;"%(self.fieldPrefix,smu.default.fieldname))
        self.fieldPrefix = ""

    def visitUnionMember(self, um):
        um.visitChildren(self)


class PrototypeGenerationVisitor(ASTVisitor):
    def __init__(self, sort_order, f):
        self.w = f.write
        self.sort_order = sort_order
    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)
    def visitConstDecl(self, cd):
        pass
    def visitStructDecl(self, sd):
        name = sd.name
        self.w("%s_t *%s_new(void);\n"%(name,name))
        self.w("void %s_free(%s_t *victim);\n"%(name, name))
        self.w("ssize_t %s_parse(%s_t **output, const uint8_t *input, const size_t len_in);\n"%(name,name))
        self.w("static ssize_t %s_parse_into(%s_t *obj, const uint8_t *input, const size_t len_in);\n"%(name,name))
        self.w("ssize_t %s_parse(%s_t **obj, const uint8_t *input, const size_t len_in);\n"%(name,name))
        self.w("ssize_t %s_encode(uint8_t *output, const size_t avail, const %s_t *input);\n\n"%(name,name))


class CodeGenerationVisitor(ASTVisitor):
    def __init__(self, sort_order, f):
        self.w = f.write
        self.sort_order = sort_order
        self.generators = [ NewFnGenerator, FreeFnGenerator, CheckFnGenerator,
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
        self.w("  return tor_malloc_zero(sizeof(%s_t));\n"%name)
        self.w("}\n\n");

class FreeFnGenerator(ASTVisitor):
    def __init__(self, writefn):
        self.w = writefn
        self.prefix = ""
    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("static void\n%s_clear(%s_t *obj)\n{\n"%(name,name))
        self.w("  if (obj == NULL)\n    return;\n")
        sd.visitChildren(self)
        self.w("}\n\n")
        self.w("void\n%s_free(%s_t *obj)\n{\n"%(name,name))
        self.w("  if (obj == NULL)\n    return;\n")
        self.w("  %s_clear(obj);\n"%name)
        self.w("  tor_free_(obj);\n")
        self.w("}\n\n");
    def visitSMInteger(self, smi):
        pass
    def visitSMFixedArray(self, sfa):
        pass
    def visitSMStruct(self, sms):
        self.w("  %s_clear(&obj->%s%s);\n"%(sms.structname, self.prefix, sms.name))
    def visitSMVarArray(self, sva):
        self.w("  tor_free(obj->%s%s);\n"%(self.prefix,sva.name))
    def visitSMString(self, ss):
        self.w("  tor_free(obj->%s%s);\n"%(self.prefix,ss.name))
    def visitSMUnion(self, smu):
        self.prefix = smu.name+"_"
        smu.visitChildren(self)
        if isinstance(smu.default, Grammar.UDStore):
            self.w("  tor_free(obj->%s%s);\n"%(self.prefix,smu.default.fieldname))
        self.prefix = ""
    def visitUnionMember(self, um):
        um.visitChildren(self)

class IndentingGenerator(ASTVisitor):
    def __init__(self, writefn):
        self.w_ = writefn
        self.indent = ""
    def w(self, string):
        lines = string.split("\n")
        if lines[-1] == "":
            del lines[-1]
        for line in lines:
            if line == "":
                continue
            self.w_("%s%s\n"%(self.indent, line))

class CheckFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)
        self.prefix = ""

    def visit_other(self, x):
        print "You haven't implemented visit_%s in %s"%(x.__class__.__name__,
                                                        self.__class__.__name__)
    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("static const char *\n%s_check(const %s_t *obj)\n{\n"%(name,name))
        self.w('  if (obj == NULL)\n    return "Object was NULL";\n')
        sd.visitChildren(self)
        self.w("  return NULL;\n}\n\n")
    def visitSMInteger(self, smi):
        pass
    def visitSMFixedArray(self, sfa):
        if type(sfa.basetype) == str:
            self.checkStructArray(sfa.basetype,
                    "&obj->%s%s[idx]"%(self.prefix,sfa.name), sfa.width)
        elif str(sfa.basetype) == 'char':
            self.w('  if (obj->%s%s[%s] != 0)'
                   'return "String not terminated";\n'
                   %(self.prefix,sfa.name,sfa.width))

    def visitSMStruct(self, sms):
        self.w(("  {\n    const char *msg;\n"
                "    if (NULL != (msg = %s_check(&obj->%s%s)))\n"
                "      return msg;\n  }\n")%(
                    sms.structname, self.prefix, sms.name))
    def visitSMVarArray(self, sva):
        self.w('  if (NULL == obj->%s%s)\n    return "Missing %s%s";\n'%(self.prefix,sva.name,self.prefix,sva.name))
        if type(sva.basetype) == str:
            self.checkStructArray(sva.basetype, "&obj->%s%s[idx]"%(self.prefix,sva.name), "obj->%s"%sva.widthfield)

    def checkStructArray(self, structtype, element, num_items):
        self.w(('  {\n'
                '    unsigned idx;\n'
                '    const char *msg;\n'
                '    for (idx = 0; idx < %s; ++idx) {\n'
                '      if (NULL != (msg = %s_check(%s)))\n'
                '        return msg;\n'
                '    }\n'
                '  }\n') %(
                    num_items, structtype, element))

    def visitSMString(self, ss):
        self.w('  if (NULL == obj->%s%s)\n    return "Missing %s%s";\n'%(self.prefix,ss.name,self.prefix,ss.name))
    def visitSMUnion(self, smu):
        self.prefix = smu.name+"_"
        self.w('  switch (obj->%s) {\n'%smu.tagfield)
        smu.visitChildren(self)
        self.visit(smu.default)

        self.w("  }\n")
        self.prefix = ""

    def visitUnionMember(self, um):
        writeUnionMemberCaseLabel(self.w,um)
        self.indent = "    "
        um.visitChildren(self)
        self.indent = ""
        self.w("      break;\n")

    def visitUDStore(self, uds):
        self.w(('    default:\n  if (NULL == obj->%s%s)\n'
                '    return "Missing %s%s";\n    break;\n')%(
                    self.prefix,uds.fieldname,
                    self.prefix,uds.fieldname))
    def visitUDFail(self, udf):
        self.w('    default:\n      return "Bad tag for union";\n')
    def visitUDIgnore(self, udi):
        pass

def writeUnionMemberCaseLabel(w, um):
    for lo, hi in um.tagvalue:
        if lo == hi:
            w("    case %s:\n"%lo)
        else:
            for value in range(lo, hi+1):
                w("    case %s:\n"%value)


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
        self.prefix = ""

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("ssize_t\n%s_encode(uint8_t *output, const size_t avail, const %s_t *obj)\n{\n"%(name,name))
        self.w('  ssize_t result = 0;\n  size_t written = 0;\n  uint8_t *ptr = output;\n  const char *msg;\n')
        self.w('\n')
        self.w('  if (NULL != (msg = %s_check(obj)))\n    goto check_failed;\n\n'%sd.name)
        self.needTruncated = False
        sd.visitChildren(self)

        self.w('\n  return written;\n\n')

        if self.needTruncated:
            self.w(" truncated:\n  result = -2;\n  goto fail;\n")
        self.w(" check_failed:\n  (void)msg;\n  result = -1;\n  goto fail;\n"
               " fail:\n  tor_assert(result < 0);\n  return result;\n"
               "}\n\n")
    def visitSMInteger(self, smi):
        self.encodeInteger(smi.inttype.width, "obj->%s%s"%(self.prefix,smi.name))

    def encodeInteger(self, width, element):
        nbytes = width // 8
        hton = HTON_FN[width]
        self.needTruncated = True
        self.w('  tor_assert(written <= avail);\n');
        self.w('  if (avail - written < %s) goto truncated;\n' % nbytes)
        self.w('  set_uint%d(ptr, %s(%s));\n'%(width,hton,element))
        self.w('  written += %s; ptr += %s;\n' % (nbytes, nbytes))

    def visitSMStruct(self, sms):
        self.encodeStruct(sms.structname, "&obj->%s%s"%(self.prefix,sms.name))
    def encodeStruct(self, structtype, element_pointer):
        self.w('  tor_assert(written <= avail);\n');
        self.w(("  result = %s_encode(ptr, avail - written, %s);\n"
                "  if (result < 0) goto fail;\n"
                "  written += result; ptr += result;\n")%(
                    structtype, element_pointer))
    def visitSMFixedArray(self, sfa):
        if arrayIsBytes(sfa):
            self.needTruncated = True
            if str(sfa.basetype) == 'char':
                self.w('  tor_assert(written <= avail);\n')
                self.w('  if (avail - written < %s) goto truncated;\n'
                       %(sfa.width))
                self.w('  {\n    size_t len = strlen(obj->%s%s);\n'
                       %(self.prefix,sfa.name))

                self.w('    tor_assert(len <= %s);\n'%sfa.width)
                self.w('    memcpy(ptr, obj->%s%s, len);\n'
                       %(self.prefix,sfa.name))
                self.w('    memset(ptr + len, 0, %s - len);\n'%sfa.width)
                self.w('    written += %s; ptr += %s;\n'%(sfa.width,sfa.width))
                self.w('  }\n')
            else:
                self.w('  tor_assert(written <= avail);\n')
                self.w('  if (avail - written < %s) goto truncated;\n'
                   %(sfa.width))
                self.w('  memcpy(ptr, obj->%s%s, %s);\n'
                       %(self.prefix,sfa.name,sfa.width))
                self.w('  written += %s; ptr += %s;\n'%(sfa.width,sfa.width))
            return

        self.w('  {\n    unsigned idx;\n    size_t len = %s;\n    for (idx = 0; idx < len; ++idx) {\n'%sfa.width)
        self.encodeArrayBody(sfa)
        self.w('    }\n  }\n')

    def visitSMVarArray(self, sva):
        if arrayIsBytes(sva):
            self.needTruncated = True
            self.w('  tor_assert(written <= avail);\n')
            self.w('  if (avail - written < obj->%s) goto truncated;\n'
                   %(sva.widthfield))
            self.w('  memcpy(ptr, obj->%s%s, obj->%s);\n'
                   %(self.prefix,sva.name,sva.widthfield))
            self.w('  written += obj->%s; ptr += obj->%s;\n'
                   %(sva.widthfield,sva.widthfield))
            return

        self.w('  {\n    unsigned idx;\n    size_t len = obj->%s%s;\n    for (idx = 0; idx < len; ++idx) {\n'%(self.prefix,sva.widthfield))
        self.encodeArrayBody(sva)
        self.w('    }\n  }\n')

    def encodeArrayBody(self, arry):
        oldIndent = self.indent
        self.indent += "    "
        if type(arry.basetype) == str:
            self.encodeStruct(arry.basetype, "&obj->%s%s[idx]"%(self.prefix,arry.name))
        else:
            assert type(arry.basetype) == Grammar.IntType
            # FFFF memcpy, then byteswap ?
            self.encodeInteger(arry.basetype.width, "obj->%s%s[idx]"%(self.prefix,arry.name))
        self.indent = oldIndent
    def visitSMString(self, ss):
        self.needTruncated = True
        self.w('  tor_assert(written <= avail);\n')
        self.w('  {\n    size_t len = strlen(obj->%s%s);\n'%(self.prefix, ss.name))
        self.w('    if (len >= avail - written) goto truncated;\n');
        self.w('    memcpy(ptr, obj->%s%s, len + 1);\n'%(self.prefix, ss.name))
        self.w('    ptr += len + 1; written += len + 1;\n  }\n')


    def visitSMUnion(self, smu):
        self.prefix = smu.name+"_"
        if smu.lengthfield is not None:
            self.w('  tor_assert(written <= avail);\n')
            self.w('  {\n    size_t written_at_end;\n')
            self.w('    if (obj->%s > written - avail) goto truncated;\n'%smu.lengthfield)
            self.w('    written_at_end = written + obj->%s;\n'%smu.lengthfield)
            self.indent += "  "
        self.w('  switch (obj->%s) {\n'%smu.tagfield)
        smu.visitChildren(self)
        self.visit(smu.default)
        self.w("  }\n")
        if smu.lengthfield is not None:
            self.indent = self.indent[:-2]
            self.w('    if (written != written_at_end) goto fail;\n')
            self.w('  }\n')
        self.prefix = ""

    def visitUnionMember(self, um):
        writeUnionMemberCaseLabel(self.w,um)
        self.indent = "    "
        um.visitChildren(self)
        self.indent = ""
        if um.allow_extra:
            self.w('  if (written != written_at_end) {\n'
                   '    tor_assert(written < written_at_end);\n'
                   '    memset(ptr, 0, written_at_end - written);\n'
                   '    ptr += (written_at_end - written);\n'
                   '    written = written_at_end;\n'
                   '  }\n')
        self.w("      break;\n")

    def visitUDStore(self, uds):
        # FFFF can this be done safely?
        self.w('    default:\n      goto fail;\n')
    def visitUDFail(self, udf):
        self.w('    default: tor_assert(0);');
    def visitUDIgnore(self, udi):
        pass


class ParseFnGenerator(IndentingGenerator):
    def __init__(self, writefn):
        IndentingGenerator.__init__(self, writefn)
        self.prefix = ""

    def visitStructDecl(self, sd):
        self.structName = name = sd.name
        self.w("static ssize_t\n%s_parse_into(%s_t *obj, const uint8_t *input, const size_t len_in)\n{\n"%(name,name))
        self.w('  const uint8_t *ptr = input;\n  size_t remaining = len_in;\n'
                '  ssize_t result = 0;\n\n')

        self.needOverflow = False
        self.needTruncated = False
        sd.visitChildren(self)

        if sd.eos:
            self.w('  if (remaining) goto fail;')

        self.w('  return len_in - remaining;\n\n')
        if self.needOverflow:
            self.w(' overflow:\n  result = -1;\n  goto fail;\n')
        if self.needTruncated:
            self.w(' truncated:\n  result = -2;\n  goto fail;\n')
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
        self.parseInteger(smi.inttype.width, "obj->%s%s"%(self.prefix,smi.name))

    def parseInteger(self, width, element):
        nbytes = width // 8
        ntoh = NTOH_FN[width]
        self.needTruncated = True
        self.w('  if (remaining < %s) goto truncated;\n'%nbytes)
        self.w('  %s = %s(get_uint%d(ptr));\n'%(element, ntoh, width))
        self.w('  remaining -= %s; ptr += %s;\n' % (nbytes, nbytes))

    def visitSMStruct(self, sms):
        self.parseStruct(sms.structname, "&obj->%s%s"%(self.prefix,sms.name))
    def parseStruct(self, structtype, element_pointer):
        self.w(("  result = %s_parse_into(%s, ptr, remaining);\n"
                "  if (result < 0) goto fail;\n"
                "  tor_assert((size_t)result <= remaining);"
                "  remaining -= result; ptr += result;\n")%(
                    structtype, element_pointer))
    def visitSMFixedArray(self, sfa):
        if type(sfa.basetype) != str:
            self.needTruncated = True
            bytesPerElt = 1
            multiplier = ""
            if type(sfa.basetype) == Grammar.IntType:
                bytesPerElt = sfa.basetype.width // 8
                if bytesPerElt > 1:
                    multiplier = "%s * "%bytesPerElt
            self.w('  if (remaining < (%s%s)) goto truncated;\n'%(multiplier, sfa.width))
            self.w('  memcpy(obj->%s%s, ptr, %s%s);\n'%(self.prefix, sfa.name , multiplier, sfa.width))
            if type(sfa.basetype) == Grammar.IntType:
                self.w(('  {\n    unsigned idx;\n'
                        '    for (idx = 0; idx < %s; ++idx)\n'
                        '      obj->%s%s[idx] = %s(obj->%s%s[idx]);\n'
                        '  }\n')%(sfa.width,
                                  self.prefix,sfa.name,
                                  NTOH_FN[sfa.basetype.width],
                                  self.prefix,sfa.name))
            self.w(('  remaining -= %s%s; ptr += %s%s;\n')%(
                multiplier, sfa.width, multiplier, sfa.width))

            return

        else:
            self.w('  {\n    unsigned idx;\n    for (idx = 0; idx < %s; ++idx) {\n'%sfa.width)
            self.parseStruct(sfa.basetype, "&obj->%s%s[idx]"%(self.prefix,sfa.name))
            self.w('    }\n  }\n')

    def visitSMVarArray(self, sva):
        # FFFF some of this is kinda cut-and-paste
        if type(sva.basetype) != str:
            self.needTruncated = True
            bytesPerElt = 1
            divisor = multiplier = ""
            if type(sva.basetype) == Grammar.IntType:
                bytesPerElt = sva.basetype.width // 8
                if bytesPerElt > 1:
                    divisor = " / %s"%bytesPerElt
                    multiplier = "((size_t)%s) * "%bytesPerElt

            self.w('  if (remaining%s < obj->%s) goto truncated;\n'%(
                divisor, sva.widthfield))

            self.needOverflow = True
            self.w('  if (NULL == (tor_calloc(obj->%s, %s))) goto overflow;\n'%(
                sva.widthfield, bytesPerElt))

            self.w(' memcpy(obj->%s%s, ptr, %sobj->%s);\n'%(self.prefix, sva.name , multiplier, sva.widthfield))
            if type(sva.basetype) == Grammar.IntType:
                self.w(('  {\n    unsigned idx;\n'
                        '    for (idx = 0; idx < obj->%s; ++idx)\n'
                        '      obj->%s%s[idx] = %s(obj->%s%s[idx]);\n'
                        '  }\n')%(sva.widthfield,
                                  self.prefix,sva.name,
                                  NTOH_FN[sva.basetype.width],
                                  self.prefix,sva.name))
            self.w(('  remaining -= %sobj->%s; ptr += %sobj->%s;\n')%(
                multiplier, sva.widthfield, multiplier, sva.widthfield))

            return

        else:
            self.needOverflow = True
            self.w('  if (NULL == (tor_calloc(obj->%s, sizeof(%s_t)))) goto overflow;\n'%(
                sva.widthfield, sva.basetype))

            self.w('  {\n    unsigned idx;\n    for (idx = 0; idx < obj->%s; ++idx) {\n'%sva.widthfield)
            self.parseStruct(sva.basetype, "&obj->%s%s[idx]"%(self.prefix,sva.name))
            self.w('    }\n  }\n')


    def visitSMString(self, ss):
        self.needTruncated = True
        self.w('  {\n    uint8_t *eos = (uint8_t*)memchr(ptr, 0, remaining)\n;'
               '    size_t memlen;\n')
        self.w('    if (eos == NULL) goto truncated;\n')
        self.w('    tor_assert(eos >= ptr);\n')
        self.w('    tor_assert((size_t)(eos - ptr) < SIZE_MAX - 1);\n')
        self.w('    memlen = ((size_t)(eos - ptr)) + 1;\n')
        self.w('    obj->%s%s = tor_malloc(memlen);\n'%(self.prefix,ss.name))
        self.w('    memcpy(obj->%s%s, ptr, memlen);\n'%(self.prefix,ss.name))
        self.w('    remaining -= memlen; ptr += memlen;\n')
        self.w('  }\n')

    def visitSMUnion(self, smu):
        self.prefix = smu.name+"_"
        if smu.lengthfield is not None:
            self.w('  {\n    size_t remaining_at_end;\n')
            self.w('    if (obj->%s > remaining) goto truncated;\n'%smu.lengthfield)
            self.w('    remaining_at_end = remaining - obj->%s;\n'%smu.lengthfield)
            self.indent += '  '

        self.w('  switch (obj->%s) {\n'%smu.tagfield)
        self.curunion = smu
        smu.visitChildren(self)
        self.visit(smu.default)
        self.w("  }\n")
        if smu.lengthfield is not None:
            self.indent = self.indent[:-2]
            self.w('  if (remaining != remaining_at_end) goto fail;\n  }\n')

        self.prefix = ""

    def visitUnionMember(self, um):
        writeUnionMemberCaseLabel(self.w,um)
        self.indent = "    "
        um.visitChildren(self)
        self.indent = ""
        if um.allow_extra:
            self.w('  if (remaining > remaining_at_end)\n'
                   '    remaining = remaining_at_end;\n')
        self.w("      break;\n")

    def visitUDStore(self, uds):
        lfield = self.curunion.lengthfield
        self.w('    default: {\n')
        self.w('      obj->%s%s = tor_malloc(obj->%s);\n'
               %(self.prefix,uds.fieldname,lfield))
        self.w('      memcpy(obj->%s%s, ptr, obj->%s);\n'
               %(self.prefix,uds.fieldname,lfield))
        self.w('      remaining -= obj->%s; ptr += obj->%s;\n'%(lfield,lfield))
        self.w('    }\n')
        self.w('    break;\n')

    def visitUDFail(self, udf):
        self.w('    default:\n      goto fail;')
    def visitUDIgnore(self, udi):
        pass


x = """const X = 20;
   // Assume these have real definitions.
   struct name2 { u8 foo; }
   struct name3 { u8 foo; }
   struct name4 { u8 foo; }
   struct xx { u8 foo; }
   struct yy { u8 foo; struct xx zz; }
   struct zz { struct yy zz; }

   const TYPE1 = 1;
   const TYPE2 = 2;
   const TYPE3 = 3;

   struct name {
      u8 thing1 IN [0..20];
      u16 thing2;


      u8 thing_x IN [TYPE1, TYPE2, TYPE3];

      u8 thing3[20];
      u32 thing4[X];

      struct name2 thing5;

      struct name2 thing6[2];

      nulterm thing7;

      u8 count;
      struct name2 counted[count];

      u8 count2;
      char string[count2];
      char buf[10];

      u16 short_list1[20];
      u16 short_list2[count2];

      u8 tag_field;
      union union_field[tag_field] {
         3 : struct name3 v1;
         4 : struct name4 v2;
         X : u32 number;
         5 : u8 stuff[10];
         6 : nulterm a_string;
         default : fail;
      };

      eos;
   }


   struct namex {
       u8 tag;
       u8 length;

       union fred[tag] WITH LENGTH length {
           4: struct xx field1;
           5: struct yy field2;
           default: ignore;
       };

       union alice[tag] WITH LENGTH length {
           5: struct yy field3 ...;
           default: u8 junk[];
       };

   }

"""

t = Grammar.Lexer().tokenize(x)
parsed = Grammar.Parser().parse(t)
c = Checker()
c.visit(parsed)

ff = open("xyzzy.c", 'w')
ff.write("""#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <stdint.h>

#define tor_malloc(x) (malloc((x)))
#define tor_malloc_zero(x) (calloc((x),1))
#define tor_free_(x) (free(x))
#define tor_free(x) (free(x))
#define tor_calloc(a,b) (calloc(a,b))
#define tor_assert(x) assert(x)
static void set_uint32(void *p, uint32_t v) {
  memcpy(p, &v, 4);
}
static void set_uint16(void *p, uint16_t v) {
  memcpy(p, &v, 2);
}
static void set_uint8(void *p, uint8_t v) {
  memcpy(p, &v, 1);
}

static uint32_t get_uint32(const void *p) {
  uint32_t x;
  memcpy(&x, p, 4);
  return x;
}
static uint16_t get_uint16(const void *p) {
  uint16_t x;
  memcpy(&x, p, 2);
  return x;
}
static uint8_t get_uint8(const void *p) {
  return *(const uint8_t*)p;
}

#if 0
static void set_uint64(void *p, uint64_t v) {
  memcpy(p, &v, 8);
}
#endif


""")
DeclarationGenerationVisitor(c.sortedStructs, ff).visit(parsed)
PrototypeGenerationVisitor(c.sortedStructs, ff).visit(parsed)
ff.write("\n\n\n")
CodeGenerationVisitor(c.sortedStructs, ff).visit(parsed)
ff.close()
