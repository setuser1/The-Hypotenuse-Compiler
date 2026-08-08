"""
C-like language parser and AST implementation.

This file defines:
- Abstract Syntax Tree (AST) node classes
- A recursive-descent parser with proper operator precedence
- A pretty-printer for AST visualization

The parser consumes tokens produced by an external lexer and builds
a structured AST suitable for semantic analysis or code generation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import re

import error_msgs

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
class UsingDecl(Node):
    """using statement for imports.

    item: specific item to import (None means import all)
    source: "<lib>" for system, "\"path\"" for local, "owner&name" for intra-file imports
    alias: optional rename
    """

    item: Optional[str]
    source: str
    alias: Optional[str] = None


@dataclass
class ExposeDecl(Node):
    """expose statement to globalize a namespace."""

    target: str


@dataclass
class LibAccess(Node):
    """lib:symbol - explicit plstd access."""

    symbol: str


@dataclass
class SpaceDecl(Node):
    """space statement to declare a namespace."""

    name: str
    declarations: List[Node]


@dataclass
class Function(Node):
    """Function definition."""

    ret_type: str  # Return type
    name: str  # Function identifier
    params: List[Tuple[str, str]]  # (type, name) parameter list
    body: Node  # Function body (Compound)


@dataclass
class AsmBlock(Node):
    """Inline assembly block."""

    ret_type: Optional[str]  # None for bare asm { }
    name: Optional[str]  # Function name or None for bare asm
    params: List[Tuple[str, str]]  # (type, name) parameter list
    lines: List[str]  # Raw assembly lines (excluding data)
    return_expr: Optional[str] = None  # Optional C△ return expression
    syntax: Optional[str] = None  # e.g., "x86_64_linux"
    is_function: bool = True  # True for asm int func(), False for bare asm { }
    variables: List[Dict] = field(default_factory=list)
    data_lines: List[str] = field(default_factory=list)


@dataclass
class Declaration(Node):
    """Variable declaration or function prototype."""

    var_type: str
    name: str
    initializer: Optional[Node]  # Optional initializer expression
    array_size: Optional[int] = (
        None  # Optional array size for declarations like char temp[32]
    )
    dimensions: Optional[List] = None  # For multi-dimensional arrays like int arr[2][3]


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
class Define(Node):
    """#define directive - stored for emission."""

    directive: str  # The full directive text


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
class Alloc(Node):
    """allocate keyword for heap allocation."""

    alloc_type: str  # The type being allocated (e.g., "int", "char", "string")
    name: str  # Variable name
    count: Optional[Node]  # Array element count (for `allocate int buf[64]`)
    byte_size: Optional[Node]  # Byte size (for `allocate int x(200)`)
    initializer: Optional[Node]  # Optional initializer (= val)


@dataclass
class Free(Node):
    """free keyword for heap deallocation."""

    expr: Node  # The pointer to free


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
class ArrayDesignation(Node):
    """C11 array element designator: [expr] = value or [start...end] = value"""

    index: Node
    value: Node
    is_range: bool = False  # True for [start...end] = val
    end_index: Optional[Node] = None  # End index for ranges


@dataclass
class Generic(Node):
    """C11 _Generic expression: _Generic(expr, type1: val1, type2: val2, ...)"""

    expr: Node
    associations: List[Tuple[str, Node]]  # (type, value) pairs


