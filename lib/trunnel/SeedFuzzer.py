#!/usr/bin/python
"""Use a trunnel input file to generate examples of that file for
   fuzzing.

    Here's the strategy:

      First, sort all the types topologically so that we consider
      every type before any type that depends on it.

      Then, for we iterate over each type to make examples of it.  We do
      a recursive descent on the syntax tree, yielding a sequence of
      (entry, constraint) tuples.  The "entry" item is a list whose
      members are bytestrings or NamedInt objects. The "constraint" item
      is an instance of Constraint that describes which NamedInt entries
      must have certain values.

      As we handle each (entry,constraint) tuple, we replace each
      NamedInt value in the entry with its constrained value, then merge
      the parts of the entry together.  If we haven't seen it before for
      this type, we save it to disk.

      To avoid combinatorial explosions, we limit the fan-out for each
      step, and choose different combinatoric strategies depending
      on the number of items to be considered at once.
"""


import trunnel.CodeGen
import trunnel.Grammar

import os
import hashlib
import random


class Constraints(object):
    """A Constraints object represents a set of constraints on named integer
       values.  It may also represent a 'failed constraint', which is
       impossible to satisfy.
    """
    def __init__(self):
        pass

    def isFailed(self):
        """Return true iff this constraint is unsatisfiable."""
        return False

    def add(self, k, v):
        """Return a new constraint made by adding the constraint "k=v" to this
           constrint.
        """
        raise NotImplemented()

    def merge(self, other):
        """Return a (maybe) new constraint made by adding all the constraints
           in 'other' to this constraint."""
        raise NotImplemented()

    def apply(self, item):
        """Given an object that might be a NamedInt or a byte sequence, return
           a byte sequence obtained by applying this constraint to
           that item.
        """
        if isinstance(item, NamedInt):
            return item.apply(self)
        return item

    def getConstraint(self, name):
        """Return the (integer) value that the integer field 'name'
           must have, or None if there is no such constraint.
        """
        return None


class NoConstraints(Constraints):
    """Represents the absence of any constraints.  Use the NIL singleton
       instead of creating more of this object.
    """
    def __init__(self):
        Constraints.__init__(self)

    def add(self, k, v):
        # Nothing plus something is something
        some = SomeConstraints({k: v})
        return some

    def merge(self, other):
        # Nothing plus anything is that thing
        return other


NIL = NoConstraints()


class FailedConstraint(Constraints):
    """Represents an unsatisfiable constraint, probably created by setting
       the same integer to two incompatible values."""
    def __init__(self):
        Constraints.__init__(self)

    def isFailed(self):
        return True

    def add(self, k, v):
        # Failed can't become any more failed
        return self

    def merge(self, other):
        # Failed can't become any more failed
        return self

    def apply(self, item):
        # You should never call apply on a failed constraint.
        assert False


FAILED = FailedConstraint()


class SomeConstraints(Constraints):
    """Represents a set of one or more constraints in a key-value dictionary.
    """
    def __init__(self, d):  # Owns reference to d!
        Constraints.__init__(self)
        self._d = d

    def add(self, k, v):
        try:
            oldval = self._d[k]
        except KeyError:
            # We had no previous value for this, so we can just add it
            # to our dict.
            newd = self._d.copy()
            newd[k] = v
            return SomeConstraints(newd)

        if oldval == v:
            # No change, so no need to allocate a new object.
            return self
        else:
            # Incompatible change; we can't satisfy it.
            return FAILED

    def merge(self, other):
        if not isinstance(other, SomeConstraints):
            # 'other' is either NIL or FAILED, which have simple merge rules.
            return other.merge(self)
        if len(other._d) < len(self._d):
            # This function runs in O(len(self._d)), so let's run it
            # on the shorter item.
            return other.merge(self)

        newd = self._d.copy()
        newd.update(other._d)
        for k, v in self._d.items():  # XXX Here's the inefficient O(n).
            if newd[k] != v:
                return FAILED
        return SomeConstraints(newd)

    def getConstraint(self, name):
        return self._d.get(name)


