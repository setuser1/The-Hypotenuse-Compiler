"""
C-like language parser and AST implementation.

This file defines:
- Abstract Syntax Tree (AST) node classes
- A recursive-descent parser with proper operator precedence
- A pretty-printer for AST visualization

The parser consumes tokens produced by an external lexer and builds
a structured AST suitable for semantic analysis or code generation.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

# ============================================================
# AST (Abstract Syntax Tree) Nodes
# ============================================================


@dataclass
class Node:
    """Base class for all AST nodes."""

    pass


@dataclass
class Program(Node):
    """Root of the AST: list of top-level declarations."""

    declarations: List[Node]


@dataclass
class Function(Node):
    """Function definition."""

    ret_type: str  # Return type
    name: str  # Function identifier
    params: List[Tuple[str, str]]  # (type, name) parameter list
    body: Node  # Function body (Compound)


@dataclass
class Declaration(Node):
    """Variable declaration or function prototype."""

    var_type: str
    name: str
    initializer: Optional[Node]  # Optional initializer expression
    array_size: Optional[int] = (
        None  # Optional array size for declarations like char temp[32]
    )


@dataclass
class Compound(Node):
    """Block scope: { statement* }"""

    stmts: List[Node]


@dataclass
class If(Node):
    """If / else control structure."""

    cond: Node
    then_branch: Node
    else_branch: Optional[Node]


@dataclass
class Do(Node):
    """Do-while loop: do { body } while (cond);"""

    body: Node
    cond: Node


@dataclass
class While(Node):
    """While loop."""

    cond: Node
    body: Node


@dataclass
class For(Node):
    """For loop with optional init, condition, and post expressions."""

    init: Optional[Node]
    cond: Optional[Node]
    post: Optional[Node]
    body: Node


@dataclass
class Switch(Node):
    """Switch statement with case labels."""

    expr: Node
    cases: List[Tuple[Optional[Node], Node]]  # (case_value, body) - None for default


@dataclass
class Case(Node):
    """Case label within a switch."""

    value: Optional[Node]  # None for default case
    body: Node


@dataclass
class Return(Node):
    """Return statement."""

    expr: Optional[Node]


@dataclass
class Break(Node):
    """Break statement."""

    pass


@dataclass
class Continue(Node):
    """Continue statement."""

    pass


@dataclass
class Goto(Node):
    """Goto statement."""

    label: str


@dataclass
class Label(Node):
    """Label statement (identifier:)."""

    name: str


@dataclass
class ExprStmt(Node):
    """Expression used as a statement."""

    expr: Optional[Node]


@dataclass
class Binary(Node):
    """Binary operation node."""

    op: str
    left: Node
    right: Node


@dataclass
class Unary(Node):
    """Unary operation (prefix or postfix).

    prefix=True  -> prefix operator  (e.g. -x, !y, ++x, --x)
    prefix=False -> postfix operator (e.g. x++, x--)
    """

    op: str
    operand: Node
    prefix: bool = True


@dataclass
class Literal(Node):
    """Literal constant."""

    value: Any


@dataclass
class Var(Node):
    """Variable reference."""

    name: str


@dataclass
class TypeExpr(Node):
    """Type expression (used in va_arg and casts)."""

    type_name: str


@dataclass
class Assignment(Node):
    """Assignment expression."""

    target: Node
    value: Node


@dataclass
class Call(Node):
    """Function call."""

    callee: Node
    args: List[Node]


@dataclass
class ArrayAccess(Node):
    """Array indexing expression."""

    array: Node
    index: Node


@dataclass
class Cast(Node):
    """C-style cast expression: (type) expr"""

    cast_type: str
    operand: Node


@dataclass
class Include(Node):
    """#include directive."""

    path: str
    is_system: bool  # True for <foo>, False for "foo"


@dataclass
class InitList(Node):
    """Brace-enclosed initializer list: { expr, expr, ... }"""

    elements: List[Node]


@dataclass
class CompoundLiteral(Node):
    """Compound literal: (type){ initializer_list }"""

    lit_type: str
    elements: List[Node]


@dataclass
class StructDef(Node):
    """C11 struct definition: struct Name { fields } or struct { fields }"""

    name: Optional[str]
    fields: List[Tuple[str, str]]
    is_anonymous: bool = False


@dataclass
class UnionDef(Node):
    """C11 union definition: union Name { fields } or union { fields }"""

    name: Optional[str]
    fields: List[Tuple[str, str]]
    is_anonymous: bool = False


@dataclass
class EnumDef(Node):
    """C11 enum definition: enum Name { values } or enum { values }"""

    name: Optional[str]
    values: List[
        Tuple[str, Optional[Any]]
    ]  # (name, value) - value is None if not specified


@dataclass
class Typedef(Node):
    """C11 typedef: typedef existing_type alias"""

    actual_type: str
    alias: str


@dataclass
class FieldAccess(Node):
    """Object.field access: obj.field"""

    obj: Node
    field_name: str


@dataclass
class DesignatedInit(Node):
    """C11 designated initializer: .field = value"""

    field: str
    value: Node


@dataclass
class Generic(Node):
    """C11 _Generic expression: _Generic(expr, type1: val1, type2: val2, ...)"""

    expr: Node
    associations: List[Tuple[str, Node]]  # (type, value) pairs


# ============================================================
# Recursive-Descent Parser
# ============================================================


# Type keyword token types used throughout the parser.
_TYPE_TOKENS = (
    "INT",
    "CHAR",
    "VOID",
    "FLOAT",
    "DOUBLE",
    "SHORT",
    "LONG",
    "SIGNED",
    "UNSIGNED",
    "STRUCT",
    "UNION",
    "ENUM",
    "TYPEDEF",
    "CONST",
    "VOLATILE",
    "STATIC",
    "EXTERN",
    "INLINE",
    "REGISTER",
    "AUTO",
    "SIZEOF",
    "UNKNOWN",
    "SIZE_T",
    "NORETURN",
)
_BASE_TYPE_TOKENS = (
    "INT",
    "CHAR",
    "VOID",
    "FLOAT",
    "DOUBLE",
    "SHORT",
    "LONG",
    "SIGNED",
    "UNSIGNED",
    "SIZE_T",
)


