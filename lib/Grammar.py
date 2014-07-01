
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
        return self.value

    def __repr__(self):
        return "IntLiteral(%r,%r)"%(self.value, self.lineno)

KEYWORDS = set("""
  union struct
  u8 u16 u32 u64
  IN const eos nulterm WITH LENGTH default fail ignore
""".split())

class Lexer(spark.GenericScanner, object):

    def tokenize(self, input):
        self.rv = []
        self.lineno = 1
        spark.GenericScanner.tokenize(self, input)
        return self.rv

    def t_punctuation(self, s):
        r"(?:[;{}\[\]=,:]|\.\.|\.\.\.)"
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

    def t_newline(self, s):
        r"\n"
        self.lineno += 1


    def t_default(self, s):
        r"."
        raise ValueError("unmatched input: %r on line %r" % (s,self.lineno))


x = """const X = 20;

   // Assume these have real definitions.
   struct NAME2 { u8 foo; }
   struct NAME3 { u8 foo; }
   struct NAME4 { u8 foo;  }
   struct X { u8 foo;  }
   struct Y { u8 foo;  }

   const TYPE1 = 1;
   const TYPE2 = 2;
   const TYPE3 = 3;

   struct NAME {
      u8 thing1 IN [0..20];
      u16 thing2;

      u8 thingX IN [TYPE1, TYPE2, TYPE3];

      u8 thing3[20];
      u32 thing4[X];

      struct NAME2 thing5;

      struct NAME2 thing6[2];

      nulterm thing7;

      u8 count;

      struct NAME2 counted[count];

      u8 tag_field;
      union[tag_field] { 3 : struct NAME3;
                         4 : struct NAME4;
                         default: reject; }

      eos;
   }

   struct NAMEX {
       u8 tag;
       u8 length;

       union[tag] WITH LENGTH length {
           4: struct X name1;
           5: struct Y name2;
           default: ignore;
       };
   }

"""



t = Lexer().tokenize(x)