def constrain(k, v):
    if k is None:
        return NIL
    else:
        return SomeConstraints({k: v})


class NamedInt(object):
    """Represents an integer object with a name whose value (maybe)
       depends on some other part of the structure.
    """
    def __init__(self, name, width, val=None):
        self._name = name
        self._width = width
        self._val = val

    def withVal(self, val):
        assert self._val is None
        return NamedInt(self._name, self._width, val)

    def __len__(self):
        return self._width

    def apply(self, constraints):
        val = constraints.getConstraint(self._name)
        if val is None:
            val = self._val
        if val is None:
            # We expected to have some constraint on this value, but we
            # didn't.  How about 3? 3 is a nice number.
            val = 3
        # encode val little-endian in width bytes.
        return encodeInt(val, self._width)


def encodeInt(val, width):
    return b"".join(chr((val >> (width-i)*8) & 0xff)
                    for i in range(1, width+1))


def findLength(lst):
    """Given a list of bytestrings and NamedInts, return the total
       length of all items in the list.
    """
    return sum(len(item) for item in lst)


def combineExamples(grp, n, maximum=256):
    """Given a sequence of examples, yield up to 'maxiumum' values built
       by concatenating n items from the sequence (chosen with
       replacement).

       If possible, do an exhaustive combination of values.  Otherwise,
       take items randomly.

    """
    if len(grp) ** n > maximum:
        # we have to sample.
        for i in range(maximum):
            result = []
            for j in range(n):
                result.append(random.choice(grp))
            yield b"".join(result)
        return
    else:
        for e in combineExhaustively(grp, n):
            yield e


def combineExhaustively(grp, n):
    """Yield all bytestrings made by concatenating n members of grp
       (with replacement)."""
    if n == 0:
        yield b""
    elif n == 1:
        for e in grp:
            yield e
    else:
        for e in grp:
            for rest in combineExhaustively(grp, n-1):
                yield e + rest


def crossProduct(lol):
    """Given a list of lists of (entry, constraint) pairs,
       yield the cross-product of those lists.
    """
    if len(lol) == 0:
        return
    elif len(lol) == 1:
        for item, constraint in lol[0]:
            yield item, constraint
    else:
        for item, constraint in lol[0]:
            for irest, crest in crossProduct(lol[1:]):
                c2 = constraint.merge(crest)
                if not c2.isFailed():
                    yield item + irest, c2


def explore(lol):
    """As cross-product, but for cases where we face a much more
       combinatorically intense list of lists.  For this case,
       we consider the inputs position by position.  For each position,
       we let it vary over all its values, while choosing the simplest
       value for the other positions that allows it to meet its constraints.

       For example, if the lists had members (a), (x,y,z), (1,2,3), and no
       constraints, we'd yield: ax1, ax1, ay1, az1, ax1, ax2, ax3.
    """
    if len(lol) == 0:
        return
    elif len(lol) == 1:
        for item, constraint in lol[0]:
            yield item, constraint
    else:
        for idx in range(len(lol)):
            for item, constraint in exploreAt(lol, idx):
                yield item, constraint


def findComplying(lol, c):
    """Find a single value from among crossproduct(lol) complying with c.
       Return that value and its combined constraints."""
    if len(lol) == 0:
        return [], c

    for i, c2 in lol[0]:
        cboth = c.merge(c2)
        if cboth.isFailed():
            continue
        rest, call = findComplying(lol[1:], cboth)
        if call.isFailed():
            continue
        return rest, call

    return [], FAILED


def exploreAt(lol, idx):
    """Helper for explore."""
    before = lol[:idx]
    at = lol[idx]
    after = lol[idx+1:]
    for item, constraint in at:
        pre, c = findComplying(before, constraint)
        post, c2 = findComplying(after, c)
        yield pre + item + post, c2