class Parser:
    """
    Recursive-descent parser for a C-like language.

    Implements operator precedence via layered parsing functions.

    Precedence (low -> high):
      assignment
      conditional (?:)
      logical or  (||)
      logical and (&&)
      equality    (== !=)
      relational  (< > <= >=)
      additive    (+ -)
      multiplicative (* /)
      power       (**)
      unary prefix  (- ! + ++ --)
      postfix       (call, subscript, ++ --)
      primary       (literal, identifier, grouped)
    """

    def __init__(self, tokens, var=None):
        self.tokens = tokens
        self.i = 0  # Current token index
        self.var = var  # Optional external state
        self._typedefs = {}  # typedef alias -> actual_type

    # -------------------------
    # Token helpers
    # -------------------------

    def peek(self):
        """Return current token without consuming it.

        Returns an ('EOF', '') sentinel when the token stream is exhausted
        so callers never receive an IndexError.
        """
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        return ("EOF", "")

    def advance(self):
        """Consume and return current token."""
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, type_name: str):
        """Consume token of expected type or raise syntax error."""
        tok = self.peek()
        if tok[0] == type_name:
            return self.advance()
        raise SyntaxError(
            f"Expected {type_name} at token index {self.i}, got {tok[0]} ({tok[1]!r})"
        )

    def accept(self, type_name: str):
        """Consume token if it matches expected type."""
        if self.peek()[0] == type_name:
            return self.advance()
        return None

    # ============================================================
    # Pointer-star helpers
    # ============================================================

    def _consume_pointer_stars(self, typ: str) -> str:
        """Append '*' to typ for each pointer star token.

        Handles both MULTIPLY (single *) and POWER (**), so that
        int** is parsed as a pointer-to-pointer rather than raising
        a syntax error.
        """
        while True:
            if self.peek()[0] == "MULTIPLY":
                self.advance()
                typ += "*"
            elif self.peek()[0] == "POWER":
                # '**' lexed as POWER — treat as two pointer stars
                self.advance()
                typ += "**"
            else:
                break
        return typ

    def _parse_local_declaration(self) -> Node:
        """Parse a local variable declaration inside a function."""
        typ = self.advance()[1]
        # Handle typedef alias - resolve to actual type for declarations
        if typ in self._typedefs:
            typ = self._typedefs[typ]
        # Handle compound types: long long, unsigned long, etc.
        if self.peek()[0] in _BASE_TYPE_TOKENS:
            typ2 = self.advance()[1]
            typ = f"{typ} {typ2}"
        # Handle pointer type
        typ = self._consume_pointer_stars(typ)

        name = self.expect("IDENTIFIER")[1]

        # Handle array declaration
        array_size = None
        if self.accept("LBRACKET"):
            if self.peek()[0] == "INT_LITERAL":
                array_size = int(self.advance()[1])
            self.expect("RBRACKET")

        # Handle initializer
        init = None
        if self.accept("ASSIGN"):
            init = self.parse_expression()

        self.expect("SEMICOLON")
        return Declaration(typ, name, init, array_size)

    # ============================================================
    # Top-level parsing
    # ============================================================

    def parse_program(self) -> Program:
        """Parse entire translation unit."""
        decls = []
        while self.peek()[0] != "EOF":
            decls.append(self.parse_external())
        return Program(decls)

    def _parse_preprocessor(self, directive: str) -> Optional[Node]:
        """Parse a preprocessor directive."""
        stripped = directive.strip()
        if stripped.startswith("#include"):
            rest = stripped[len("#include") :].strip()
            if rest.startswith("<") and ">" in rest:
                start = rest.index("<")
                end = rest.index(">")
                path = rest[start + 1 : end]
                return Include(path, is_system=True)
            elif rest.startswith('"') and rest.count('"') >= 2:
                start = rest.index('"')
                end = rest.index('"', start + 1)
                path = rest[start + 1 : end]
                return Include(path, is_system=False)
        return None

    def parse_external(self) -> Node:
        """
        Parse global declarations:
        - Functions
        - Function prototypes
        - Global variables
        - Include directives
        """
        t = self.peek()

        # Handle preprocessor directives
        if t[0] == "PREPROCESSOR":
            directive = self.advance()[1]
            result = self._parse_preprocessor(directive)
            if result is not None:
                return result
            return self.parse_external()

        # Skip comments
        if t[0] in ("COMMENT_MULTI", "COMMENT_LINE"):
            self.advance()
            return self.parse_external()

        # Reject deprecated / removed keywords immediately.
        if t[0] in ("RESTRICT", "BOOLEAN"):
            raise SyntaxError(
                f"Deprecated keyword used! Please remove or replace the keyword. "
                f"Found '{t[0]}'."
            )

        if t[0] == "TYPEDEF":
            return self.parse_typedef()

        if t[0] == "STRUCT":
            return self.parse_struct_definition()

        if t[0] == "UNION":
            return self.parse_union_definition()

        if t[0] == "ENUM":
            return self.parse_enum_definition()

        if t[0] in _TYPE_TOKENS or t[0] == "IDENTIFIER":
            if t[0] == "IDENTIFIER" and t[1] not in self._typedefs:
                raise SyntaxError(f"Unexpected identifier at top-level: '{t[1]}")
            typ = self.advance()[1]
            # Handle typedef alias - resolve to actual type for declarations
            if typ in self._typedefs:
                typ = self._typedefs[typ]
            # Handle compound types: long long, unsigned long, etc.
            if self.peek()[0] in _BASE_TYPE_TOKENS:
                typ2 = self.advance()[1]
                typ = f"{typ} {typ2}"

            # Handle function specifiers (inline, noreturn)
            while self.peek()[0] in ("INLINE", "NORETURN"):
                spec = self.advance()[1]
                typ = f"{spec} {typ}"

            # Handle pointer type: int* ptr or int** ptr2
            typ = self._consume_pointer_stars(typ)
            # Expected Identifier error handling
            if self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                raise SyntaxError(
                    f"Expected identifier. "
                    f"Declaration keyword '{typ}' was followed by a non-identifier token. "
                    f"Got '{bad_tok[0]}'."
                )
            name = self.advance()[1]
            # Function or prototype
            if self.accept("LPAREN"):
                params = []

                if not self.accept("RPAREN"):
                    # Handle void parameter (means no params)
                    if self.peek()[0] == "VOID":
                        self.advance()  # consume void
                        self.expect("RPAREN")
                        params = []
                    else:
                        while True:
                            # Handle type qualifiers BEFORE base type (const, volatile, etc.)
                            type_qualifiers = []
                            while self.peek()[0] in ("CONST", "VOLATILE"):
                                type_qualifiers.append(self.advance()[1])

                            ptype = self.advance()[1]
                            # Handle typedef alias - resolve to actual type for declarations
                            if ptype in self._typedefs:
                                ptype = self._typedefs[ptype]
                            # Handle compound types in parameters
                            if self.peek()[0] in _BASE_TYPE_TOKENS:
                                ptype2 = self.advance()[1]
                                ptype = f"{ptype} {ptype2}"
                            # Handle pointer types in parameters
                            ptype = self._consume_pointer_stars(ptype)

                            # Handle type qualifiers AFTER pointer (like const after *)
                            while self.peek()[0] in ("CONST", "VOLATILE"):
                                type_qualifiers.append(self.advance()[1])

                            # Prepend qualifiers if any
                            if type_qualifiers:
                                ptype = " ".join(type_qualifiers) + " " + ptype

                            pname = self.expect("IDENTIFIER")[1]
                            params.append((ptype, pname))
                            if self.accept("COMMA"):
                                # Handle variadic functions with ...
                                if self.accept("ELLIPSIS"):
                                    params.append(("...", "..."))
                                    self.expect("RPAREN")
                                    break
                                continue
                            self.expect("RPAREN")
                            break

                # Function definition vs prototype
                if self.peek()[0] == "LBRACE":
                    return Function(typ, name, params, self.parse_compound())
                else:
                    self.expect("SEMICOLON")
                    return Declaration(f"{typ} (func prototype)", name, None)

            # Global variable — may have comma-separated declarators
            # Handle array declaration (including multi-dimensional)
            array_size = None
            sizes = []
            while self.accept("LBRACKET"):
                if self.peek()[0] == "INT_LITERAL":
                    sizes.append(int(self.advance()[1]))
                else:
                    sizes.append(0)  # flexible array
                self.expect("RBRACKET")
            if len(sizes) > 0:
                array_size = sizes[0] if len(sizes) == 1 else sizes

            init = self.parse_expression() if self.accept("ASSIGN") else None
            decls = [Declaration(typ, name, init, array_size)]
            while self.accept("COMMA"):
                extra_name = self.expect("IDENTIFIER")[1]
                # Handle multi-dimensional array in comma-separated list
                extra_sizes = []
                while self.accept("LBRACKET"):
                    if self.peek()[0] == "INT_LITERAL":
                        extra_sizes.append(int(self.advance()[1]))
                    else:
                        extra_sizes.append(0)
                    self.expect("RBRACKET")
                extra_array_size = (
                    extra_sizes[0]
                    if len(extra_sizes) == 1
                    else extra_sizes
                    if extra_sizes
                    else None
                )
                extra_init = self.parse_expression() if self.accept("ASSIGN") else None
                decls.append(Declaration(typ, extra_name, extra_init, extra_array_size))
            self.expect("SEMICOLON")
            if len(decls) == 1:
                return decls[0]
            # Wrap multiple declarators in a synthetic Compound so the caller
            # gets a single node (Program.declarations is a flat list, so we
            # extend it below instead).
            return _MultiDecl(decls)

        raise SyntaxError(f"Unexpected token at top-level: {t}")

    def parse_typedef(self) -> Node:
        """Parse a typedef declaration."""
        self.expect("TYPEDEF")
        actual_type = ""
        while True:
            tok = self.peek()
            if tok[0] in _BASE_TYPE_TOKENS:
                actual_type += self.advance()[1] + " "
                if self.peek()[0] in _BASE_TYPE_TOKENS:
                    actual_type += self.advance()[1] + " "
            elif tok[0] == "IDENTIFIER":
                # Check if this is the alias (next token is SEMICOLON)
                # In that case, don't consume it as part of the type
                if self.tokens[self.i + 1][0] == "SEMICOLON":
                    break
                actual_type += self.advance()[1] + " "
            elif tok[0] == "STRUCT":
                actual_type += self.advance()[1]
                if self.peek()[0] == "IDENTIFIER":
                    actual_type += " " + self.advance()[1]
                if self.peek()[0] == "LBRACE":
                    actual_type += self.advance()[1]
                    depth = 1
                    while depth > 0:
                        inner_tok = self.peek()
                        if inner_tok[0] == "LBRACE":
                            depth += 1
                        elif inner_tok[0] == "RBRACE":
                            depth -= 1
                        self.advance()
                    if self.peek()[0] == "IDENTIFIER":
                        actual_type += " " + self.advance()[1]
            elif tok[0] == "MULTIPLY":
                actual_type += self.advance()[1]
            elif tok[0] == "LPAREN":
                saved_i = self.i
                if (
                    self.i + 1 < len(self.tokens)
                    and self.tokens[self.i + 1][0] == "MULTIPLY"
                ):
                    self.advance()
                    self.advance()
                    alias = self.expect("IDENTIFIER")[1]
                    self.expect("RPAREN")
                    self.expect("LPAREN")
                    params = []
                    if self.peek()[0] != "RPAREN":
                        while True:
                            ptype = ""
                            if self.peek()[0] in _BASE_TYPE_TOKENS:
                                ptype = self.advance()[1]
                            elif self.peek()[0] == "IDENTIFIER":
                                ptype = self.advance()[1]
                            elif self.peek()[0] == "STRUCT":
                                ptype = self.advance()[1]
                                if self.peek()[0] == "IDENTIFIER":
                                    ptype += " " + self.advance()[1]
                            params.append(ptype)
                            if self.peek()[0] == "COMMA":
                                self.advance()
                            else:
                                break
                    self.expect("RPAREN")
                    actual_type = f"{actual_type.strip()} (*)({', '.join(params)})"
                    self._typedefs[alias] = actual_type
                    self.expect("SEMICOLON")
                    return Typedef(actual_type, alias)
                else:
                    self.i = saved_i
                    break
            else:
                break
            if self.peek()[0] == "SEMICOLON":
                break
            # Check if next token would be semicolon - if so, we're done with type
            if self.peek()[0] == "SEMICOLON":
                break
        actual_type = actual_type.strip()
        actual_type = self._consume_pointer_stars(actual_type)
        # If there's no more type to parse, what we have is the alias
        # The last identifier consumed should be the actual_type if we broke due to SEMICOLON lookahead
        # But we need to get the final alias
        alias = self.expect("IDENTIFIER")[1]
        self.expect("SEMICOLON")
        self._typedefs[alias] = actual_type
        return Typedef(actual_type, alias)

    def parse_struct_definition(self) -> Node:
        """Parse a struct definition or struct type usage."""
        self.expect("STRUCT")
        name = None
        is_anonymous = False
        if self.peek()[0] == "IDENTIFIER":
            name = self.advance()[1]

        # Check what follows the struct name
        if self.peek()[0] == "LBRACE":
            # Full struct definition: struct Name { ... };
            is_anonymous = name is None
            self.advance()
            fields = []
            while self.peek()[0] != "RBRACE":
                if self.peek()[0] == "EOF":
                    raise SyntaxError("Unexpected end of file: unclosed struct")
                field_type = ""
                while self.peek()[0] in _BASE_TYPE_TOKENS:
                    field_type += self.advance()[1] + " "
                    if self.peek()[0] in _BASE_TYPE_TOKENS:
                        field_type += self.advance()[1] + " "
                field_type = field_type.strip()
                field_type = self._consume_pointer_stars(field_type)
                field_name = self.expect("IDENTIFIER")[1]
                self.expect("SEMICOLON")
                fields.append((field_type, field_name))
            self.expect("RBRACE")
            self.expect("SEMICOLON")
            return StructDef(name=name, fields=fields, is_anonymous=is_anonymous)
        elif self.peek()[0] == "SEMICOLON":
            # Forward declaration: struct Name;
            self.advance()
            return StructDef(name=name, fields=[], is_anonymous=False)
        elif self.peek()[0] == "IDENTIFIER" and name is not None:
            # Type usage: struct Name varName;
            # This is actually a variable declaration using struct type
            # We need to handle it as a Declaration
            var_type = f"struct {name}"
            var_type = self._consume_pointer_stars(var_type)
            var_name = self.expect("IDENTIFIER")[1]
            init = self.parse_expression() if self.accept("ASSIGN") else None
            self.expect("SEMICOLON")
            return Declaration(var_type, var_name, init)

        raise SyntaxError(f"Unexpected token after struct: {self.peek()}")

    def parse_union_definition(self) -> Node:
        """Parse a union definition or union type usage."""
        self.expect("UNION")
        name = None
        is_anonymous = False
        if self.peek()[0] == "IDENTIFIER":
            name = self.advance()[1]

        if self.peek()[0] == "LBRACE":
            is_anonymous = name is None
            self.advance()
            fields = []
            while self.peek()[0] != "RBRACE":
                if self.peek()[0] == "EOF":
                    raise SyntaxError("Unexpected end of file: unclosed union")
                field_type = ""
                while self.peek()[0] in _BASE_TYPE_TOKENS:
                    field_type += self.advance()[1] + " "
                    if self.peek()[0] in _BASE_TYPE_TOKENS:
                        field_type += self.advance()[1] + " "
                field_type = field_type.strip()
                field_type = self._consume_pointer_stars(field_type)
                field_name = self.expect("IDENTIFIER")[1]
                self.expect("SEMICOLON")
                fields.append((field_type, field_name))
            self.expect("RBRACE")
            self.expect("SEMICOLON")
            return UnionDef(name=name, fields=fields, is_anonymous=is_anonymous)
        elif self.peek()[0] == "SEMICOLON":
            self.advance()
            return UnionDef(name=name, fields=[], is_anonymous=False)
        elif self.peek()[0] == "IDENTIFIER" and name is not None:
            var_type = f"union {name}"
            var_type = self._consume_pointer_stars(var_type)
            var_name = self.expect("IDENTIFIER")[1]
            init = self.parse_expression() if self.accept("ASSIGN") else None
            self.expect("SEMICOLON")
            return Declaration(var_type, var_name, init)

        raise SyntaxError(f"Unexpected token after union: {self.peek()}")

    def parse_enum_definition(self) -> Node:
        """Parse an enum definition or enum type usage."""
        self.expect("ENUM")
        name = None
        if self.peek()[0] == "IDENTIFIER":
            name = self.advance()[1]

        if self.peek()[0] == "LBRACE":
            self.advance()
            values = []
            next_value = 0
            while self.peek()[0] != "RBRACE":
                if self.peek()[0] == "EOF":
                    raise SyntaxError("Unexpected end of file: unclosed enum")
                enum_name = self.expect("IDENTIFIER")[1]
                value = None
                if self.accept("ASSIGN"):
                    value = self.parse_expression()
                    if isinstance(value, Literal):
                        lit_val = _cast_literal(value.value)
                        if isinstance(lit_val, int):
                            next_value = lit_val + 1
                            value = lit_val
                        else:
                            next_value += 1
                    else:
                        next_value += 1
                else:
                    value = next_value
                    next_value += 1
                values.append((enum_name, value))
                if not self.accept("COMMA"):
                    break
            self.expect("RBRACE")
            self.expect("SEMICOLON")
            return EnumDef(name=name, values=values)
        elif self.peek()[0] == "SEMICOLON":
            self.advance()
            return EnumDef(name=name, values=[])
        elif self.peek()[0] == "IDENTIFIER" and name is not None:
            var_type = f"enum {name}"
            var_type = self._consume_pointer_stars(var_type)
            var_name = self.expect("IDENTIFIER")[1]
            init = self.parse_expression() if self.accept("ASSIGN") else None
            self.expect("SEMICOLON")
            return Declaration(var_type, var_name, init)

        raise SyntaxError(f"Unexpected token after enum: {self.peek()}")

    # ============================================================
    # Statements
    # ============================================================

    def parse_statement(self) -> Node:
        """Parse a single statement."""
        t = self.peek()

        # Skip preprocessor directives and comments inside function bodies too
        if t[0] in ("PREPROCESSOR", "COMMENT_MULTI", "COMMENT_LINE"):
            self.advance()
            return self.parse_statement()

        # Handle type declarations (including size_t)
        if t[0] in _BASE_TYPE_TOKENS:
            return self._parse_local_declaration()
        # Handle typedef aliases
        if t[0] == "IDENTIFIER" and t[1] in self._typedefs:
            return self._parse_local_declaration()

        if t[0] == "LBRACE":
            return self.parse_compound()

        if t[0] == "IF":
            self.advance()
            self.expect("LPAREN")
            cond = self.parse_expression()
            self.expect("RPAREN")
            then_branch = self.parse_statement()
            else_branch = self.parse_statement() if self.accept("ELSE") else None
            return If(cond, then_branch, else_branch)

        if t[0] == "WHILE":
            self.advance()
            self.expect("LPAREN")
            cond = self.parse_expression()
            self.expect("RPAREN")
            return While(cond, self.parse_statement())

        if t[0] == "FOR":
            self.advance()
            self.expect("LPAREN")
            init = None
            if self.peek()[0] != "SEMICOLON":
                if self.peek()[0] in (
                    "INT",
                    "CHAR",
                    "VOID",
                    "FLOAT",
                    "DOUBLE",
                    "LONG",
                    "SHORT",
                    "SIGNED",
                    "UNSIGNED",
                    "STRUCT",
                    "UNION",
                    "ENUM",
                ):
                    typ = self.advance()[1]
                    idtok = self.expect("IDENTIFIER")
                    name = idtok[1]
                    init = Declaration(var_type=typ, name=name, initializer=None)
                    if self.accept("ASSIGN"):
                        init.initializer = self.parse_expression()
                else:
                    init = self.parse_expression()
            self.expect("SEMICOLON")
            cond = None
            if self.peek()[0] != "SEMICOLON":
                cond = self.parse_expression()
            self.expect("SEMICOLON")
            post = None
            if self.peek()[0] != "RPAREN":
                post = self.parse_expression()
            self.expect("RPAREN")
            body = self.parse_statement()
            return For(init=init, cond=cond, post=post, body=body)

        if t[0] == "DO":
            self.advance()
            body = self.parse_statement()
            self.expect("WHILE")
            self.expect("LPAREN")
            cond = self.parse_expression()
            self.expect("RPAREN")
            self.expect("SEMICOLON")
            return Do(body=body, cond=cond)

        if t[0] == "RETURN":
            self.advance()
            expr = self.parse_expression() if self.peek()[0] != "SEMICOLON" else None
            self.expect("SEMICOLON")
            return Return(expr)

        if t[0] == "BREAK":
            self.advance()
            self.expect("SEMICOLON")
            return Break()

        if t[0] == "CONTINUE":
            self.advance()
            self.expect("SEMICOLON")
            return Continue()

        if t[0] == "GOTO":
            self.advance()
            label = self.expect("IDENTIFIER")[1]
            self.expect("SEMICOLON")
            return Goto(label)

        if t[0] == "SWITCH":
            self.advance()
            self.expect("LPAREN")
            expr = self.parse_expression()
            self.expect("RPAREN")
            body = self.parse_compound()
            cases = []
            i = 0
            while i < len(body.stmts):
                stmt = body.stmts[i]
                if hasattr(stmt, "case_label"):
                    case_value = stmt.case_label
                    case_body = []
                    i += 1
                    while i < len(body.stmts) and not (
                        hasattr(body.stmts[i], "case_label")
                        or hasattr(body.stmts[i], "is_default")
                    ):
                        case_body.append(body.stmts[i])
                        i += 1
                    cases.append(
                        (case_value, Compound(case_body) if case_body else Compound([]))
                    )
                else:
                    i += 1
            return Switch(expr, cases)

        if t[0] == "CASE":
            case_label_node = type(
                "CaseLabel", (), {"case_label": None, "is_default": False}
            )()
            self.advance()
            case_value = self.parse_expression()
            case_label_node.case_label = case_value
            self.expect("COLON")
            return case_label_node

        if t[0] == "DEFAULT":
            default_label_node = type(
                "DefaultLabel", (), {"case_label": None, "is_default": True}
            )()
            self.advance()
            self.expect("COLON")
            return default_label_node

        # Reject deprecated / removed keywords in statement position too.
        if t[0] in ("RESTRICT", "BOOLEAN"):
            raise SyntaxError(
                f"Deprecated keyword used! Please remove or replace the keyword. "
                f"Found '{t[0]}'."
            )

        # Label: IDENTIFIER:
        if t[0] == "IDENTIFIER" and len(self.tokens) > self.i + 1:
            next_tok = self.tokens[self.i + 1]
            if next_tok[0] == "COLON":
                name = self.advance()[1]
                self.advance()  # consume COLON
                return Label(name)

        # Local declaration
        if t[0] in (
            "INT",
            "CHAR",
            "VOID",
            "FLOAT",
            "DOUBLE",
            "LONG",
            "SHORT",
            "SIGNED",
            "UNSIGNED",
            "STRUCT",
            "UNION",
            "ENUM",
            "CONST",
            "VOLATILE",
            "TYPEDEF",
        ) or (
            t[0] == "IDENTIFIER" and (t[1] in ("va_list",) or t[1] in self._typedefs)
        ):
            qualifiers = []
            # Collect any leading type qualifiers
            while self.peek()[0] in ("CONST", "VOLATILE"):
                qualifiers.append(self.advance()[1])

            # Get the base type
            base_type = self.advance()[1]

            # Handle TYPEDEF keyword - it's being used as a type, not as a new typedef definition
            # Look up the actual type from typedef table
            if base_type == "typedef":
                if self.peek()[0] == "IDENTIFIER":
                    base_type = self.advance()[1]
                else:
                    base_type = "int"
                if base_type in self._typedefs:
                    base_type = self._typedefs[base_type]

            # Handle identifier that's a typedef alias (not the typedef keyword)
            elif t[0] == "IDENTIFIER" and t[1] not in ("va_list",):
                if t[1] in self._typedefs:
                    base_type = self._typedefs[t[1]]

            # Handle struct TypeName varName (both global and local)
            # base_type is "struct", next token should be the struct tag
            elif base_type == "struct" and self.peek()[0] == "IDENTIFIER":
                # This is struct Tag varName or struct varName
                struct_tag = self.advance()[1]
                base_type = f"struct {struct_tag}"
                # Check for pointer
                base_type = self._consume_pointer_stars(base_type)

            # Handle union TypeName varName (both global and local)
            elif base_type == "union" and self.peek()[0] == "IDENTIFIER":
                union_tag = self.advance()[1]
                base_type = f"union {union_tag}"
                base_type = self._consume_pointer_stars(base_type)

            # Handle enum TypeName varName (both global and local)
            elif base_type == "enum" and self.peek()[0] == "IDENTIFIER":
                enum_tag = self.advance()[1]
                base_type = f"enum {enum_tag}"
                base_type = self._consume_pointer_stars(base_type)

            # Handle compound types in local declarations
            if self.peek()[0] in _BASE_TYPE_TOKENS:
                base_type2 = self.advance()[1]
                base_type = f"{base_type} {base_type2}"

            # Build the full type: [qualifiers] base_type [pointers]
            typ = base_type
            if qualifiers:
                typ = " ".join(qualifiers) + " " + typ

            # Handle pointer type: int* ptr or int** ptr2
            typ = self._consume_pointer_stars(typ)

            if self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                raise SyntaxError(
                    f"Expected identifier. "
                    f"Declaration keyword '{typ}' was followed by a non-identifier token. "
                    f"Got '{bad_tok[0]}'."
                )
            name = self.advance()[1]

            # Handle array declarations: char temp[32]
            array_size = None
            if self.peek()[0] == "LBRACKET":
                self.advance()  # consume '['
                if self.peek()[0] == "INT_LITERAL":
                    array_size = int(self.advance()[1])
                self.expect("RBRACKET")

            # Handle initialization
            init = None
            if self.accept("ASSIGN"):
                init = self.parse_expression()
            elif self.peek()[0] == "LBRACE":
                # Brace-init without '=': int arr[] = {1, 2, 3} style
                init = self.parse_init_list()

            # First declarator
            decls = [Declaration(typ, name, init, array_size)]

            # Comma-separated declarators: int a = 1, b = 2, c;
            while self.accept("COMMA"):
                extra_name = self.expect("IDENTIFIER")[1]
                extra_init = None
                if self.accept("ASSIGN"):
                    extra_init = self.parse_expression()
                elif self.peek()[0] == "LBRACE":
                    extra_init = self.parse_init_list()
                decls.append(Declaration(typ, extra_name, extra_init))

            self.expect("SEMICOLON")

            if len(decls) == 1:
                return decls[0]
            return Compound(decls)

        # Expression statement
        expr = self.parse_expression() if self.peek()[0] != "SEMICOLON" else None
        self.expect("SEMICOLON")
        return ExprStmt(expr)

    def parse_compound(self) -> Compound:
        """Parse a block scope.

        Raises a clean SyntaxError if EOF is reached before the closing
        brace, rather than propagating an IndexError from peek().
        """
        self.expect("LBRACE")
        stmts = []
        while True:
            t = self.peek()
            if t[0] == "RBRACE":
                break
            if t[0] == "EOF":
                raise SyntaxError(
                    "Unexpected end of file: unclosed '{' — missing closing '}'"
                )
            stmts.append(self.parse_statement())
        self.expect("RBRACE")
        return Compound(stmts)

    def parse_init_list(self) -> InitList:
        """Parse a brace-enclosed initializer list: { expr, expr, ... }"""
        self.expect("LBRACE")
        elements = []
        if self.peek()[0] != "RBRACE":
            elements.append(self.parse_initializer_element())
            while self.accept("COMMA"):
                if self.peek()[0] == "RBRACE":
                    break
                elements.append(self.parse_initializer_element())
        self.expect("RBRACE")
        return InitList(elements)

    def parse_initializer_element(self) -> Node:
        """Parse a single element in an initializer list.

        Handles both regular expressions and C11 designated initializers (.field = value).
        """
        if self.peek()[0] == "DOT":
            self.advance()
            field_name = self.expect("IDENTIFIER")[1]
            self.expect("ASSIGN")
            value = self.parse_assignment()
            return DesignatedInit(field=field_name, value=value)
        return self.parse_assignment()

    # ============================================================
    # Expressions (precedence climbing)
    # ============================================================

    def parse_expression(self) -> Node:
        node = self.parse_assignment()
        while self.accept("COMMA"):
            right = self.parse_assignment()
            node = right
        return node

    def parse_assignment(self) -> Node:
        node = self.parse_conditional()
        if self.accept("ASSIGN"):
            return Assignment(node, self.parse_assignment())
        # Handle compound assignment operators (+=, -=, *=, /=, %=, etc.)
        compound_ops = {
            "PLUS_ASSIGN": "+",
            "MINUS_ASSIGN": "-",
            "MULTIPLY_ASSIGN": "*",
            "DIVIDE_ASSIGN": "/",
            "MOD_ASSIGN": "%",
        }
        for tok_type, op_symbol in compound_ops.items():
            if self.accept(tok_type):
                right = self.parse_assignment()
                return Assignment(node, Binary(op_symbol, node, right))
        return node

    def parse_conditional(self) -> Node:
        node = self.parse_logical_or()
        if self.accept("QUESTION"):
            t = self.parse_expression()
            self.expect("COLON")
            f = self.parse_conditional()
            return Binary("?:", node, Binary("branch", t, f))
        return node

    def parse_logical_or(self) -> Node:
        """Parse logical OR expressions (||)."""
        left = self.parse_logical_and()
        while self.peek()[0] == "OR":
            op = self.advance()[1]
            right = self.parse_logical_and()
            left = Binary(op, left, right)
        return left

    def parse_logical_and(self) -> Node:
        """Parse logical AND expressions (&&)."""
        left = self.parse_equality()
        while self.peek()[0] == "AND":
            op = self.advance()[1]
            right = self.parse_equality()
            left = Binary(op, left, right)
        return left

    def parse_equality(self) -> Node:
        """Parse equality expressions (== !=)."""
        left = self.parse_relational()
        while self.peek()[0] in ("EQ", "NEQ"):
            op = self.advance()[1]
            right = self.parse_relational()
            left = Binary(op, left, right)
        return left

    def parse_bitwise(self) -> Node:
        """Parse bitwise expressions (| ^ & << >>)."""
        left = self.parse_add()
        while self.peek()[0] in (
            "BITWISE_OR",
            "BITWISE_XOR",
            "BITWISE_NOT",
            "AMPERSAND",
        ):
            op = self.advance()[1]
            right = self.parse_add()
            left = Binary(op, left, right)

        while self.peek()[0] in ("LSHIFT", "RSHIFT"):
            op = self.advance()[1]
            right = self.parse_add()
            left = Binary(op, left, right)
        return left

    def parse_relational(self) -> Node:
        """Parse relational expressions (< > <= >=)."""
        left = self.parse_bitwise()
        while self.peek()[0] in ("LT", "GT", "LE", "GE"):
            op = self.advance()[1]
            right = self.parse_bitwise()
            left = Binary(op, left, right)
        return left

    def parse_add(self) -> Node:
        """Parse addition and subtraction expressions."""
        left = self.parse_term()
        while self.peek()[0] in ("PLUS", "MINUS"):
            op = self.advance()[1]
            right = self.parse_term()
            left = Binary(op, left, right)
        return left

    def parse_term(self) -> Node:
        """Parse multiplication and division expressions."""
        left = self.parse_power()
        while self.peek()[0] in ("MULTIPLY", "DIVIDE", "MODULO"):
            op = self.advance()[1]
            right = self.parse_power()
            left = Binary(op, left, right)
        return left

    def parse_power(self) -> Node:
        """Parse exponentiation expressions (right-associative)."""
        left = self.parse_unary()
        if self.accept("POWER"):
            right = self.parse_power()  # Right-associative
            return Binary("**", left, right)
        return left

    def parse_unary(self) -> Node:
        """Parse unary prefix expressions (e.g. -x, !y, ++x, --x)."""
        token = self.peek()
        # Handle signed integer literals directly to preserve integer kind for negatives
        if token[0] == "MINUS":
            # Peek at next token to check if it's an integer literal
            next_token = (
                self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
            )
            if next_token and next_token[0] == "INT_LITERAL":
                self.advance()  # consume MINUS
                lit_val = self.advance()[1]
                return Literal(f"-{lit_val}")
        if token[0] in ("PLUS", "MINUS", "NOT", "BITWISE_NOT"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return Unary(op=op, operand=operand, prefix=True)
        if token[0] in ("INCREMENT", "DECREMENT"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return Unary(op=op, operand=operand, prefix=True)
        if token[0] == "MULTIPLY":
            self.advance()
            operand = self.parse_unary()
            return Unary(op="*", operand=operand, prefix=True)
        if token[0] == "AMPERSAND":
            self.advance()
            operand = self.parse_unary()
            return Unary(op="&", operand=operand, prefix=True)
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        """Parse postfix expressions: calls, subscripts, and x++/x--."""
        node = self.parse_primary()
        while True:
            if self.peek()[0] == "LPAREN":
                # Function call: expr(arg, ...)
                self.advance()
                args = []
                if self.peek()[0] != "RPAREN":
                    # Check if first arg is a type keyword (for va_arg)
                    if self.peek()[0] in _BASE_TYPE_TOKENS:
                        args.append(self.parse_type_expression())
                    else:
                        args.append(self.parse_assignment())
                    while self.accept("COMMA"):
                        if self.peek()[0] in _BASE_TYPE_TOKENS:
                            args.append(self.parse_type_expression())
                        else:
                            args.append(self.parse_assignment())
                self.expect("RPAREN")
                node = Call(node, args)
            elif self.peek()[0] == "LBRACKET":
                # Array subscript: expr[index]
                self.advance()
                index = self.parse_expression()
                self.expect("RBRACKET")
                node = ArrayAccess(node, index)
            elif self.peek()[0] in ("INCREMENT", "DECREMENT"):
                # Postfix ++/--: expr++ / expr--
                op = self.advance()[1]
                node = Unary(op=op, operand=node, prefix=False)
            elif self.peek()[0] == "DOT":
                # Field access: expr.field
                self.advance()
                field_name = self.expect("IDENTIFIER")[1]
                node = FieldAccess(node, field_name)
            else:
                break
        return node

    def parse_type_expression(self) -> Node:
        """Parse a type keyword or compound type (e.g., int, long long)."""
        if self.peek()[0] in _BASE_TYPE_TOKENS:
            type1 = self.advance()[1]
            if self.peek()[0] in _BASE_TYPE_TOKENS:
                type2 = self.advance()[1]
                type1 = f"{type1} {type2}"
            type1 = self._consume_pointer_stars(type1)
            return TypeExpr(type1)
        if self.peek()[0] == "STRUCT":
            self.advance()
            type_name = "struct"
            if self.peek()[0] == "IDENTIFIER":
                type_name += " " + self.advance()[1]
            return TypeExpr(type_name)
        raise SyntaxError(f"Expected type keyword, got {self.peek()}")

    def parse_generic(self) -> Node:
        """Parse a C11 _Generic expression: _Generic(expr, type1: val1, type2: val2, ...)."""
        self.expect("UNDERSCORE_GENERIC")
        self.expect("LPAREN")

        # Parse controlling expression - only consume up to the first top-level comma
        # that starts the associations list
        start = self.i
        paren_depth = 1
        while self.i < len(self.tokens):
            tok = self.tokens[self.i]
            if tok[0] == "LPAREN":
                paren_depth += 1
            elif tok[0] == "RPAREN":
                paren_depth -= 1
                if paren_depth == 0:
                    break
            elif tok[0] == "COMMA" and paren_depth == 1:
                break
            self.i += 1

        if self.i <= start:
            raise SyntaxError("Expected expression in _Generic")
        expr_tokens = self.tokens[start : self.i]
        self.i = start
        expr = self._parse_expr_from_tokens(expr_tokens)
        self.i = start + len(expr_tokens)

        # Now should be at COMMA (associations separator)
        associations = []
        while True:
            self.expect("COMMA")
            tok = self.peek()
            if tok[0] in _BASE_TYPE_TOKENS or tok[0] in ("DEFAULT", "IDENTIFIER"):
                assoc_type = self.advance()[1]
            else:
                assoc_type = self.expect("IDENTIFIER")[1]
            self.expect("COLON")
            assoc_value = self.parse_assignment()
            associations.append((assoc_type, assoc_value))
            if self.peek()[0] == "RPAREN":
                break
        self.expect("RPAREN")
        return Generic(expr=expr, associations=associations)

    def _parse_expr_from_tokens(self, tokens: list) -> Node:
        """Helper to parse a sub-expression from a token list."""
        parser = Parser(tokens)
        node = parser.parse_expression()
        return node

    def parse_primary(self) -> Node:
        """Parse the most basic expression forms."""
        tok = self.peek()
        if tok[0] == "IDENTIFIER":
            return Var(self.advance()[1])
        if tok[0] in (
            "INT_LITERAL",
            "FLOAT_LITERAL",
            "STRING_LITERAL",
            "CHAR_LITERAL",
            "HEX_LITERAL",
            "BINARY_LITERAL",
        ):
            return Literal(self.advance()[1])
        if tok[0] == "SIZEOF":
            self.advance()
            self.expect("LPAREN")
            if self.peek()[0] in _TYPE_TOKENS:
                type_node = self.parse_type_expression()
                self.expect("RPAREN")
                return Unary(op="sizeof", operand=type_node, prefix=True)
            if self.peek()[0] == "STRUCT":
                self.advance()
                type_name = "struct"
                if self.peek()[0] == "IDENTIFIER":
                    type_name += " " + self.advance()[1]
                self.expect("RPAREN")
                return Unary(op="sizeof", operand=TypeExpr(type_name), prefix=True)
            operand = self.parse_expression()
            self.expect("RPAREN")
            return Unary(op="sizeof", operand=operand, prefix=True)
        if tok[0] == "LBRACE":
            # Brace-init list in expression position
            return self.parse_init_list()
        if tok[0] == "LPAREN":
            self.advance()
            if self.peek()[0] in (
                "INT",
                "CHAR",
                "VOID",
                "FLOAT",
                "DOUBLE",
                "SHORT",
                "LONG",
                "SIGNED",
                "UNSIGNED",
                "CONST",
                "VOLATILE",
            ):
                type_node = self.parse_type_expression()
                while self.peek()[0] == "MULTIPLY":
                    self.advance()
                    type_node.type_name += "*"
                # Handle array type suffix: (int[])...
                if self.peek()[0] == "LBRACKET":
                    self.advance()  # consume '['
                    if self.peek()[0] == "RBRACKET":
                        # Flexible array member: type[]
                        type_node.type_name += "[]"
                    else:
                        # Fixed size: type[N]
                        size = self.expect("INT_LITERAL")[1]
                        type_node.type_name += f"[{size}]"
                    self.expect("RBRACKET")
                # Check for compound literal: (type){ ... }
                if self.peek()[0] == "LBRACE":
                    init_list = self.parse_init_list()
                    return CompoundLiteral(
                        lit_type=type_node.type_name, elements=init_list.elements
                    )
                self.expect("RPAREN")
                operand = self.parse_unary()
                return Cast(cast_type=type_node.type_name, operand=operand)
            expr = self.parse_expression()
            self.expect("RPAREN")
            return expr
        if tok[0] in _BASE_TYPE_TOKENS:
            return TypeExpr(self.advance()[1])
        if tok[0] == "UNDERSCORE_GENERIC":
            return self.parse_generic()
        raise SyntaxError(f"Unexpected token {tok} in primary expression")


# ============================================================
# Internal helpers
# ============================================================


class _MultiDecl:
    """Internal wrapper for comma-separated declarators at global scope.

    parse_program() unwraps these into individual Declaration nodes so
    Program.declarations remains a flat list.
    """

    def __init__(self, decls):
        self.decls = decls


# Patch parse_program to unwrap _MultiDecl nodes.
_orig_parse_program = Parser.parse_program


def _parse_program_unwrap(self) -> Program:
    decls_raw = []
    while self.peek()[0] != "EOF":
        node = self.parse_external()
        if isinstance(node, _MultiDecl):
            decls_raw.extend(node.decls)
        else:
            decls_raw.append(node)
    return Program(decls_raw)


Parser.parse_program = _parse_program_unwrap


# ============================================================
# AST Pretty Printer
# ============================================================


def pretty(node: Node, indent: int = 0) -> str:
    """Human-readable AST dump."""
    pad = "  " * indent
    return pad + repr(node) + "\n"


# ============================================================
# Entry point
# ============================================================


def main(tokens):
    """Parse tokens and print AST."""
    parser = Parser(tokens)
    ast = parser.parse_program()
    print(pretty(ast))


def _cast_literal(raw):
    """Try to cast a raw lexeme string to int or float."""
    if isinstance(raw, (int, float)):
        return raw
    try:
        return int(raw)
    except (ValueError, TypeError):
        pass
    try:
        return float(raw)
    except (ValueError, TypeError):
        pass
    return raw