@dataclass
class Comma(Node):
    """Comma expression node."""

    left: Node
    right: Node


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
    "STRING",
    "BOOLEAN",
    "DYNAM",
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
    "DYNAM",
    "STRING",
    "BOOLEAN",
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

        Returns an ('EOF', '', 0, 0) sentinel when the token stream is exhausted
        so callers never receive an IndexError.
        """
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        return ("EOF", "", 0, 0)

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
        line = tok[2] if len(tok) > 2 else 0
        col = tok[3] if len(tok) > 3 else 0
        raise SyntaxError(
            error_msgs.get_error_msg(
                "E001",
                found=tok[0],
                expected=type_name,
                line=line,
                col=col,
                fallback=f"Expected {type_name} at line {line}, column {col}, got {tok[0]}",
            )
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

    def _make_decl_list(self, decls: List[Declaration]) -> Compound:
        """Create a synthetic declaration list that is not a lexical block."""
        node = Compound(decls)  # type: ignore[arg-type]
        setattr(node, "_is_decl_list", True)
        return node

    def _parse_local_declaration(self) -> Node:
        """Parse a local variable declaration inside a function."""
        # Handle qualifiers before base type: volatile string*, const int*
        qualifiers = []
        while self.peek()[0] in ("CONST", "VOLATILE"):
            qualifiers.append(self.advance()[1])
        typ = self.advance()[1]

        # Special handling for dynam type: "dynam <element_type>"
        if typ == "dynam":
            elem_typ = self.advance()[1]  # get element type like "int"
            # Check for additional type qualifiers
            while self.peek()[0] in _BASE_TYPE_TOKENS:
                next_tok = self.peek()
                if next_tok[0] in (
                    "INT_LITERAL",
                    "HEX_LITERAL",
                    "BINARY_LITERAL",
                    "OCTAL_LITERAL",
                    "CHAR_LITERAL",
                    "STRING_LITERAL",
                    "FLOAT_LITERAL",
                ):
                    break
                elem_typ2 = self.advance()[1]
                elem_typ = f"{elem_typ} {elem_typ2}"
            typ = f"dynam {elem_typ}"
        # Don't expand typedef aliases - keep original name for correct C output
        # Handle compound types: long long, unsigned long, etc.
        # Use while loop to handle multiple type qualifiers (long long)
        elif typ not in (
            "dynam",
            "string",
        ):  # Skip compound type handling for special types
            while self.peek()[0] in _BASE_TYPE_TOKENS:
                next_tok = self.peek()
                # Stop if we hit a literal (handles suffixes like ULL)
                if next_tok[0] in (
                    "INT_LITERAL",
                    "HEX_LITERAL",
                    "BINARY_LITERAL",
                    "OCTAL_LITERAL",
                    "CHAR_LITERAL",
                    "STRING_LITERAL",
                    "FLOAT_LITERAL",
                ):
                    break
                typ2 = self.advance()[1]
                typ = f"{typ} {typ2}"

        # Prepend qualifiers to type
        if qualifiers:
            typ = " ".join(qualifiers) + " " + typ
        # Handle string type - allow pointer to string
        if typ == "string":
            typ = self._consume_pointer_stars(typ)
        elif typ.startswith("dynam "):
            # dynam type: check for pointer to dynam or dynam of pointers
            # "dynam int*" = dynam array of int pointers
            # "dynam int**" = dynam array of pointers to pointers
            typ = self._consume_pointer_stars(typ)
        else:
            typ = self._consume_pointer_stars(typ)

        # Allow literals after compound types (e.g., unsigned long long x = 0xFF)
        if self.peek()[0] not in (
            "IDENTIFIER",
            "INT_LITERAL",
            "HEX_LITERAL",
            "BINARY_LITERAL",
            "OCTAL_LITERAL",
            "CHAR_LITERAL",
            "STRING_LITERAL",
            "FLOAT_LITERAL",
        ):
            bad_tok = self.peek()
            line = bad_tok[2] if len(bad_tok) > 2 else 0
            col = bad_tok[3] if len(bad_tok) > 3 else 0
            raise SyntaxError(
                error_msgs.get_error_msg(
                    "E008",
                    found=bad_tok[0],
                    line=line,
                    col=col,
                    fallback=f"Expected identifier at line {line}, column {col}. Got '{bad_tok[0]}'.",
                )
            )
        name = self.expect("IDENTIFIER")[1]

        # Support multi-dimensional arrays: int arr[2][3], int arr[][3] = {{1,2,3}}
        dimensions = []
        while self.accept("LBRACKET"):
            if self.peek()[0] == "RBRACKET":
                # Empty dimension
                dimensions.append(None)
                self.expect("RBRACKET")
            elif self.peek()[0] == "INT_LITERAL":
                dimensions.append(int(self.advance()[1]))
                self.expect("RBRACKET")
            elif self.peek()[0] == "IDENTIFIER":
                dimensions.append(self.advance()[1])
                self.expect("RBRACKET")
            else:
                dimensions.append(None)
                self.expect("RBRACKET")

        # Determine primary array size from first dimension
        array_size = dimensions[0] if dimensions else None
        # Store all dimensions for codegen (always keep for inference)
        full_dims = dimensions if dimensions else None

        init = None
        if self.accept("ASSIGN"):
            # Check for dynam array initializer: [1, 2, 3]
            if self.peek()[0] == "LBRACKET" and typ.startswith("dynam"):
                init = self.parse_array_initializer()
            else:
                init = self.parse_assignment()
        elif self.peek()[0] == "LBRACE":
            init = self.parse_init_list()

        decls = [Declaration(typ, name, init, array_size, full_dims)]

        while self.accept("COMMA"):
            extra_name = self.expect("IDENTIFIER")[1]
            extra_init = None
            if self.accept("ASSIGN"):
                extra_init = self.parse_assignment()
            elif self.peek()[0] == "LBRACE":
                extra_init = self.parse_init_list()
            decls.append(Declaration(typ, extra_name, extra_init))

        self.expect("SEMICOLON")

        if len(decls) == 1:
            return decls[0]
        return self._make_decl_list(decls)

    # ============================================================
    # Top-level parsing
    # ============================================================

    def parse_program(self) -> Program:
        """Parse entire translation unit."""
        decls = []
        while self.peek()[0] != "EOF":
            node = self.parse_external()
            if node is not None:
                decls.append(node)
        return Program(decls)

    def _parse_preprocessor(self, directive: str) -> Optional[Node]:
        """Parse a preprocessor directive."""
        stripped = directive.strip()
        stripped = re.sub(r'^#\s+', '#', stripped)
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
        elif stripped.startswith("#define"):
            return Define(directive)
        # For other preprocessor directives (#if, #ifdef, #ifndef, #endif, etc.)
        # Return the directive as-is to be emitted
        return Define(directive)

    def parse_external(self) -> Optional[Node]:
        """
        Parse global declarations:
        - Functions
        - Function prototypes
        - Global variables
        - Include directives
        - Namespace blocks (space)
        """
        t = self.peek()

        # Handle namespace blocks (space)
        if t[0] == "SPACE":
            return self.parse_space()

        # Handle asm blocks
        if t[0] == "ASM":
            return self.parse_asm_block()

        # Handle preprocessor directives
        if t[0] == "PREPROCESSOR":
            directive = self.advance()[1]
            result = self._parse_preprocessor(directive)
            if result is not None:
                return result
            return self.parse_external()

        # Skip comments iteratively to avoid stack overflow
        while t[0] in ("COMMENT_MULTI", "COMMENT_LINE"):
            self.advance()
            t = self.peek()

        # Reject deprecated / removed keywords immediately.
        if t[0] in (
            "RESTRICT",
            "BOOLEAN",
            "UNDERSCORE_ALIGNOF",
            "UNDERSCORE_ALIGNAS",
            "UNDERSCORE_COMPLEX",
            "UNDERSCORE_IMAGINARY",
        ):
            line = t[2] if len(t) > 2 else 0
            col = t[3] if len(t) > 3 else 0
            raise SyntaxError(
                error_msgs.get_error_msg(
                    "E001",
                    found=t[0],
                    line=line,
                    col=col,
                    fallback=f"Deprecated keyword used at line {line}, column {col}! Found '{t[0]}'.",
                )
            )

        if t[0] == "USING":
            return self.parse_using()

        if t[0] == "EXPOSE":
            return self.parse_expose()

        if t[0] == "SPACE":
            return self.parse_space()

        if t[0] == "EXTERN":
            next_idx = self.i + 1
            if (next_idx < len(self.tokens)
                and self.tokens[next_idx][0] == "STRING_LITERAL"
                and self.tokens[next_idx][1].strip('"') in ("C", "c")):
                return self.parse_extern_c_block()

        if t[0] == "TYPEDEF":
            return self.parse_typedef()

        if t[0] == "STRUCT":
            return self.parse_struct_definition()

        if t[0] == "UNION":
            return self.parse_union_definition()

        if t[0] == "ENUM":
            return self.parse_enum_definition()

        if t[0] == "ALLOCATE":
            self.advance()
            alloc_type = self.advance()[1]
            while self.peek()[0] in (
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
            ):
                alloc_type += " " + self.advance()[1]
            while self.peek()[0] == "MULTIPLY":
                alloc_type += "*"
                self.advance()
            name = self.expect("IDENTIFIER")[1]
            count = None
            byte_size = None
            if self.accept("LBRACKET"):
                if self.peek()[0] == "INT_LITERAL":
                    count = Literal(int(self.advance()[1]))
                self.expect("RBRACKET")
            elif self.accept("LPAREN"):
                if self.peek()[0] == "INT_LITERAL":
                    byte_size = Literal(int(self.advance()[1]))
                self.expect("RPAREN")
            init = None
            if self.accept("ASSIGN"):
                init = self.parse_assignment()
            self.expect("SEMICOLON")
            return Alloc(alloc_type, name, count, byte_size, init)

        if t[0] in _TYPE_TOKENS or t[0] == "IDENTIFIER":
            if t[0] == "IDENTIFIER" and t[1] not in self._typedefs:
                next_tok = (
                    self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
                )
                if not next_tok or next_tok[0] not in (
                    "LPAREN",
                    "MULTIPLY",
                    "IDENTIFIER",
                    "LBRACKET",
                ):
                    line = t[2] if len(t) > 2 else 0
                    col = t[3] if len(t) > 3 else 0
                    raise SyntaxError(
                        error_msgs.get_error_msg(
                            "E001",
                            found=t[1],
                            line=line,
                            col=col,
                            fallback=f"Unexpected identifier at line {line}, column {col}: '{t[1]}'",
                        )
                    )
            # Handle qualifiers before base type: volatile string*, const int*
            qualifiers = []
            while self.peek()[0] in ("CONST", "VOLATILE"):
                qualifiers.append(self.advance()[1])
            typ = self.advance()[1]
            # Don't expand typedef aliases - keep original name for correct C output
            # Prepend qualifiers to type
            if qualifiers:
                typ = " ".join(qualifiers) + " " + typ
            # Handle storage class specifiers (extern, static, auto, register)
            # These are consumed but not added to the type
            while self.peek()[0] in ("EXTERN", "STATIC", "AUTO", "REGISTER"):
                self.advance()
            # Handle compound types: long long, unsigned long, etc.
            # Stop at literals (INT_LITERAL, HEX_LITERAL, etc.) or other non-type tokens
            while self.peek()[0] in _BASE_TYPE_TOKENS:
                next_tok = self.peek()
                if next_tok[0] in (
                    "INT_LITERAL",
                    "HEX_LITERAL",
                    "BINARY_LITERAL",
                    "OCTAL_LITERAL",
                    "CHAR_LITERAL",
                    "STRING_LITERAL",
                    "FLOAT_LITERAL",
                ):
                    break
                typ2 = self.advance()[1]
                typ = f"{typ} {typ2}"

            # Handle function specifiers (inline, noreturn)
            while self.peek()[0] in ("INLINE", "NORETURN"):
                spec = self.advance()[1]
                typ = f"{spec} {typ}"

            # Handle pointer type: int* ptr or int** ptr2
            typ = self._consume_pointer_stars(typ)
            # Expected Identifier error handling
            # Check if next token is a literal (not a type or identifier) - this can happen after compound types
            valid_initializer_start = self.peek()[0] in (
                "INT_LITERAL",
                "HEX_LITERAL",
                "BINARY_LITERAL",
                "OCTAL_LITERAL",
                "CHAR_LITERAL",
                "STRING_LITERAL",
                "FLOAT_LITERAL",
            )
            if not valid_initializer_start and self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                line = bad_tok[2] if len(bad_tok) > 2 else 0
                col = bad_tok[3] if len(bad_tok) > 3 else 0
                raise SyntaxError(
                    error_msgs.get_error_msg(
                        "E008",
                        found=bad_tok[0],
                        keyword=typ,
                        line=line,
                        col=col,
                        fallback=f"Expected identifier at line {line}, column {col}. Got '{bad_tok[0]}'.",
                    )
                )
            name = self.advance()[1]
            # Function or prototype
            if self.accept("LPAREN"):
                params = []

                if not self.accept("RPAREN"):
                    if self.peek()[0] == "VOID":
                        self.advance()
                        self.expect("RPAREN")
                    else:
                        while True:
                            if self.accept("ELLIPSIS"):
                                params.append(("...", "..."))
                                self.expect("RPAREN")
                                break

                            qualifiers = []
                            while self.peek()[0] in ("CONST", "VOLATILE"):
                                qualifiers.append(self.advance()[1])

                            ptype = self.advance()[1]
                            # Don't expand typedef aliases - keep original name
                            if self.peek()[0] in _BASE_TYPE_TOKENS:
                                ptype = f"{ptype} {self.advance()[1]}"

                            ptype = self._consume_pointer_stars(ptype)
                            if qualifiers:
                                ptype = " ".join(qualifiers) + " " + ptype

                            pname = self.expect("IDENTIFIER")[1]
                            params.append((ptype, pname, None))

                            if self.accept("COMMA"):
                                continue
                            self.expect("RPAREN")
                            break

                if self.peek()[0] == "LBRACE":
                    return Function(typ, name, params, self.parse_compound())
                self.expect("SEMICOLON")
                return Declaration(f"{typ} (prototype)", name, None)

            # Global variable
            array_size = None
            full_dims = None
            sizes = []
            while self.accept("LBRACKET"):
                if self.peek()[0] == "RBRACKET":
                    # Empty dimension - mark as None for inference
                    sizes.append(None)
                    self.expect("RBRACKET")
                elif self.peek()[0] == "INT_LITERAL":
                    sizes.append(int(self.advance()[1]))
                    self.expect("RBRACKET")
                elif self.peek()[0] == "IDENTIFIER":
                    # Handle macro constants in array sizes
                    ident = self.advance()[1]
                    sizes.append(ident)
                    self.expect("RBRACKET")
                else:
                    sizes.append(None)
                    self.expect("RBRACKET")
            if len(sizes) > 0:
                array_size = sizes[0] if len(sizes) == 1 else sizes
                # Store full dimensions for inference
                full_dims = sizes if len(sizes) > 1 else sizes

            init = self.parse_assignment() if self.accept("ASSIGN") else None
            decls = [Declaration(typ, name, init, array_size, full_dims)]  # type: ignore[arg-type]
            while self.accept("COMMA"):
                extra_name = self.expect("IDENTIFIER")[1]
                # Handle multi-dimensional array in comma-separated list
                extra_sizes = []
                while self.accept("LBRACKET"):
                    if self.peek()[0] == "RBRACKET":
                        extra_sizes.append(None)
                        self.expect("RBRACKET")
                    elif self.peek()[0] == "INT_LITERAL":
                        extra_sizes.append(int(self.advance()[1]))
                        self.expect("RBRACKET")
                    elif self.peek()[0] == "IDENTIFIER":
                        ident = self.advance()[1]
                        extra_sizes.append(ident)
                        self.expect("RBRACKET")
                    else:
                        extra_sizes.append(None)
                        self.expect("RBRACKET")
                extra_array_size = (
                    extra_sizes[0]
                    if len(extra_sizes) == 1
                    else extra_sizes
                    if extra_sizes
                    else None
                )
                extra_full_dims = extra_sizes if extra_sizes else None
                extra_init = self.parse_assignment() if self.accept("ASSIGN") else None
                decls.append(
                    Declaration(  # type: ignore[arg-type]
                        typ,
                        extra_name,
                        extra_init,
                        extra_array_size,  # type: ignore[arg-type]
                        extra_full_dims,  # type: ignore[arg-type]
                    )
                )
            self.expect("SEMICOLON")
            if len(decls) == 1:
                return decls[0]
            # Wrap multiple declarators in a synthetic Compound so the caller
            # gets a single node (Program.declarations is a flat list, so we
            # extend it below instead).
            return _MultiDecl(decls)  # type: ignore

    def parse_using(self) -> UsingDecl:
        """Parse a using statement.

        Forms:
            using "x"           # import all from local
            using "x" as y      # import all with alias
            using X from <Y>    # import specific from system
            using X from "Y"    # import specific from local
            using X from <Y> as Z  # import with alias
            using owner&X       # import X from owner
            using main&X        # import X from main
            using foo&X as Y    # import X from foo as Y
        """
        self.expect("USING")
        t = self.peek()

        # Check for X& form (import from scoped, where X is any identifier like main, foo, etc.)
        # Supports chained scopes: using a&b&c&symbol
        if t[0] == "IDENTIFIER":
            next_tok = (
                self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok[0] == "AMPERSAND":
                # This is a scoped import: using X&Y or using a&b&c&Y
                scope_parts = []
                # Collect the first identifier
                scope_parts.append(self.advance()[1])
                # Loop through all ampersands
                while self.peek()[0] == "AMPERSAND":
                    self.expect("AMPERSAND")
                    # Can be IDENTIFIER or another scope reference
                    if self.peek()[0] == "IDENTIFIER":
                        scope_parts.append(self.advance()[1])
                    else:
                        break
                # Build source string from parts
                source = "&".join(scope_parts)
                alias = self._parse_optional_alias()
                # Semicolon is optional for using statements
                if self.peek()[0] == "SEMICOLON":
                    self.expect("SEMICOLON")
                return UsingDecl(item=None, source=source, alias=alias)

        # Check if we're importing a specific item (identifier before "from")
        if t[0] == "IDENTIFIER":
            next_tok = (
                self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok[0] == "FROM":
                # Item specified: using X from ...
                item = self.advance()[1]
                self.expect("FROM")
                source = self._parse_import_source()
                alias = self._parse_optional_alias()
                # Semicolon is optional for using statements
                if self.peek()[0] == "SEMICOLON":
                    self.expect("SEMICOLON")
                return UsingDecl(item=item, source=source, alias=alias)
            elif next_tok and next_tok[0] == "AS":
                # Direct import with alias: using "x" as y
                source = self.advance()[1]
                alias = self._parse_optional_alias()
                # Semicolon is optional for using statements
                if self.peek()[0] == "SEMICOLON":
                    self.expect("SEMICOLON")
                return UsingDecl(item=None, source=source, alias=alias)

        # Check for string literal (import all from local)
        if t[0] == "STRING_LITERAL":
            source = self.advance()[1].strip('"')
            alias = self._parse_optional_alias()
            # Semicolon is optional for using statements
            if self.peek()[0] == "SEMICOLON":
                self.expect("SEMICOLON")
            return UsingDecl(item=None, source=source, alias=alias)

        # Check for system lib <x>
        if t[0] == "LT":
            source = self._parse_import_source()
            alias = self._parse_optional_alias()
            # Semicolon is optional for using statements
            if self.peek()[0] == "SEMICOLON":
                self.expect("SEMICOLON")
            return UsingDecl(item=None, source=source, alias=alias)

        line = t[2] if len(t) > 2 else 0
        col = t[3] if len(t) > 3 else 0
        raise SyntaxError(
            error_msgs.get_error_msg(
                "E001",
                found=t[1],
                line=line,
                col=col,
                fallback=f"Invalid using statement at line {line}, column {col}",
            )
        )

    def _parse_import_source(self) -> str:
        """Parse the source of an import: <lib> or <lib/sublib> or "path"."""
        t = self.peek()
        if t[0] == "LT":
            self.expect("LT")
            # Handle both IDENTIFIER and PLSTD (plstd is a reserved keyword)
            if self.peek()[0] == "PLSTD":
                lib_name = self.expect("PLSTD")[1]
            else:
                lib_name = self.expect("IDENTIFIER")[1]

            # Handle path-like imports: <plstd/printd>
            while self.peek()[0] == "DIVIDE":
                self.expect("DIVIDE")
                if self.peek()[0] == "PLSTD":
                    lib_name += "/" + self.expect("PLSTD")[1]
                else:
                    lib_name += "/" + self.expect("IDENTIFIER")[1]

            self.expect("GT")
            return f"<{lib_name}>"
        elif t[0] == "STRING_LITERAL":
            return self.advance()[1].strip('"')
        else:
            line = t[2] if len(t) > 2 else 0
            col = t[3] if len(t) > 3 else 0
            raise SyntaxError(
                error_msgs.get_error_msg(
                    "E001",
                    found=t[1],
                    line=line,
                    col=col,
                    fallback=f"Invalid import source at line {line}, column {col}",
                )
            )

    def _parse_optional_alias(self) -> Optional[str]:
        """Parse optional 'as' alias."""
        if self.accept("AS"):
            return self.expect("IDENTIFIER")[1]
        return None

    def _parse_lib_call(self, symbol: str) -> Node:
        """Parse a lib~symbol(...) call."""
        self.expect("LPAREN")
        args = []
        if self.peek()[0] != "RPAREN":
            args.append(self.parse_assignment())
            while self.accept("COMMA"):
                args.append(self.parse_assignment())
        self.expect("RPAREN")
        # Convert to a Call node with lib~ prefix
        return Call(callee=Var(f"lib~{symbol}"), args=args)

    def parse_expose(self) -> Optional[ExposeDecl]:
        """Parse an expose statement: expose namespace or expose func@namespace."""
        self.expect("EXPOSE")
        t = self.peek()
        # Accept IDENTIFIER or keywords (like STRING) as valid targets
        if t[0] in ("IDENTIFIER", "STRING", "PLSTD") or t[0].endswith("_KEYWORD"):
            target = self.advance()[1]
            # Check for @ syntax like expose printd@plstd or expose printd@lib
            if self.peek()[0] == "AT":
                self.expect("AT")
                # Can be IDENTIFIER or PLSTD for the namespace
                if self.peek()[0] == "PLSTD":
                    namespace = self.advance()[1]
                else:
                    namespace = self.expect("IDENTIFIER")[1]
                target = f"{target}@{namespace}"
            # Semicolon is optional for expose statements
            if self.peek()[0] == "SEMICOLON":
                self.expect("SEMICOLON")
            return ExposeDecl(target=target)
        elif t[0] == "PLSTD":
            self.advance()
            # Semicolon is optional for expose statements
            if self.peek()[0] == "SEMICOLON":
                self.expect("SEMICOLON")
            return ExposeDecl(target="plstd")

        return None  # type: ignore

    def parse_asm_block(self) -> "AsmBlock":
        """Parse an inline assembly block."""
        self.expect("ASM")

        # Check if this is a bare asm block (asm { }) or function asm block (asm int func() { })
        ret_type = None
        name = None
        params = []
        is_function = True

        if self.peek()[0] == "LBRACE":
            # Bare asm block - no return type, name, or params
            is_function = False
        else:
            # Asm function - parse return type
            ret_type = self.advance()[1]
            if self.peek()[0] == "MULTIPLY":
                self.advance()
                ret_type = ret_type + "*"
            # Parse function name
            name = self.expect("IDENTIFIER")[1]
            # Parse parameters
            self.expect("LPAREN")
            if self.peek()[0] != "RPAREN":
                while True:
                    param_type = self.advance()[1]
                    if self.peek()[0] == "MULTIPLY":
                        self.advance()
                        param_type = param_type + "*"
                    param_name = self.expect("IDENTIFIER")[1]
                    params.append((param_type, param_name))
                    if self.peek()[0] == "COMMA":
                        self.advance()
                    else:
                        break
            self.expect("RPAREN")

        # Parse body
        self.expect("LBRACE")
        lines = []
        variables = []
        data_lines = []
        return_expr = None
        syntax = None

        while self.peek()[0] != "RBRACE":
            if self.peek()[0] == "EOF":
                raise SyntaxError("Unclosed asm block - missing '}'")

            # Skip standalone semicolons (C△ statement terminators or comments)
            if self.peek()[0] == "SEMICOLON":
                semicolon_line = self.peek()[2] if len(self.peek()) > 2 else 0
                self.advance()
                # Skip everything else on this line
                while self.peek()[0] not in ("EOF", "RBRACE"):
                    tok = self.peek()
                    tok_line = tok[2] if len(tok) > 2 else 0
                    if tok_line > semicolon_line:
                        break  # New line started
                    self.advance()
                continue

            # Check for syntax declaration: syntax x86_64_elf or syntax arm64_macho
            if self.peek()[0] == "IDENTIFIER" and self.peek()[1] == "syntax":
                self.advance()  # consume 'syntax'
                if self.peek()[0] == "IDENTIFIER":
                    syntax = self.advance()[1]
                continue

            # Check for C△ variable declarations. ASM blocks allow declarations
            # anywhere; they are emitted into the generated data section.
            if self.peek()[0] in (
                "STRING",
                "BOOLEAN",
                "INT",
                "CHAR",
                "FLOAT",
                "DOUBLE",
                "SHORT",
                "LONG",
            ):
                var_info = self._read_ctri_declaration()
                if var_info:
                    variables.append(var_info)
                    data_lines.append(var_info["asm_line"])
                continue

            # Check for return statement
            if self.peek()[0] == "RETURN":
                self.advance()
                # Check if there's an expression after return (optional)
                if self.peek()[0] not in ("SEMICOLON", "RBRACE", "EOF"):
                    # Parse the return expression until end of line or brace
                    expr_parts = []
                    paren_depth = 0
                    first_expr_line = None
                    while self.peek()[0] != "RBRACE" and self.peek()[0] != "EOF":
                        tok = self.peek()
                        tok_line = tok[2] if len(tok) > 2 else 0
                        if first_expr_line is None:
                            first_expr_line = tok_line
                        elif tok_line > first_expr_line:
                            break
                        if tok[0] == "SEMICOLON" and paren_depth == 0:
                            self.advance()
                            break
                        if tok[0] == "LPAREN":
                            paren_depth += 1
                        elif tok[0] == "RPAREN":
                            paren_depth -= 1
                        elif tok[0] == "LBRACKET":
                            paren_depth += 1
                        elif tok[0] == "RBRACKET":
                            paren_depth -= 1
                        expr_parts.append(tok[1])
                        self.advance()
                    return_expr = " ".join(expr_parts).strip()
                else:
                    return_expr = ""
                    if self.peek()[0] == "SEMICOLON":
                        self.advance()
                continue  # don't add return to lines

            # Check for C△ function call (call func(args))
            if self.peek()[0] == "IDENTIFIER" and self.peek()[1] == "call":
                call_lines = self._read_ctri_call()
                lines.extend(call_lines)
                continue

            # Collect the line as-is
            line = self._read_asm_line()
            if line:
                lines.append(line)

        self.expect("RBRACE")
        self._validate_asm_sections(lines, syntax, name)

        return AsmBlock(
            ret_type=ret_type,
            name=name,
            params=params,
            lines=lines,
            return_expr=return_expr,
            syntax=syntax,
            is_function=is_function,
            variables=variables,
            data_lines=data_lines,
        )

    def _validate_asm_sections(
        self, lines: List[str], syntax: Optional[str], name: Optional[str]
    ):
        """Require an explicit text section directive that matches the asm syntax."""
        syntax_name = (syntax or "").lower()
        normalized_lines = [line.strip().lower() for line in lines]
        compact_lines = [line.replace(" ", "") for line in normalized_lines]
        has_arm64_macho_text = any(
            line == ".section__text,__text" for line in compact_lines
        )
        has_generic_text = any(
            line in ("section .text", ".section .text") for line in normalized_lines
        )

        if "arm64" in syntax_name and "macho" in syntax_name:
            if has_arm64_macho_text:
                return
            block_name = name or "<asm>"
            raise SyntaxError(
                f"asm block '{block_name}' uses syntax {syntax}, so it must declare "
                ".section __TEXT,__text"
            )

        if has_generic_text:
            return

        block_name = name or "<asm>"
        expected = (
            ".section __TEXT,__text"
            if "arm64" in syntax_name and "macho" in syntax_name
            else "section .text"
        )
        raise SyntaxError(
            f"asm block '{block_name}' must declare an explicit text section for its syntax: {expected}"
        )

    def _read_asm_line(self) -> str:
        """Read a single line of assembly (until newline or closing brace)."""
        parts = []
        depth = 0
        last_tok_type = None
        first_line = None
        while True:
            tok = self.peek()
            if tok[0] == "EOF":
                raise SyntaxError("Unclosed asm block - missing '}'")
            if tok[0] == "RBRACE" and depth == 0:
                break
            if tok[0] == "SEMICOLON" and depth == 0:
                # Skip comment text after semicolon (rest of this line)
                semicolon_line = tok[2] if len(tok) > 2 else 0
                self.advance()
                while self.peek()[0] not in ("EOF", "RBRACE"):
                    next_tok = self.peek()
                    next_line = next_tok[2] if len(next_tok) > 2 else 0
                    if next_line > semicolon_line:
                        break
                    self.advance()
                break
            tok_line = tok[2] if len(tok) > 2 else 0
            if first_line is not None and tok_line > first_line:
                break
            if first_line is None:
                first_line = tok_line
            if tok[0] == "LPAREN":
                depth += 1
            elif tok[0] == "RPAREN":
                depth -= 1

            tok_type = tok[0]
            tok_text = tok[1]

            if tok_type == "DOT":
                next_tok = (
                    self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
                )
                if next_tok and next_tok[0] == "IDENTIFIER":
                    combined = "." + next_tok[1]
                    if parts and parts[-1] != ".":
                        parts.append(" ")
                    parts.append(combined)
                    self.advance()
                    self.advance()
                    last_tok_type = "DIRECTIVE"
                    continue

            needs_space_before = (
                tok_type
                in ("IDENTIFIER", "INT_LITERAL", "HEX_LITERAL", "BINARY_LITERAL")
                and parts
                and last_tok_type
                not in (
                    "INT_LITERAL",
                    "HEX_LITERAL",
                    "BINARY_LITERAL",
                    "LPAREN",
                    "LBRACKET",
                    "DOT",
                )
            )
            if needs_space_before:
                parts.append(" ")

            parts.append(tok_text)
            last_tok_type = tok_type
            self.advance()
        return "".join(parts).strip()

    def _read_ctri_declaration(self) -> Optional[Dict]:
        """Parse a C△ variable declaration and return info dict."""
        tok = self.peek()
        var_type = tok[1]
        self.advance()

        # Get variable name
        var_name = self.expect("IDENTIFIER")[1]

        # Check for array declaration: IDENTIFIER[INT_LITERAL]
        array_size = None
        if self.peek()[0] == "LBRACKET":
            self.advance()  # [
            size_tok = self.expect("INT_LITERAL")
            self.expect("RBRACKET")  # ]
            array_size = int(size_tok[1])

        # Expect assignment
        self.expect("ASSIGN")

        # Parse value based on type
        tok = self.peek()
        initializer = None
        nasm_directive = None

        type_to_nasm = {
            "char": "db",
            "short": "dw",
            "int": "dd",
            "long": "dd",
            "float": "dd",
            "double": "dq",
        }

        if var_type == "string":
            if tok[0] == "STRING_LITERAL":
                value = tok[1][1:-1]  # Remove quotes
                escape_map = {"\\n": "\n", "\\t": "\t", "\\\\": "\\", '\\"': '"'}
                for esc, replacement in escape_map.items():
                    value = value.replace(esc, replacement)
                bytes_list = [str(ord(c)) for c in value]
                bytes_str = ", ".join(bytes_list) + ", 0"
                nasm_directive = f"db {bytes_str}"
                initializer = value
                self.advance()
        elif var_type == "char":
            if array_size:
                # char array
                if tok[0] == "STRING_LITERAL":
                    value = tok[1][1:-1]
                    bytes_list = [str(ord(c)) for c in value]
                    nasm_directive = f"db {', '.join(bytes_list)}"
                    initializer = value
                    self.advance()
                elif tok[0] == "INT_LITERAL":
                    initializer = tok[1]
                    nasm_directive = f"times {array_size} dup({initializer})"
                    self.advance()
            else:
                # char scalar
                if tok[0] == "CHAR_LITERAL":
                    initializer = str(ord(tok[1][1:-1]))
                    nasm_directive = f"db {initializer}"
                    self.advance()
                elif tok[0] == "INT_LITERAL":
                    initializer = tok[1]
                    nasm_directive = "db " + initializer
                    self.advance()
        elif var_type in ("int", "short", "long", "float", "double"):
            nasm_type = type_to_nasm.get(var_type, "dd")
            if tok[0] == "INT_LITERAL":
                initializer = tok[1]
                if array_size:
                    nasm_directive = f"times {array_size} dup({initializer})"
                else:
                    nasm_directive = f"{nasm_type} {initializer}"
                self.advance()
            elif tok[0] == "FLOAT_LITERAL":
                initializer = tok[1]
                if array_size:
                    nasm_directive = f"times {array_size} dup({initializer})"
                else:
                    nasm_directive = f"{nasm_type} {initializer}"
                self.advance()

        if nasm_directive:
            if self.peek()[0] == "SEMICOLON":
                self.advance()
            return {
                "name": var_name,
                "type": var_type,
                "size": array_size,
                "initializer": initializer,
                "nasm_directive": nasm_directive,
                "asm_line": f"{var_name}: {nasm_directive}",
            }
        return None

    def _read_ctri_call(self) -> List[str]:
        """Parse a C△ function call and return list of assembly lines."""
        self.expect("IDENTIFIER")  # consume 'call'
        func_name = self.advance()[1]
        self.expect("LPAREN")

        # Parse arguments
        args = []
        if self.peek()[0] != "RPAREN":
            while True:
                tok = self.peek()
                if tok[0] == "INT_LITERAL":
                    args.append(("imm", tok[1]))
                    self.advance()
                elif tok[0] == "IDENTIFIER":
                    args.append(("reg", tok[1]))
                    self.advance()
                elif tok[0] == "CHAR_LITERAL":
                    args.append(("imm", str(ord(tok[1][1:-1]))))
                    self.advance()
                else:
                    # Just consume the token as-is
                    args.append(("expr", tok[1]))
                    self.advance()

                if self.peek()[0] == "COMMA":
                    self.advance()
                else:
                    break

        self.expect("RPAREN")
        # Don't expect semicolon - asm lines don't need them

        # Generate assembly for function call
        lines = []
        # Register argument order for x86_64 System V ABI
        arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        for i, (arg_type, arg_val) in enumerate(args):
            if i < len(arg_regs):
                if arg_type == "imm":
                    lines.append(f"    mov {arg_regs[i]}, {arg_val}")
                elif arg_type == "reg":
                    lines.append(f"    mov {arg_regs[i]}, {arg_val}")
                else:
                    lines.append(f"    mov {arg_regs[i]}, {arg_val}")

        lines.append(f"    call {func_name}")
        return lines

    def parse_extern_c_block(self):
        """Skip contents of extern "C" { } block (no-op in C)."""
        self.advance()  # skip extern
        self.advance()  # skip "C"
        if self.peek()[0] != "LBRACE":
            return None
        self.advance()  # skip {
        depth = 1
        while self.peek()[0] != "EOF":
            if self.peek()[0] == "LBRACE":
                depth += 1
            elif self.peek()[0] == "RBRACE":
                depth -= 1
                if depth == 0:
                    self.advance()  # skip closing }
                    return None
            self.advance()
        raise SyntaxError("Unclosed extern \"C\" block - missing '}'")

    def parse_space(self) -> SpaceDecl:
        """Parse a namespace block declaration."""
        self.expect("SPACE")
        t = self.peek()
        if t[0] == "IDENTIFIER" or t[0] == "PLSTD":
            name = self.advance()[1]
            self.expect("LBRACE")
            declarations = []
            while True:
                if self.peek()[0] == "RBRACE":
                    self.advance()
                    break
                if self.peek()[0] == "EOF" or self.i >= len(self.tokens):
                    raise SyntaxError(f"Unexpected end of input inside space '{name}'")
                node = self.parse_external()
                if node is not None:
                    declarations.append(node)
            return SpaceDecl(name=name, declarations=declarations)
        else:
            line = t[2] if len(t) > 2 else 0
            col = t[3] if len(t) > 3 else 0
            raise SyntaxError(
                error_msgs.get_error_msg(
                    "E001",
                    found=t[1],
                    line=line,
                    col=col,
                    fallback=f"Invalid space statement at line {line}, column {col}",
                )
            )

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
                if self.i + 1 < len(self.tokens) and self.tokens[self.i + 1][0] == "SEMICOLON":
                    break
                actual_type += self.advance()[1] + " "
            elif tok[0] == "STRUCT":
                actual_type += self.advance()[1]
                if self.peek()[0] == "IDENTIFIER":
                    actual_type += " " + self.advance()[1]
                if self.peek()[0] == "LBRACE":
                    actual_type += " " + self.advance()[1]
                    depth = 1
                    while depth > 0:
                        inner_tok = self.peek()
                        if inner_tok[0] == "LBRACE":
                            depth += 1
                        elif inner_tok[0] == "RBRACE":
                            depth -= 1
                        actual_type += " " + self.advance()[1]
                    # BUG FIX: Don't consume the typedef alias here
                    # if self.peek()[0] == "IDENTIFIER":
                    #     actual_type += " " + self.advance()[1]
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
                    raise SyntaxError(
                        error_msgs.get_error_msg(
                            "E602",
                            file="struct",
                            fallback="Unexpected end of file: unclosed struct",
                        )
                    )
                field_type = ""
                while self.peek()[0] in _BASE_TYPE_TOKENS:
                    field_type += self.advance()[1] + " "
                    if self.peek()[0] in _BASE_TYPE_TOKENS:
                        field_type += self.advance()[1] + " "
                # Handle typedef/identifier types (e.g., socklen_t, mode_t)
                # Only if no base types were found
                if not field_type.strip() and self.peek()[0] == "IDENTIFIER":
                    field_type = self.advance()[1]
                # Handle STRUCT as a field type (nested anonymous struct)
                if not field_type.strip() and self.peek()[0] == "STRUCT":
                    self.advance()  # consume STRUCT
                    if self.peek()[0] == "IDENTIFIER":
                        # struct TypeName field; - named struct type
                        struct_name = self.advance()[1]
                        field_type = f"struct {struct_name}"
                    elif self.peek()[0] == "LBRACE":
                        # struct { ... } field; - anonymous struct type
                        self.advance()  # consume LBRACE
                        brace_depth = 1
                        while brace_depth > 0:
                            if self.peek()[0] == "EOF":
                                raise SyntaxError(
                                    error_msgs.get_error_msg(
                                        "E602",
                                        file="struct",
                                        fallback="Unexpected end of file: unclosed struct",
                                    )
                                )
                            tok = self.advance()
                            if tok[0] == "LBRACE":
                                brace_depth += 1
                            elif tok[0] == "RBRACE":
                                brace_depth -= 1
                        field_type = "struct { anonymous }"
                    else:
                        field_type = "struct"
                field_type = field_type.strip()
                field_type = self._consume_pointer_stars(field_type)
                field_name = self.expect("IDENTIFIER")[1]
                # Collect all field names separated by commas
                field_names = [field_name]
                while self.accept("COMMA"):
                    field_name = self.expect("IDENTIFIER")[1]
                    field_names.append(field_name)
                # Support array fields: int arr[5], int arr[], char s[]
                for fn in field_names:
                    array_suffix = ""
                    while self.accept("LBRACKET"):
                        dim = self.advance()[1] if self.peek()[0] != "RBRACKET" else ""
                        array_suffix += f"[{dim}]"
                        self.expect("RBRACKET")
                    full_name = f"{fn}{array_suffix}" if array_suffix else fn
                    fields.append((field_type, full_name))
                self.expect("SEMICOLON")
            self.expect("RBRACE")
            self.expect("SEMICOLON")
            return StructDef(name=name, fields=fields, is_anonymous=is_anonymous)
        elif self.peek()[0] == "SEMICOLON":
            # Forward declaration: struct Name;
            self.advance()
            return StructDef(name=name, fields=[], is_anonymous=False)
        elif self.peek()[0] == "IDENTIFIER" and name is not None:
            var_type = f"struct {name}"
            var_type = self._consume_pointer_stars(var_type)
            func_name = self.advance()[1]
            if self.accept("LPAREN"):
                params = []
                if not self.accept("RPAREN"):
                    if self.peek()[0] == "VOID":
                        self.advance()
                        self.expect("RPAREN")
                    else:
                        while True:
                            type_qualifiers = []
                            # Handle qualifiers before base type
                            while self.peek()[0] in ("CONST", "VOLATILE"):
                                type_qualifiers.append(self.advance()[1])
                            ptype = self.advance()[1]
                            # Don't expand typedef aliases - keep original name
                            if (
                                ptype in ("struct", "union", "enum")
                                and self.peek()[0] == "IDENTIFIER"
                            ):
                                ptype = f"{ptype} {self.advance()[1]}"
                            elif self.peek()[0] in _BASE_TYPE_TOKENS:
                                ptype2 = self.advance()[1]
                                ptype = f"{ptype} {ptype2}"
                            ptype = self._consume_pointer_stars(ptype)
                            while self.peek()[0] in ("CONST", "VOLATILE"):
                                type_qualifiers.append(self.advance()[1])
                            if type_qualifiers:
                                ptype = " ".join(type_qualifiers) + " " + ptype
                            pname = self.expect("IDENTIFIER")[1]
                            psize = None
                            psize_list = []
                            while self.accept("LBRACKET"):
                                if self.peek()[0] == "INT_LITERAL":
                                    psize_list.append(int(self.advance()[1]))
                                elif self.peek()[0] == "IDENTIFIER":
                                    psize_list.append(self.advance()[1])
                                else:
                                    psize_list.append(0)
                                self.expect("RBRACKET")
                            if psize_list:
                                if len(psize_list) == 1:
                                    psize = psize_list[0]
                                else:
                                    psize = psize_list
                            params.append((ptype, pname, psize))
                            if self.accept("COMMA"):
                                if self.accept("ELLIPSIS"):
                                    params.append(("...", "...", None))
                                    self.expect("RPAREN")
                                    break
                                continue
                            self.expect("RPAREN")
                            break
                if self.peek()[0] == "LBRACE":
                    return Function(var_type, func_name, params, self.parse_compound())
                else:
                    self.expect("SEMICOLON")
                    return Declaration(f"{var_type} (func prototype)", func_name, None)
            init = self.parse_expression() if self.accept("ASSIGN") else None
            self.expect("SEMICOLON")
            return Declaration(var_type, func_name, init)

        tok = self.peek()
        line = tok[2] if len(tok) > 2 else 0
        col = tok[3] if len(tok) > 3 else 0
        raise SyntaxError(
            error_msgs.get_error_msg(
                "E001",
                found=tok[0],
                line=line,
                col=col,
                fallback=f"Unexpected token after struct at line {line}, column {col}: {tok}",
            )
        )

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
                    tok = self.peek()
                    line = tok[2] if len(tok) > 2 else 0
                    col = tok[3] if len(tok) > 3 else 0
                    raise SyntaxError(
                        error_msgs.get_error_msg(
                            "E602",
                            file="union",
                            line=line,
                            col=col,
                            fallback=f"Unexpected end of file at line {line}, column {col}: unclosed union",
                        )
                    )
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

        tok = self.peek()
        line = tok[2] if len(tok) > 2 else 0
        col = tok[3] if len(tok) > 3 else 0
        raise SyntaxError(
            f"Unexpected token after union at line {line}, column {col}: {tok}"
        )

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
                    raise SyntaxError(
                        error_msgs.get_error_msg(
                            "E602",
                            file="enum",
                            fallback="Unexpected end of file: unclosed enum",
                        )
                    )
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

        tok = self.peek()
        line = tok[2] if len(tok) > 2 else 0
        col = tok[3] if len(tok) > 3 else 0
        raise SyntaxError(
            error_msgs.get_error_msg(
                "E001",
                found=tok[0],
                line=line,
                col=col,
                fallback=f"Unexpected token after enum at line {line}, column {col}: {tok}",
            )
        )

    # ============================================================
    # Statements
    # ============================================================

    def parse_statement(self) -> Node:
        """Parse a single statement."""
        t = self.peek()

        # Skip preprocessor directives and comments iteratively
        while t[0] in ("PREPROCESSOR", "COMMENT_MULTI", "COMMENT_LINE"):
            self.advance()
            t = self.peek()

        # Handle type declarations (including size_t and system types like mode_t, uid_t, etc.)
        if t[0] in _BASE_TYPE_TOKENS:
            return self._parse_local_declaration()
        # Handle qualifiers (const, volatile) before type: volatile int* x;
        if t[0] in ("CONST", "VOLATILE"):
            return self._parse_local_declaration()
        # Handle storage class specifiers at statement level (e.g., extern void foo())
        if t[0] in ("EXTERN", "STATIC", "AUTO", "REGISTER"):
            self.advance()
            if self.peek()[0] in _BASE_TYPE_TOKENS:
                # Skip function prototype: type name(...);
                saved_i = self.i
                try:
                    self.advance()  # consume base type
                    if self.peek()[0] in _BASE_TYPE_TOKENS:
                        self.advance()  # consume second part of compound type
                    self._consume_pointer_stars("")  # consume pointer stars
                    if self.peek()[0] == "IDENTIFIER":
                        self.advance()  # consume name
                        if self.accept("LPAREN"):
                            # Skip parameter list
                            while not self.accept("RPAREN"):
                                self.advance()
                                if self.peek()[0] == "COMMA":
                                    self.advance()
                            self.expect("SEMICOLON")
                            return Declaration(
                                "extern (func prototype)", "_skipped", None
                            )
                except Exception:
                    pass
                self.i = saved_i  # not a function prototype
        # Handle typedef aliases
        if t[0] == "IDENTIFIER" and t[1] in self._typedefs:
            return self._parse_local_declaration()
        # Handle storage class specifiers at statement level (e.g., extern void foo())
        if t[0] in ("EXTERN", "STATIC", "AUTO", "REGISTER"):
            self.advance()
            if self.peek()[0] in _BASE_TYPE_TOKENS:
                # Check if this is a function prototype: type name(...)
                saved_i = self.i
                self.advance()  # consume base type
                if self.peek()[0] in _BASE_TYPE_TOKENS:
                    self.advance()  # consume second part of compound type
                self._consume_pointer_stars("")  # consume pointer stars
                if self.peek()[0] == "IDENTIFIER":
                    self.advance()  # consume name
                    if self.accept("LPAREN"):
                        self.expect("RPAREN")  # simple prototype
                        self.expect("SEMICOLON")
                        return Declaration(
                            "extern (func prototype)", "local_decl", None
                        )
                self.i = saved_i  # not a simple prototype, treat as variable decl
                return self._parse_local_declaration()
        # Handle typedef aliases
        if t[0] == "IDENTIFIER" and t[1] in self._typedefs:
            return self._parse_local_declaration()
        # Handle system type aliases (mode_t, uid_t, gid_t, etc.) - check if next token looks like a variable
        if t[0] == "IDENTIFIER":
            # Peek at next token - if it's an identifier, this is likely a type declaration
            next_idx = self.i + 1
            if next_idx < len(self.tokens):
                next_tok = self.tokens[next_idx]
                if next_tok[0] in ("IDENTIFIER", "MULTIPLY"):
                    return self._parse_local_declaration()

        if t[0] == "LBRACE":
            return self.parse_compound()

        # Handle asm blocks inside function bodies
        if t[0] == "ASM":
            return self.parse_asm_block()

        # Handle using declarations inside function bodies
        if t[0] == "USING":
            return self.parse_using()

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
                        init.initializer = self._parse_single_expression()
                    while self.accept("COMMA"):
                        if self.peek()[0] == "IDENTIFIER":
                            next_idtok = self.expect("IDENTIFIER")
                            next_name = next_idtok[1]
                            next_decl = Declaration(
                                var_type=typ, name=next_name, initializer=None
                            )
                            if self.accept("ASSIGN"):
                                next_decl.initializer = self._parse_single_expression()
                            if isinstance(init, Declaration):
                                init = Compound([init, next_decl])
                            else:
                                init.stmts.append(next_decl)
                        else:
                            next_expr = self._parse_single_expression()
                            if isinstance(init, Compound):
                                init.stmts.append(next_expr)
                            else:
                                init = Compound([init, next_expr])
                else:
                    init = self.parse_expression()
                    while self.accept("COMMA"):
                        next_expr = self.parse_expression()
                        if isinstance(init, Compound):
                            init.stmts.append(next_expr)
                        else:
                            init = Compound([init, next_expr])
            self.expect("SEMICOLON")
            cond = None
            if self.peek()[0] != "SEMICOLON":
                cond = self.parse_expression()
            self.expect("SEMICOLON")
            post = None
            if self.peek()[0] != "RPAREN":
                post = self._parse_single_expression()
                while self.accept("COMMA"):
                    next_expr = self._parse_single_expression()
                    if isinstance(post, Compound):
                        post.stmts.append(next_expr)
                    else:
                        post = Compound([post, next_expr])
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
                    case_value = getattr(stmt, "case_label")
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
            setattr(case_label_node, "case_label", case_value)
            self.expect("COLON")
            return case_label_node  # type: ignore

        if t[0] == "DEFAULT":
            default_label_node = type(
                "DefaultLabel", (), {"case_label": None, "is_default": True}
            )()
            self.advance()
            self.expect("COLON")
            return default_label_node  # type: ignore

        # Reject deprecated / removed keywords in statement position too.
        if t[0] in (
            "RESTRICT",
            "BOOLEAN",
            "UNDERSCORE_ALIGNOF",
            "UNDERSCORE_ALIGNAS",
            "UNDERSCORE_COMPLEX",
            "UNDERSCORE_IMAGINARY",
        ):
            line = t[2] if len(t) > 2 else 0
            col = t[3] if len(t) > 3 else 0
            raise SyntaxError(
                error_msgs.get_error_msg(
                    "E001",
                    found=t[0],
                    line=line,
                    col=col,
                    fallback=f"Deprecated keyword used at line {line}, column {col}! Found '{t[0]}'.",
                )
            )

        # Label: IDENTIFIER:
        if t[0] == "IDENTIFIER" and len(self.tokens) > self.i + 1:
            next_tok = self.tokens[self.i + 1]
            if next_tok[0] == "COLON":
                name = self.advance()[1]
                self.advance()  # consume COLON
                return Label(name)

        # Local declaration - only enter if next token looks like a variable declaration
        is_typedef_decl = t[0] in (
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
        ) or (t[0] == "IDENTIFIER" and (t[1] in ("va_list",) or t[1] in self._typedefs))
        if is_typedef_decl:
            next_tok = (
                self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok[0] not in (
                "IDENTIFIER",
                "MULTIPLY",
                "LBRACKET",
                "COMMA",
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
            ):
                is_typedef_decl = False

        if is_typedef_decl:
            qualifiers = []
            while self.peek()[0] in ("CONST", "VOLATILE"):
                qualifiers.append(self.advance()[1])

            base_type = self.advance()[1]

            if base_type == "typedef":
                if self.peek()[0] == "IDENTIFIER":
                    base_type = self.advance()[1]
                else:
                    base_type = "int"
                # Don't expand typedef aliases - keep original name

            elif t[0] == "IDENTIFIER" and t[1] not in ("va_list",):
                if t[1] in self._typedefs:
                    pass  # Keep original name

            elif base_type == "struct" and self.peek()[0] == "IDENTIFIER":
                struct_tag = self.advance()[1]
                base_type = f"struct {struct_tag}"
                base_type = self._consume_pointer_stars(base_type)

            elif base_type == "union" and self.peek()[0] == "IDENTIFIER":
                union_tag = self.advance()[1]
                base_type = f"union {union_tag}"
                base_type = self._consume_pointer_stars(base_type)

            elif base_type == "enum" and self.peek()[0] == "IDENTIFIER":
                enum_tag = self.advance()[1]
                base_type = f"enum {enum_tag}"
                base_type = self._consume_pointer_stars(base_type)

            # Handle compound types in local declarations
            # Stop at literals to avoid consuming type tokens after value
            while self.peek()[0] in _BASE_TYPE_TOKENS:
                next_tok = self.peek()
                if next_tok[0] in (
                    "INT_LITERAL",
                    "HEX_LITERAL",
                    "BINARY_LITERAL",
                    "OCTAL_LITERAL",
                    "CHAR_LITERAL",
                    "STRING_LITERAL",
                    "FLOAT_LITERAL",
                ):
                    break
                base_type2 = self.advance()[1]
                base_type = f"{base_type} {base_type2}"

            # Build the full type: [qualifiers] base_type [pointers]
            typ = base_type
            if qualifiers:
                typ = " ".join(qualifiers) + " " + typ

            # Handle pointer type: int* ptr or int** ptr2
            typ = self._consume_pointer_stars(typ)

            # Allow literals after compound types (e.g., unsigned long long x = 0xFF)
            valid_initializer_start = self.peek()[0] in (
                "INT_LITERAL",
                "HEX_LITERAL",
                "BINARY_LITERAL",
                "OCTAL_LITERAL",
                "CHAR_LITERAL",
                "STRING_LITERAL",
                "FLOAT_LITERAL",
            )
            if not valid_initializer_start and self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                raise SyntaxError(
                    error_msgs.get_error_msg(
                        "E008",
                        found=bad_tok[0],
                        keyword=typ,
                        fallback=f"Expected identifier. Declaration keyword '{typ}' was followed by a non-identifier token. Got '{bad_tok[0]}'.",
                    )
                )
            name = self.advance()[1]

            # Handle array declarations: char temp[32]
            array_size = None
            if self.peek()[0] == "LBRACKET":
                # Simple heuristic: if this is a reassignment (arr = [1,2,3]),
                # the LBRACKET is NOT an array size but an initializer
                # Check if this is a redeclaration - if the name already exists,
                # LBRACKET is an initializer, not array size
                # For now, just check if we just parsed a name and the previous token is =
                prev_tok = self.tokens[self.i - 1] if self.i > 0 else None
                is_reassignment = prev_tok and prev_tok[0] == "ASSIGN"

                if not is_reassignment:
                    self.advance()  # consume '['
                    if self.peek()[0] == "INT_LITERAL":
                        array_size = int(self.advance()[1])
                    self.expect("RBRACKET")

            # Handle initialization
            init = None
            if self.accept("ASSIGN"):
                init = self.parse_assignment()
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
                    extra_init = self.parse_assignment()
                elif self.peek()[0] == "LBRACE":
                    extra_init = self.parse_init_list()
                decls.append(Declaration(typ, extra_name, extra_init))

            self.expect("SEMICOLON")

            if len(decls) == 1:
                return decls[0]
            return self._make_decl_list(decls)

        if t[0] == "ALLOCATE":
            self.advance()  # consume allocate
            alloc_type = self.advance()[1]
            # Handle compound types
            while self.peek()[0] in (
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
            ):
                alloc_type += " " + self.advance()[1]
            # Pointer stars
            while self.peek()[0] == "MULTIPLY":
                alloc_type += "*"
                self.advance()
            name = self.expect("IDENTIFIER")[1]
            count = None
            byte_size = None
            if self.accept("LBRACKET"):
                if self.peek()[0] == "INT_LITERAL":
                    count = Literal(int(self.advance()[1]))
                self.expect("RBRACKET")
            elif self.accept("LPAREN"):
                if self.peek()[0] == "INT_LITERAL":
                    byte_size = Literal(int(self.advance()[1]))
                self.expect("RPAREN")
            init = None
            if self.accept("ASSIGN"):
                init = self.parse_assignment()
            self.expect("SEMICOLON")
            return Alloc(alloc_type, name, count, byte_size, init)

        if t[0] == "FREE":
            self.advance()
            self.expect("LPAREN")
            expr = self.parse_expression()
            self.expect("RPAREN")
            self.expect("SEMICOLON")
            return Free(expr)

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
            if t[0] in ("PREPROCESSOR", "COMMENT_MULTI", "COMMENT_LINE"):
                self.advance()
                continue
            if t[0] == "RBRACE":
                break
            if t[0] == "EOF":
                line = t[2] if len(t) > 2 else 0
                col = t[3] if len(t) > 3 else 0
                raise SyntaxError(
                    error_msgs.get_error_msg(
                        "E006",
                        statement="compound",
                        line=line,
                        col=col,
                        fallback=f"Unexpected end of file at line {line}, column {col}: unclosed '{{' — missing closing '}}'",
                    )
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

    def parse_array_initializer(self) -> InitList:
        """Parse a bracket-enclosed array initializer: [ expr, expr, ... ]"""
        self.expect("LBRACKET")
        elements = []
        if self.peek()[0] != "RBRACKET":
            elements.append(self.parse_assignment())
            while self.accept("COMMA"):
                if self.peek()[0] == "RBRACKET":
                    break
                elements.append(self.parse_assignment())
        self.expect("RBRACKET")
        return InitList(elements)

    def parse_initializer_element(self) -> Node:
        """Parse a single element in an initializer list.

        Handles C11 designated initializers:
        - .field = value (struct field)
        - [expr] = value (array element)
        - [start...end] = value (array range)
        """
        if self.peek()[0] == "DOT":
            self.advance()
            field_name = self.expect("IDENTIFIER")[1]
            self.expect("ASSIGN")
            value = self.parse_assignment()
            return DesignatedInit(field=field_name, value=value)  # type: ignore
        if self.peek()[0] == "LBRACKET":
            self.advance()
            start_idx = self.parse_expression()
            if self.accept("ELLIPSIS"):
                end_idx = self.parse_expression()
                self.expect("RBRACKET")
                self.expect("ASSIGN")
                value = self.parse_assignment()
                return ArrayDesignation(
                    index=start_idx,
                    value=value,  # type: ignore
                    is_range=True,
                    end_index=end_idx,  # type: ignore
                )
            self.expect("RBRACKET")
            self.expect("ASSIGN")
            value = self.parse_assignment()
            return ArrayDesignation(index=start_idx, value=value)  # type: ignore
        return self.parse_assignment()  # type: ignore

    # ============================================================
    # Expressions (precedence climbing)
    # ============================================================

    def parse_expression(self) -> Node:
        node = self.parse_assignment()  # type: ignore
        while self.accept("COMMA"):
            right = self.parse_assignment()  # type: ignore
            if node is None or right is None:
                raise SyntaxError("Expected expression after ','")
            assert node is not None and right is not None
            node = Comma(node, right)
        return node  # type: ignore

    def _parse_single_expression(self) -> Node:
        """Parse a single expression without handling top-level commas."""
        return self.parse_assignment()  # type: ignore

    def parse_assignment(self) -> Optional[Node]:
        node = self.parse_conditional()
        if self.accept("ASSIGN"):
            return Assignment(node, self.parse_assignment())  # type: ignore
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
                return Assignment(node, Binary(op_symbol, node, right))  # type: ignore
        return node  # type: ignore

    def parse_conditional(self) -> Node:
        node = self.parse_logical_or()
        if self.accept("QUESTION"):
            t = self.parse_expression()
            self.expect("COLON")
            f = self.parse_conditional()
            return Binary("?:", node, Binary("branch", t, f))
        return node

    def parse_logical_or(self) -> Node:
        node = self.parse_logical_and()
        while self.accept("OR"):
            right = self.parse_logical_and()
            node = Binary("||", node, right)
        return node

    def parse_logical_and(self) -> Node:
        node = self.parse_equality()
        while self.accept("AND"):
            right = self.parse_equality()
            node = Binary("&&", node, right)
        return node

    def parse_equality(self) -> Node:
        node = self.parse_relational()
        while self.peek()[0] in ("EQ", "NEQ"):
            op = self.advance()[1]
            right = self.parse_relational()
            node = Binary(op, node, right)
        return node

    def parse_relational(self) -> Node:
        node = self.parse_bitwise_or()
        while self.peek()[0] in ("LT", "GT", "LE", "GE"):
            op = self.advance()[1]
            right = self.parse_bitwise_or()
            node = Binary(op, node, right)
        return node

    def parse_bitwise_or(self) -> Node:
        node = self.parse_bitwise_xor()
        while self.peek()[0] == "BITWISE_OR":
            op = self.advance()[1]
            right = self.parse_bitwise_xor()
            node = Binary(op, node, right)
        return node

    def parse_bitwise_xor(self) -> Node:
        node = self.parse_bitwise_and()
        while self.peek()[0] == "BITWISE_XOR":
            op = self.advance()[1]
            right = self.parse_bitwise_and()
            node = Binary(op, node, right)
        return node

    def parse_bitwise_and(self) -> Node:
        node = self.parse_shift()
        while self.peek()[0] == "AMPERSAND":
            op = self.advance()[1]
            right = self.parse_shift()
            node = Binary(op, node, right)
        return node

    def parse_shift(self) -> Node:
        node = self.parse_add()
        while self.peek()[0] in ("LSHIFT", "RSHIFT"):
            op = self.advance()[1]
            right = self.parse_add()
            node = Binary(op, node, right)
        return node

    def parse_add(self) -> Node:
        node = self.parse_term()
        while self.peek()[0] in ("PLUS", "MINUS"):
            op = self.advance()[1]
            right = self.parse_term()
            node = Binary(op, node, right)
        return node

    def parse_term(self) -> Node:
        node = self.parse_unary()  # type: ignore
        while self.peek()[0] in ("MULTIPLY", "DIVIDE", "MODULO"):
            op = self.advance()[1]
            right = self.parse_unary()  # type: ignore
            node = Binary(op, node, right)  # type: ignore
        return node  # type: ignore

    def parse_unary(self) -> Optional[Node]:
        """Parse unary prefix expressions (e.g. !y, ++x, --x, *ptr, &var, -x)."""
        token = self.peek()
        if token[0] == "SIZEOF":
            self.advance()
            if self.peek()[0] == "LPAREN":
                self.advance()
                is_typedef = (
                    self.peek()[0] == "IDENTIFIER" and self.peek()[1] in self._typedefs
                )
                if (
                    self.peek()[0] in _BASE_TYPE_TOKENS
                    or self.peek()[0] in ("STRUCT", "UNION", "ENUM")
                    or is_typedef
                ):
                    operand = self.parse_type_expression()
                else:
                    operand = self.parse_expression()
                self.expect("RPAREN")
            else:
                operand = self.parse_unary()  # type: ignore
            return Unary(op="sizeof", operand=operand, prefix=True)  # type: ignore
        if token[0] == "MINUS":
            self.advance()
            operand = self.parse_unary()  # type: ignore
            return Unary(op="-", operand=operand, prefix=True)  # type: ignore
        if token[0] == "PLUS":
            self.advance()
            operand = self.parse_unary()  # type: ignore
            return Unary(op="+", operand=operand, prefix=True)  # type: ignore
        if token[0] == "NOT":
            op = self.advance()[1]
            operand = self.parse_unary()  # type: ignore
            return Unary(op=op, operand=operand, prefix=True)  # type: ignore
        if token[0] == "TILDE":
            self.advance()
            operand = self.parse_unary()  # type: ignore
            return Unary(op="~", operand=operand, prefix=True)  # type: ignore
        if token[0] in ("INCREMENT", "DECREMENT"):
            op = self.advance()[1]
            operand = self.parse_unary()  # type: ignore
            return Unary(op=op, operand=operand, prefix=True)  # type: ignore
        if token[0] == "MULTIPLY":
            self.advance()
            operand = self.parse_unary()  # type: ignore
            return Unary(op="*", operand=operand, prefix=True)  # type: ignore
        if token[0] == "AMPERSAND":
            self.advance()
            operand = self.parse_unary()  # type: ignore
            return Unary(op="&", operand=operand, prefix=True)  # type: ignore
        return self.parse_postfix()

    def _is_assignment_rhs(self) -> bool:
        """Check if we're in the right-hand side of an assignment.

        Looks backward to see if the previous token was an ASSIGN.
        """
        if self.i == 0:
            return False
        # Check if previous token was ASSIGN
        prev_tok = self.tokens[self.i - 1]
        return prev_tok[0] == "ASSIGN"

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
                # Check if this is an array subscript (e.g., arr[0]) or array initializer
                # Array initializer only happens when we're at the start of an expression
                # Array subscript happens after we've already parsed an expression
                if isinstance(node, Var) and self._is_assignment_rhs():
                    # In assignment RHS context, [1, 2, 3] is array initializer
                    self.advance()  # consume LBRACKET
                    init = self.parse_array_initializer()
                    node = init
                else:
                    # Array subscript: arr[0]
                    self.advance()  # consume LBRACKET
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
            elif self.peek()[0] == "ARROW":
                # Arrow operator: expr->field (pointer dereference field access)
                self.advance()
                field_name = self.expect("IDENTIFIER")[1]
                # Convert arrow to (*expr).field for AST representation
                deref = Unary(op="*", operand=node, prefix=True)
                node = FieldAccess(deref, field_name)
            else:
                break
        return node

    def parse_type_expression(self) -> Node:
        """Parse a type keyword or compound type (e.g., int, long long, dynam int, string)."""
        if self.peek()[0] in _BASE_TYPE_TOKENS:
            type1 = self.advance()[1]
            # Handle dynam type: "dynam <element_type>"
            if type1 == "dynam":
                elem_type = self.parse_type_expression()
                return TypeExpr(f"dynam {getattr(elem_type, 'type_name', '')}")
            # Handle string type (no element type needed)
            if type1 == "string":
                return TypeExpr("string")
            if self.peek()[0] in _BASE_TYPE_TOKENS:
                type2 = self.advance()[1]
                type1 = f"{type1} {type2}"
            type1 = self._consume_pointer_stars(type1)
            return TypeExpr(type1)
        # Handle typedef names (user-defined types)
        if self.peek()[0] == "IDENTIFIER" and self.peek()[1] in self._typedefs:
            type_name = self.advance()[1]
            type_name = self._consume_pointer_stars(type_name)
            return TypeExpr(type_name)
        if self.peek()[0] == "STRUCT":
            self.advance()
            type_name = "struct"
            if self.peek()[0] == "IDENTIFIER":
                type_name += " " + self.advance()[1]
            return TypeExpr(type_name)
        tok = self.peek()
        line = tok[2] if len(tok) > 2 else 0
        col = tok[3] if len(tok) > 3 else 0
        raise SyntaxError(
            error_msgs.get_error_msg(
                "E102",
                found=tok[0],
                line=line,
                col=col,
                fallback=f"Expected type keyword at line {line}, column {col}, got {tok}",
            )
        )

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
            raise SyntaxError(
                error_msgs.get_error_msg(
                    "E605",
                    found="_Generic",
                    fallback="Expected expression in _Generic at current position",
                )
            )
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

        # Handle func@lib - namespace access (function@namespace)
        if tok[0] == "IDENTIFIER":
            # Check if this is followed by @
            next_tok = (
                self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
            )
            if next_tok and next_tok[0] == "AT":
                # This is function@namespace pattern
                func_name = self.advance()[1]
                self.expect("AT")
                # Namespace can be IDENTIFIER, PLSTD, or STRING (string type keyword)
                if self.peek()[0] in ("IDENTIFIER", "PLSTD", "STRING"):
                    namespace = self.advance()[1]
                else:
                    line = self.peek()[2] if len(self.peek()) > 2 else 0
                    col = self.peek()[3] if len(self.peek()) > 3 else 0
                    raise SyntaxError(
                        error_msgs.get_error_msg(
                            "E001",
                            found=self.peek()[0],
                            expected="identifier",
                            line=line,
                            col=col,
                            fallback=f"Expected identifier after '@' at line {line}, column {col}",
                        )
                    )
                return Var(f"{func_name}@{namespace}")

        if tok[0] == "IDENTIFIER":
            return Var(self.advance()[1])
        if tok[0] in (
            "INT_LITERAL",
            "FLOAT_LITERAL",
            "CHAR_LITERAL",
            "HEX_LITERAL",
            "BINARY_LITERAL",
            "OCTAL_LITERAL",
            "STRING_LITERAL",
        ):
            return Literal(self.advance()[1])
        if tok[0] == "FLOAT_LITERAL":
            return Literal(self.advance()[1])
        if tok[0] == "LPAREN":
            self.advance()
            # Check if this is a cast: (type)expr vs grouping: (expr)
            # Cast if: base type, struct/union/enum keyword, or typedef name
            is_typedef = (
                self.peek()[0] == "IDENTIFIER" and self.peek()[1] in self._typedefs
            )
            if (
                self.peek()[0] in _BASE_TYPE_TOKENS
                or self.peek()[0]
                in (
                    "STRUCT",
                    "UNION",
                    "ENUM",
                )
                or is_typedef
            ):
                # Cast path - go to cast handling
                # First, save position so we can resume here
                # Handle type with pointer/array suffixes and potential compound literal
                # Then parse operand and return Cast node
                type_node = self.parse_type_expression()
                while self.peek()[0] == "MULTIPLY":
                    self.advance()
                    setattr(
                        type_node,
                        "type_name",
                        getattr(type_node, "type_name", "") + "*",
                    )
                if self.peek()[0] == "LBRACKET":
                    self.advance()
                    if self.peek()[0] == "RBRACKET":
                        setattr(
                            type_node,
                            "type_name",
                            getattr(type_node, "type_name", "") + "[]",
                        )
                    else:
                        size = self.expect("INT_LITERAL")[1]
                        setattr(
                            type_node,
                            "type_name",
                            getattr(type_node, "type_name", "") + f"[{size}]",
                        )
                    self.expect("RBRACKET")
                if self.peek()[0] == "LBRACE":
                    init_list = self.parse_init_list()
                    return CompoundLiteral(
                        lit_type=getattr(type_node, "type_name", ""),
                        elements=init_list.elements,
                    )
                self.expect("RPAREN")
                operand = self.parse_unary()  # type: ignore
                return Cast(  # type: ignore
                    cast_type=getattr(type_node, "type_name", ""),
                    operand=operand,  # type: ignore
                )
            else:
                # Grouping: (expr)
                node = self.parse_expression()
                self.expect("RPAREN")
                return CompoundLiteral("()", [node]) if self.accept("LBRACE") else node
        if tok[0] == "LBRACE":
            return self.parse_init_list()
        if tok[0] in _BASE_TYPE_TOKENS:
            return TypeExpr(self.advance()[1])
        if tok[0] == "LBRACKET":
            # Parse as array initializer: [1, 2, 3]
            return self.parse_array_initializer()
        if tok[0] == "UNDERSCORE_GENERIC":
            return self.parse_generic()
        line = tok[2] if len(tok) > 2 else 0
        col = tok[3] if len(tok) > 3 else 0
        raise SyntaxError(
            error_msgs.get_error_msg(
                "E001",
                found=tok[0],
                line=line,
                col=col,
                fallback=f"Unexpected token {tok} in primary expression at line {line}, column {col}",
            )
        )


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
        prev_i = self.i
        if prev_i >= len(self.tokens):
            break
        node = self.parse_external()
        if node is None:
            if self.i == prev_i and self.i < len(self.tokens):
                self.advance()
            continue
        if self.i == prev_i:
            raise SyntaxError(f"Parser stuck at token: {self.peek()}")
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