def take_n(iterator, n):
    """Takes an iterator and yields up to the first n items
       from that iterator."""
    so_far = 0
    for item in iterator:
        so_far += 1
        if so_far > n:
            return
        yield item


class CorpusGenerator(trunnel.CodeGen.ASTVisitor):
    # target_dir -- where to write items
    # sort_order -- topologically sorted list of structure names
    # structExamples -- map from structure name to possible
    #   values that we generated for that structure
    # _expandConst -- helper function that knows how to map constant
    #   names to integers.
    # _maxFanout -- used to limit the branching factor when running
    #   combinatorically intense generators.
    # _maxExamples -- maximum number of distinct examples to generate
    #   for each structure
    # _maxCombinatorics -- when building long sequences, we try a cross-product
    #   approach when it would generate fewer than this many entries.
    #   Otherwise, we try an alternative approach; see explore().
    def __init__(self, target_dir):
        trunnel.CodeGen.ASTVisitor.__init__(self)
        self.target_dir = target_dir
        self.structExamples = {}
        self._maxFanout = 128
        self._maxCombinatorics = 1024
        self._maxExamples = 1024
        self._constrainedIntFieldNames = None
        self._strictFail = False   # DOCDOC

    def setChecker(self, ch):
        self.sort_order = ch.sortedStructs
        self._expandConst = ch.expandConstant

    def expandConst(self, v):
        """If v is a constant name, expand it.  Otherwise return v."""
        if isinstance(v, str):
            return self._expandConst(v)
        else:
            return v

    def visitFile(self, f):
        f.visitChildrenSorted(self.sort_order, self)

    def visitConstDecl(self, cd):
        pass

    def visitStructDecl(self, sd):
        self._constrainedIntFieldNames = sd.constrainedIntFields
        target = os.path.join(self.target_dir, sd.name)
        if not os.path.exists(target):
            os.makedirs(target)
        examples = set()
        for item in self.enumerateStructValues(sd):
            if item in examples:
                continue
            digest = hashlib.sha256(item).hexdigest()
            fname = os.path.join(target, digest)
            print(fname)
            with open(fname, 'wb') as f:
                f.write(item)
            examples.add(item)
            if len(examples) >= self._maxExamples:
                break
        self.structExamples[sd.name] = sorted(examples, key=len)
        self._constrainedIntFieldNames = None

    def enumerateStructValues(self, sd):
        """Helper: yields bytestrings that match a StructDecl."""
        for members, constraints in self.visitListOfMembers(sd.members):
            if constraints.isFailed():
                continue
            result = b"".join(constraints.apply(m) for m in members)
            yield result

    def visitSMInteger(self, smi):
        width = smi.inttype.width
        ni = NamedInt(smi.name, width // 8)
        if smi.name in self._constrainedIntFieldNames:
            # This will be set elsewhere, I hope.
            yield [ni], NIL
        elif smi.constraints is None:
            yield [ni.withVal(0)], NIL
            yield [ni.withVal((1 << width) - 1)], NIL
        else:
            for lo, hi in smi.constraints.ranges:
                lo = self.expandConst(lo)
                hi = self.expandConst(hi)
                yield [ni.withVal(lo)], NIL
                if lo != hi:
                    yield [ni.withVal(hi)], NIL

    def visitListOfMembers(self, members):
        results = []
        n_vals = 1
        for m in members:
            results.append(list(take_n(self.visit(m), self._maxFanout)))
            n_vals *= len(results[-1])
        if n_vals < self._maxCombinatorics:
            for i, c in crossProduct(results):
                yield i, c
        else:
            for i, c in explore(results):
                yield i, c

        # if len(members) == 0:
        #     return
        # elif len(members) == 1:
        #     for i, c in take_n(self.visit(members[0]), self._maxFanout):
        #         yield i, c
        #     return

        # for i, c in take_n(self.visit(members[0]), self._maxFanout):
        #     for irest, crest in self.visitListOfMembers(members[1:]):
        #         c2 = c.merge(crest)
        #         if not c2.isFailed():
        #             yield i + irest, c2

    def visitSMStruct(self, sms):
        for e in self.structExamples[sms.structname][:self._maxFanout]:
            yield [e], NIL

    def visitSMString(self, sms):
        yield [b"\0"], NIL
        yield [b"a\0"], NIL
        yield [b"abc\0"], NIL

    def visitSMFixedArray(self, sma):
        w = self.expandConst(sma.width)
        if type(sma.basetype) == str:
            examples = self.structExamples[sma.basetype]
            for e in combineExamples(examples, w, self._maxFanout):
                yield [e], NIL
        elif str(sma.basetype) == 'char':
            yield [b"x"*w], NIL
            yield [b"\xff"*w], NIL
        else:
            bitwidth = sma.basetype.width
            nbytes = w * (bitwidth // 8)
            yield [b"\0"*nbytes], NIL
            yield [b"\xff"*nbytes], NIL

    def visitSMVarArray(self, smva):
        widthfield = smva.widthfield
        if type(smva.basetype) == str:
            examples = self.structExamples[smva.basetype]
            yield [b""], constrain(widthfield, 0)
            c = constrain(widthfield, 1)
            for e in examples[:self._maxFanout]:
                yield [e], c
            c = constrain(widthfield, 2)
            for e in combineExamples(examples, 2, self._maxFanout):
                yield [e], c
        elif str(smva.basetype) == 'char':
            yield [b""], constrain(widthfield, 0)
            yield [b"h"], constrain(widthfield, 1)
            yield [b"hi"], constrain(widthfield, 2)
        else:
            w = smva.basetype.width // 8
            yield [b""], constrain(widthfield, 0)
            yield [b"\x00"*w], constrain(widthfield, 1)
            yield [b"\x00"*w*2], constrain(widthfield, 2)

    def visitSMLenConstrained(self, smlc):
        varname = smlc.lengthfield
        assert len(smlc.members) == 1   # XXX limitation
        for item, constraints in self.visit(smlc.members[0]):
            c = constraints.add(varname, findLength(item))
            if not c.isFailed():
                yield item, c

    def visitSMUnion(self, smu):
        tagfield = smu.tagfield
        for m in smu.members:
            for item, constraints in take_n(
                    self.visitListOfMembers(m.decls), self._maxFanout):
                if m.is_default:
                    c = constraints
                else:
                    oneval = m.tagvalue[0][0]
                    c = constraints.add(tagfield, self.expandConst(oneval))
                if not c.isFailed():
                    yield item, c

    def visitSMFail(self, x):
        if self._strictFail:
            return
        else:
            yield [b""], NIL

    def visitSMEos(self, x):
        yield [b""], NIL

    def visitSMIgnore(self, x):
        yield [b""], NIL
        yield [b"bla"], NIL

    def visitSMPosition(self, x):
        yield [b""], NIL


def generate_corpus(input_fnames, target_dir):
    generator = CorpusGenerator(target_dir)
    for input_fname in input_fnames:
        inp = open(input_fname, 'r')
        t = trunnel.Grammar.Lexer().tokenize(inp.read())
        inp.close()
        parsed = trunnel.Grammar.Parser().parse(t)

        c = trunnel.CodeGen.Checker()
        c.visit(parsed)

        generator.setChecker(c)
        generator.visit(parsed)


if __name__ == '__main__':
    import getopt
    import sys

    opts, args = getopt.gnu_getopt(sys.argv[1:],
                                   "o:",
                                   ["output-dir="])

    target_dir = "fuzzing-inputs"
    for (k, v) in opts:
        if k in ("-o", "--output-dir"):
            target_dir = v

    if len(args) == 0:
        sys.stderr.write("Syntax: python -m trunnel.SeedFuzzer [-o <dir>] "
                         "<fname...>\n")
        sys.exit(1)

    generate_corpus(args, target_dir)
