
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
            raise CheckError("duplicate field %s.%s"%(self.structName,sms.name))

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

      u8 tag_field;
      union union_field[tag_field] {
         3 : struct name3 v1 ;
         4 : struct name4 v2 ;
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
   }

"""


t = Grammar.Lexer().tokenize(x)
parsed = Grammar.Parser().parse(t)
c = Checker()
c.visit(parsed)




