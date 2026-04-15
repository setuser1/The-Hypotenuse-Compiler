import logging
import os
import platform
from typing import Optional

from parser import (
    Program,
    Function,
    Declaration,
    Compound,
    If,
    While,
    For,
    Return,
    ExprStmt,
    Assignment,
    Binary,
    Unary,
    Literal,
    Var,
    Call,
    ArrayAccess,
    StructDef,
    UnionDef,
    EnumDef,
    Typedef,
    FieldAccess,
    UsingDecl,
    ExposeDecl,
    LibAccess,
    SpaceDecl,
    AsmBlock,
)


# ============================================================
# Scope / graph nodes
# ============================================================

logger = logging.getLogger(__name__)

SYSTEM_INCLUDE_PATHS = {
    "linux": [
        "/usr/include",
        "/usr/local/include",
    ],
    "darwin": [
        "/usr/include",
        "/usr/local/include",
        "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include",
        "/Library/Developer/CommandLineTools/usr/lib/clang/*/include",
    ],
}

HOMEBObrew_INCLUDE_PATHS = [
    "/opt/homebrew/include",
    "/usr/local/include",
]

C11_SIZEOF = {
    "char": 1,
    "short": 2,
    "int": 4,
    "long": 8,
    "long long": 8,
    "float": 4,
    "double": 8,
    "long double": 16,
    "void*": 8,
    "_Bool": 1,
}


def get_system_include_paths():
    system = platform.system().lower()
    paths = list(SYSTEM_INCLUDE_PATHS.get(system, []))

    if system == "darwin":
        xcode_sdk_path = (
            "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include"
        )
        if xcode_sdk_path not in paths:
            if os.path.isdir(xcode_sdk_path):
                paths.append(xcode_sdk_path)
        for hb_path in HOMEBObrew_INCLUDE_PATHS:
            if hb_path not in paths and os.path.isdir(hb_path):
                paths.append(hb_path)

    return paths


class IncludeNode:
    """Represents a #include directive with lazy import tracking."""

    def __init__(self, path, is_system, exists=None, used_definitions=None):
        self.path = path
        self.is_system = is_system
        self.exists = exists
        self.used_definitions = used_definitions or []
        self._resolved_path = None
        self._all_definitions = []
        self._checked = False

    def __repr__(self):
        status = (
            "valid"
            if self.exists
            else ("unknown" if self.exists is None else "missing")
        )
        used_count = len(self.used_definitions)
        return f"Include(path={self.path!r}, is_system={self.is_system}, status={status}, used={used_count})"

    def resolve_path(self, base_dir=None):
        """Resolve the include path to an absolute path on the current OS."""
        if self._resolved_path:
            return self._resolved_path

        search_paths = get_system_include_paths()
        if base_dir:
            search_paths.insert(0, base_dir)
            search_paths.insert(0, os.path.join(base_dir, "include"))

        import glob as glob_module

        found = False
        for search_dir in search_paths:
            if "*" in search_dir:
                matched_paths = glob_module.glob(search_dir)
                for matched in matched_paths:
                    full_path = os.path.join(matched, self.path)
                    if os.path.isfile(full_path):
                        self._resolved_path = full_path
                        self.exists = True
                        found = True
                        break
                if found:
                    break
            else:
                full_path = os.path.join(search_dir, self.path)
                if os.path.isfile(full_path):
                    self._resolved_path = full_path
                    self.exists = True
                    found = True
                    break

        self._checked = True
        if not found:
            self._resolved_path = None
            if self.exists is not False:
                logger.warning(
                    "Header not found in system paths: %s (搜索了 %s)",
                    self.path,
                    search_paths,
                )
            self.exists = False

        return self._resolved_path

    def parse_header(self):
        """Parse the header file to extract all exported definitions."""
        resolved = self.resolve_path()
        if not resolved or not self.exists:
            return

        try:
            with open(resolved, "r") as f:
                content = f.read()
        except OSError:
            return

        self._parse_content(content, {resolved})

    def _parse_content(self, content, visited_files):
        """Recursively parse header content and included files."""
        import re

        decl_blocks = re.findall(
            r"__BEGIN_DECLS\s*(.*?)\s*__END_DECLS", content, re.DOTALL
        )
        if decl_blocks:
            decl_section = " ".join(decl_blocks)
        else:
            decl_section = content

        functions = re.findall(
            r"^\s*(?:extern\s+)?(\w+)\s+(\w+)\s*\([^;{]*\)\s*;",
            decl_section,
            re.MULTILINE,
        )
        for ret_type, name in functions:
            self._all_definitions.append(("function", name, ret_type.strip()))

        functions_with_attr = re.findall(
            r"^\s*(?:extern\s+)?(\w+)\s+(\w+)\s*\([^;]*\)\s*(?:\([^)]*\))?\s*;",
            decl_section,
            re.MULTILINE,
        )
        for ret_type, name in functions_with_attr:
            if name not in [d[1] for d in self._all_definitions if d[0] == "function"]:
                self._all_definitions.append(("function", name, ret_type.strip()))

        variables = re.findall(
            r"^\s*extern\s+([\w\s\*]+?)\s+(\w+)\s*;\s*$",
            decl_section,
            re.MULTILINE,
        )
        for var_type, name in variables:
            self._all_definitions.append(("variable", name, var_type.strip()))

        structs = re.findall(r"^\s*struct\s+(\w+)\s*\{", decl_section, re.MULTILINE)
        for name in structs:
            self._all_definitions.append(("struct", name, "struct"))

        typedefs = re.findall(
            r"^\s*typedef\s+(?:struct\s+)?\w+\s+(\w+)\s*;", decl_section, re.MULTILINE
        )
        for name in typedefs:
            self._all_definitions.append(("typedef", name, "typedef"))

        enums = re.findall(r"^\s*enum\s+(\w+)\s*\{", decl_section, re.MULTILINE)
        for name in enums:
            self._all_definitions.append(("enum", name, "enum"))

        includes = re.findall(r"#include\s+<\s*([^>]+)\s*>", content)
        for inc in includes:
            inc_path = inc
            inc_resolved = None
            for search_dir in get_system_include_paths():
                full_path = os.path.join(search_dir, inc_path)
                if os.path.isfile(full_path) and full_path not in visited_files:
                    inc_resolved = full_path
                    break
            if inc_resolved:
                new_visited = visited_files | {inc_resolved}
                try:
                    with open(inc_resolved, "r") as f:
                        inc_content = f.read()
                    self._parse_content(inc_content, new_visited)
                except OSError:
                    pass

    def track_used_definitions(self, source_content):
        """Track which definitions from the header are used in the source."""
        if not self._all_definitions:
            self.parse_header()

        if not source_content:
            self.used_definitions = list(self._all_definitions)
            return

        import re

        used = set()
        for def_type, name, type_info in self._all_definitions:
            pattern = r"\b" + re.escape(name) + r"\b"
            if re.search(pattern, source_content):
                used.add((def_type, name, type_info))

        self.used_definitions = list(used)


class Scope:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = {}  # generic children
        self.callees = {}  # name -> Callee
        self.callers = {}  # name -> Caller

    def __repr__(self):
        parent_name = self.parent.name if self.parent else None
        return f"Scope(name={self.name!r}, parent={parent_name!r})"

    def add_child(self, node):
        if isinstance(node, Callee):
            target = self.callees
        elif isinstance(node, Caller):
            target = self.callers
        else:
            target = self.children
        if node.name in target:
            # Silently overwrite duplicate instead of raising error
            # (allows redefinition in nested scopes)
            target[node.name] = node
            return node
        target[node.name] = node
        return node

    def called(self, name):
        for store in (self.children, self.callees, self.callers):
            if name in store:
                return store[name]
        if self.parent:
            return self.parent.called(name)
        return None


class Node:
    """Base graph node."""

    def __init__(self, name, scope):
        self.name = name
        self.scope = scope
        self.scope.add_child(self)
        self.dependencies = []

    def eval(self):
        raise NotImplementedError


class Callee(Node):
    """A value provider or function."""

    def __init__(self, name, scope, value, var_type=None, is_library=False):
        super().__init__(name, scope)
        self.value = value
        self.var_type = var_type
        self.is_library = is_library
        self.return_type = None
        self.has_return = False
        self.return_expression = None
        # True when this Callee was registered via a Declaration node
        # (i.e. it is a variable, not a function).
        self.is_variable = False

    def __repr__(self):
        val_repr = repr(self.value)
        if self.var_type and "*" in self.var_type:
            kind = self.var_type
        elif self.is_library:
            kind = "library"
        elif self.is_variable:
            kind, _ = callee_value_display_parts(self.value)
        elif self.value is None and not self.is_library:
            kind = "function"
        else:
            kind, _ = callee_value_display_parts(self.value)
        type_info = f", type={self.var_type!r}" if self.var_type else ""
        return (
            f"Callee(name={self.name!r}, kind={kind}, value={val_repr}, "
            f"scope={self.scope.name!r}{type_info})"
        )

    def eval(self, *args, **kwargs):
        if callable(self.value):
            resolved = [a.eval() if isinstance(a, Node) else a for a in args]
            return self.value(*resolved)
        if isinstance(self.value, Node):
            return self.value.eval()
        return self.value

    def add_return_expression(self, node):
        self.return_expression = node
        self.has_return = True

    def get_return_expression(self):
        return self.return_expression

    def set_computed_value(self, val):
        self.value = val

    def has_constant_value(self):
        return not callable(self.value) and not isinstance(self.value, Node)


class Caller(Node):
    """A node that depends on and calls other nodes."""

    def __init__(self, name, scope, value=None):
        super().__init__(name, scope)
        self.value = value
        self.propagated_value = None
        self.callee_children: dict | None = None
        self._callee_ref = None
        self._args = []

    def __repr__(self):
        if not self.dependencies:
            return f"Caller(name={self.name!r}, scope={self.scope.name!r}, args=[])"
        callee_node, args = self.dependencies[0]
        args_repr = [repr(a) for a in args]
        return (
            f"Caller(name={self.name!r}, scope={self.scope.name!r}, "
            f"callee={callee_node.name!r}, args={args_repr})"
        )

    def call(self, node, *args):
        self.dependencies.append((node, args))

    def assign_callee(self, callee_node):
        self._callee_ref = callee_node

    def set_arguments(self, args):
        self._args = args

    def propagate_value(self, value):
        self.value = value

    def eval(self):
        result = self.value if isinstance(self.value, (int, float)) else 0
        if isinstance(self.value, Node):
            result = self.value.eval()
        for node, args in self.dependencies:
            if node is None:
                raise ValueError("callee not found")
            result += node.eval(*args)
        return result


class Lib:
    """Library scope containing callable or value nodes."""

    def __init__(self, name, parent_scope=None):
        self.name = name
        self.scope = Scope(name, parent_scope)
        if parent_scope:
            parent_scope.add_child(self.scope)

    def add_node(self, node):
        if node.name in self.scope.children:
            return self.scope.children[node.name]
        return self.scope.add_child(node)

    def called(self, name):
        return self.scope.called(name)


class StructInfo:
    """Information about a struct definition."""

    def __init__(self, name, fields, size=0, alignment=1):
        self.name = name
        self.fields = fields
        self.size = size
        self.alignment = alignment
        self.offset_of = {}


class TypedefInfo:
    """Information about a typedef alias."""

    def __init__(self, alias, actual_type):
        self.alias = alias
        self.actual_type = actual_type


# ============================================================
# Callee value display
# ============================================================


def callee_value_display_parts(value):
    """Return (kind_label, repr_string) for a Callee.value."""
    if value is None:
        return "none", "None"
    if callable(value):
        return "function", repr(value)
    if type(value) is bool:
        return "boolean", repr(value)
    if type(value) is int:
        return "integer", repr(value)
    if type(value) is float:
        return "float", repr(value)
    if isinstance(value, Node):
        return "graph_node", f"<Node {type(value).__name__}>"
    if isinstance(value, str):
        return "string", repr(value)
    return "other", repr(value)


# ============================================================
# Literal value extraction from AST expressions
# ============================================================


def _is_int_const(x):
    """True for plain int constants (not bool, which is a Python int subclass)."""
    return type(x) is int


def _c_int_div(a: int, b: int) -> int:
    """C integer division: truncates toward zero (C99)."""
    c = abs(a) // abs(b)
    if (a < 0) ^ (b < 0):
        c = -c
    return c


def _c_int_mod(a: int, b: int) -> int:
    """C integer remainder using C99 truncation division."""
    return a - _c_int_div(a, b) * b


def _numeric_binary(op, left, right):
    """Apply a binary op to two numeric (or boolean) constants.

    Returns None if the operation is unsupported or would be invalid
    (e.g. division by zero).

    Arithmetic: + - * / % **  (/ and % use C99 truncation rules)
    Comparison: == != < > <= >=
    Logical:    && ||  (short-circuit semantics, returns Python bool)
    """
    # Guard against division/modulo by zero
    if right == 0 and op in ("/", "%"):
        return None

    # Arithmetic
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if _is_int_const(left) and _is_int_const(right):
            return _c_int_div(left, right)
        return left / right
    if op == "**":
        return left**right
    if op == "%":
        if _is_int_const(left) and _is_int_const(right):
            return _c_int_mod(left, right)
        return left % right

    # Comparison  (return int 1/0 to match C semantics)
    if op == "==":
        return int(left == right)
    if op == "!=":
        return int(left != right)
    if op == "<":
        return int(left < right)
    if op == ">":
        return int(left > right)
    if op == "<=":
        return int(left <= right)
    if op == ">=":
        return int(left >= right)

    # Logical  (return int 1/0)
    if op == "&&":
        return int(bool(left) and bool(right))
    if op == "||":
        return int(bool(left) or bool(right))

    return None


def _extract_literal(expr, scope=None):
    """Return a Python value from a simple AST expression, or None.

    Handles:
    - Literal nodes
    - Var nodes (with scope lookup)
    - Unary(-/+/!) on a constant
    - Binary on two constants (arithmetic, comparison, logical)
    - Anything else -> None
    """
    if isinstance(expr, Literal):
        return _cast_literal(expr.value)

    if isinstance(expr, Var) and scope is not None:
        for store in (scope.children, scope.callees, scope.callers):
            if expr.name in store:
                callee = store[expr.name]
                if (
                    hasattr(callee, "has_constant_value")
                    and callee.has_constant_value()
                ):
                    return callee.value
        if scope.parent:
            return _extract_literal(expr, scope.parent)
        return None

    if isinstance(expr, Unary) and expr.prefix:
        inner = _extract_literal(expr.operand, scope)
        if expr.op == "-" and isinstance(inner, (int, float)):
            return -inner
        if expr.op == "+" and isinstance(inner, (int, float)):
            return inner
        if expr.op == "!" and inner is not None:
            return int(not inner)  # C semantics: returns 0 or 1
        if expr.op in ("&", "*"):
            return None
        if expr.op == "sizeof":
            from parser import TypeExpr

            if isinstance(expr.operand, TypeExpr):
                type_name = expr.operand.type_name
                if type_name in ("int", "signed", "signed int"):
                    return 4
                elif type_name in ("char", "signed char"):
                    return 1
                elif type_name in ("long", "long int", "signed long"):
                    return 8
                elif type_name in ("short", "short int", "signed short"):
                    return 2
                elif type_name in ("float",):
                    return 4
                elif type_name in ("double",):
                    return 8
                elif type_name in ("void",):
                    return 0
                elif type_name in (
                    "unsigned",
                    "unsigned int",
                    "unsigned char",
                    "unsigned long",
                    "unsigned short",
                    "signed",
                ):
                    return 4
                elif type_name in ("long long", "unsigned long long"):
                    return 8
                elif "*" in type_name:
                    return 8
            return None

    if isinstance(expr, Binary):
        left = _extract_literal(expr.left, scope)
        right = _extract_literal(expr.right, scope)
        if left is None or right is None:
            return None
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        return _numeric_binary(expr.op, left, right)

    return None


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
    return raw  # string literal or other


# ============================================================
# Structor: AST walker that builds the Callee/Caller/Scope graph
# ============================================================


class Structor:
    """Builds the Callee/Caller/Scope graph by walking a parser AST.

    Usage::

        from parser import Parser
        ast = Parser(tokens).parse_program()
        structor = Structor(ast)
        objects = structor.build_from_ast()

    Scope rules:
    - ``Program``  -> root ``program`` scope
    - ``Function`` -> named child scope for the function body
    - ``For``      -> anonymous ``for_<n>`` child scope (init declaration
                      is scoped to the loop, not the enclosing function)
    - ``Compound`` / ``If`` / ``While`` share the enclosing scope
    """

    def __init__(self, ast: Program, source_content: Optional[str] = None):
        self.ast = ast
        self.objects = {}
        self._order = {}
        self._counter = 0
        self._func_callee_stack: list = []
        self._user_funcs: set = set()
        self._includes: list = []
        self._source_content = source_content or ""
        self._structs = {}
        self._typedefs = {}
        # Import system
        self._imports: list = []  # All UsingDecl nodes
        self._exposes: list = []  # All ExposeDecl nodes
        self._import_table: dict = {}  # namespace -> {symbol -> resolved}
        self._used_symbols: set = set()  # Track what's actually used
        self._in_plib_func: bool = False  # Track if currently inside a plib function

    def _next_id(self):
        self._counter += 1
        return self._counter

    def _obj_key(self, name, scope):
        return f"{scope.name}::{name}"

    def _register(self, node, scope_obj):
        key = self._obj_key(node.name, scope_obj)
        if key not in self.objects:
            self.objects[key] = node
            self._order[key] = self._next_id()
        return self.objects[key]

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build_from_ast(self):
        """Walk self.ast and return an ordered list of graph nodes."""
        program_scope = Scope("program")
        self._collect_user_funcs(self.ast)
        self._walk_program(self.ast, program_scope)
        self._link_callee_children()
        self._compute_struct_info()
        sorted_keys = sorted(self._order, key=lambda k: self._order[k])
        return [self.objects[k] for k in sorted_keys]

    def _collect_user_funcs(self, node):
        """Collect all user-defined function names from the AST."""
        if isinstance(node, Program):
            for decl in node.declarations:
                self._collect_user_funcs(decl)
        elif isinstance(node, Function):
            self._user_funcs.add(node.name)
            self._collect_user_funcs(node.body)
        elif hasattr(node, "body"):
            self._collect_user_funcs(node.body)
        elif hasattr(node, "then"):
            self._collect_user_funcs(node.then)
            if getattr(node, "else", None):
                self._collect_user_funcs(getattr(node, "else"))
        elif hasattr(node, "init"):
            if node.init:
                self._collect_user_funcs(node.init)
            if getattr(node, "cond", None):
                self._collect_user_funcs(node.cond)
            if getattr(node, "body", None):
                self._collect_user_funcs(node.body)

    # ------------------------------------------------------------------
    # Walkers
    # ------------------------------------------------------------------

    def _walk_program(self, node: Program, scope: Scope):
        for decl in node.declarations:
            self._walk_node(decl, scope)

    def _walk_node(self, node, scope: Scope):
        """Dispatch to the appropriate walker based on AST node type."""
        from parser import Include as ParserInclude

        if isinstance(node, Function):
            self._walk_function(node, scope)
        elif isinstance(node, Declaration):
            self._walk_declaration(node, scope)
        elif isinstance(node, For):
            self._walk_for(node, scope)
        elif isinstance(node, Compound):
            self._walk_compound(node, scope)
        elif isinstance(node, If):
            self._walk_if(node, scope)
        elif isinstance(node, While):
            self._walk_while(node, scope)
        elif isinstance(node, Return):
            if node.expr is not None:
                self._walk_expr(node.expr, scope)
                if self._func_callee_stack:
                    callee = self._func_callee_stack[-1]
                    callee.add_return_expression(node.expr)
                    v = _extract_literal(node.expr, scope)
                    if v is not None:
                        callee.set_computed_value(v)
                    callee.has_return = True
        elif isinstance(node, ExprStmt):
            if node.expr is not None:
                self._walk_expr(node.expr, scope)
        elif isinstance(node, ParserInclude):
            self._walk_include(node, scope)
        elif isinstance(
            node, (Assignment, Binary, Unary, Call, ArrayAccess, Var, Literal)
        ):
            self._walk_expr(node, scope)
        elif isinstance(node, StructDef):
            self._walk_struct_def(node, scope)
        elif isinstance(node, UnionDef):
            self._walk_union_def(node, scope)
        elif isinstance(node, EnumDef):
            self._walk_enum_def(node, scope)
        elif isinstance(node, Typedef):
            self._walk_typedef(node, scope)
        elif isinstance(node, FieldAccess):
            self._walk_field_access(node, scope)
        elif isinstance(node, UsingDecl):
            self._walk_using(node, scope)
        elif isinstance(node, ExposeDecl):
            self._walk_expose(node, scope)
        elif isinstance(node, LibAccess):
            self._walk_lib_access(node, scope)
        elif isinstance(node, SpaceDecl):
            for decl in node.declarations:
                self._walk_node(decl, scope)
        elif isinstance(node, AsmBlock):
            self._walk_asm_block(node, scope)

    def _walk_function(self, node: Function, parent_scope: Scope):
        # Check if this function is from a plib
        is_plib = getattr(node, "_from_plib", False)

        # Only add user functions to _user_funcs
        if not is_plib:
            self._user_funcs.add(node.name)

        callee = Callee(node.name, parent_scope, None)
        # Functions are not variables
        callee.is_variable = False
        self._register(callee, parent_scope)
        func_scope = Scope(node.name, parent_scope)
        self._func_callee_stack.append(callee)

        # Track plib context
        old_in_plib = self._in_plib_func
        self._in_plib_func = is_plib
        try:
            self._walk_node(node.body, func_scope)
        finally:
            self._func_callee_stack.pop()
            self._in_plib_func = old_in_plib

    def _walk_declaration(self, node: Declaration, scope: Scope):
        """Register a variable declaration as a Callee with its initial value."""
        value = (
            _extract_literal(node.initializer, scope)
            if node.initializer is not None
            else None
        )
        callee = Callee(node.name, scope, value, var_type=node.var_type)
        # Mark as variable so print_objects/repr display the right kind
        callee.is_variable = True
        self._register(callee, scope)
        if node.initializer is not None:
            self._walk_expr(node.initializer, scope)

    def _walk_for(self, node: For, parent_scope: Scope):
        for_scope = Scope(f"for_{self._next_id()}", parent_scope)
        if node.init is not None:
            self._walk_node(node.init, for_scope)
        if node.cond is not None:
            self._walk_expr(node.cond, for_scope)
        if node.post is not None:
            self._walk_expr(node.post, for_scope)
        self._walk_node(node.body, for_scope)

    def _walk_compound(self, node: Compound, scope: Scope):
        for stmt in node.stmts:
            self._walk_node(stmt, scope)

    def _walk_if(self, node: If, scope: Scope):
        self._walk_expr(node.cond, scope)
        self._walk_node(node.then_branch, scope)
        if node.else_branch is not None:
            self._walk_node(node.else_branch, scope)

    def _walk_while(self, node: While, scope: Scope):
        self._walk_expr(node.cond, scope)
        self._walk_node(node.body, scope)

    def _walk_expr(self, node, scope: Scope):
        """Walk an expression, registering Call nodes as Callers.

        Returns the constant-folded value when it can be determined,
        or None otherwise.
        """
        if isinstance(node, Call):
            self._walk_call(node, scope)
            return None
        if isinstance(node, Assignment):
            self._walk_expr(node.target, scope)
            self._walk_expr(node.value, scope)
            return None
        if isinstance(node, Binary):
            left_val = _extract_literal(node.left, scope)
            right_val = _extract_literal(node.right, scope)
            # Always recurse so nested calls are still registered
            self._walk_expr(node.left, scope)
            self._walk_expr(node.right, scope)
            if left_val is not None and right_val is not None:
                if isinstance(left_val, (int, float)) and isinstance(
                    right_val, (int, float)
                ):
                    return _numeric_binary(node.op, left_val, right_val)
            return None
        if isinstance(node, Unary):
            operand_val = self._walk_expr(node.operand, scope)
            if operand_val is not None:
                if node.op == "-" and isinstance(operand_val, (int, float)):
                    return -operand_val
                if node.op == "+" and isinstance(operand_val, (int, float)):
                    return operand_val
                if node.op == "!":
                    return int(not operand_val)
            if node.op == "sizeof":
                from parser import TypeExpr

                if isinstance(node.operand, TypeExpr):
                    type_name = node.operand.type_name
                    if type_name in ("int", "signed", "signed int"):
                        return 4
                    elif type_name in ("char", "signed char"):
                        return 1
                    elif type_name in ("long", "long int", "signed long"):
                        return 8
                    elif type_name in ("short", "short int", "signed short"):
                        return 2
                    elif type_name in ("float",):
                        return 4
                    elif type_name in ("double",):
                        return 8
                    elif type_name in ("void",):
                        return 0
                    elif type_name in (
                        "unsigned",
                        "unsigned int",
                        "unsigned char",
                        "unsigned long",
                        "unsigned short",
                        "signed",
                    ):
                        return 4
                    elif type_name in ("long long", "unsigned long long"):
                        return 8
                    elif "*" in type_name:
                        return 8
                return None
            return None
        if isinstance(node, ArrayAccess):
            self._walk_expr(node.array, scope)
            self._walk_expr(node.index, scope)
            return None
        # Var and Literal: return their constant value if known
        if isinstance(node, Literal):
            return _cast_literal(node.value)
        if isinstance(node, Var):
            return _extract_literal(node, scope)
        return None

    def _walk_call(self, node: Call, scope: Scope):
        """Register a function call as a Caller node linked to its Callee."""
        if isinstance(node.callee, Var):
            callee_name = node.callee.name
        else:
            self._walk_expr(node.callee, scope)
            for arg in node.args:
                self._walk_expr(arg, scope)
            return

        callee_key = self._obj_key(callee_name, scope)
        callee_node = self.objects.get(callee_key)
        if callee_node is None:
            found = scope.called(callee_name)
            if found is not None and isinstance(found, Callee):
                callee_node = found
            else:
                is_library = callee_name not in self._user_funcs
                callee_node = Callee(callee_name, scope, None, is_library=is_library)
                self._register(callee_node, scope)

        args = list(node.args)
        caller_name = f"call_{callee_name}_{self._next_id()}"
        caller = Caller(caller_name, scope)
        caller.call(callee_node, *args)
        caller.assign_callee(callee_node)
        caller.set_arguments(args)

        if callee_node.has_constant_value():
            caller.propagate_value(callee_node.value)

        self._register(caller, scope)

        for arg in node.args:
            self._walk_expr(arg, scope)

    def _walk_include(self, node, scope: Scope):
        """Process an Include node with lazy import tracking."""
        include = IncludeNode(node.path, node.is_system)
        include.resolve_path()
        include.parse_header()
        if hasattr(self, "_source_content"):
            include.track_used_definitions(self._source_content)
        self._includes.append(include)

    def _walk_struct_def(self, node, scope: Scope):
        """Register a struct definition and compute basic info."""
        fields = []
        if hasattr(node, "fields") and node.fields:
            for field in node.fields:
                if isinstance(field, tuple) and len(field) == 2:
                    fields.append(field)
                elif hasattr(field, "type_name") and hasattr(field, "name"):
                    fields.append((field.type_name, field.name))
        struct_name = getattr(node, "name", None)
        if struct_name:
            self._structs[struct_name] = StructInfo(struct_name, fields)
        else:
            anon_name = f"__anon_struct_{self._next_id()}"
            self._structs[anon_name] = StructInfo(None, fields)

    def _walk_union_def(self, node, scope: Scope):
        """Register a union definition and compute basic info."""
        fields = []
        if hasattr(node, "fields") and node.fields:
            for field in node.fields:
                if isinstance(field, tuple) and len(field) == 2:
                    fields.append(field)
                elif hasattr(field, "type_name") and hasattr(field, "name"):
                    fields.append((field.type_name, field.name))
        union_name = getattr(node, "name", None)
        if union_name:
            self._structs[union_name] = StructInfo(union_name, fields)
        else:
            anon_name = f"__anon_union_{self._next_id()}"
            self._structs[anon_name] = StructInfo(None, fields)

    def _walk_enum_def(self, node, scope: Scope):
        """Register an enum definition."""
        enum_name = getattr(node, "name", None)
        values = getattr(node, "values", [])
        if enum_name:
            self._structs[enum_name] = StructInfo(enum_name, values)
        else:
            anon_name = f"__anon_enum_{self._next_id()}"
            self._structs[anon_name] = StructInfo(None, values)

    def _walk_typedef(self, node, scope: Scope):
        """Register a typedef mapping."""
        alias = getattr(node, "alias", None)
        actual_type = getattr(node, "actual_type", None)
        if alias:
            self._typedefs[alias] = TypedefInfo(alias, actual_type)

    def _walk_field_access(self, node, scope: Scope):
        """Process field access expression."""
        self._walk_expr(node.obj, scope)

    def _walk_using(self, node: UsingDecl, scope: Scope):
        """Process a using declaration."""
        self._imports.append(node)
        # Register in import table
        namespace = self._get_namespace(node.source)
        if namespace not in self._import_table:
            self._import_table[namespace] = {}
        # Add to import table
        if node.alias:
            self._import_table[namespace][node.alias] = node.item
        elif node.item:
            self._import_table[namespace][node.item] = node.item

    def _walk_expose(self, node: ExposeDecl, scope: Scope):
        """Process an expose declaration."""
        self._exposes.append(node)

    def _walk_lib_access(self, node: LibAccess, scope: Scope):
        """Process a lib~ symbol access."""
        self._used_symbols.add(f"lib~{node.symbol}")

    def _walk_asm_block(self, node: AsmBlock, scope: Scope):
        """Process an inline asm block.

        For asm functions (is_function=True): creates a Callee and its own scope.
        For bare asm blocks (is_function=False): variables go into parent scope.
        """
        if node.is_function:
            callee = Callee(node.name, scope, None, var_type=node.ret_type)
            callee.is_variable = False
            self._register(callee, scope)
            func_scope = Scope(node.name, scope)
            for var_info in node.variables:
                var_callee = Callee(
                    var_info["name"],
                    func_scope,
                    var_info.get("initializer"),
                    var_type=var_info["type"],
                )
                var_callee.is_variable = True
                self._register(var_callee, func_scope)
            self._func_callee_stack.append(callee)
            try:
                if node.return_expr:
                    self._walk_expr(node.return_expr, func_scope)
            finally:
                self._func_callee_stack.pop()
        else:
            for var_info in node.variables:
                var_callee = Callee(
                    var_info["name"],
                    scope,
                    var_info.get("initializer"),
                    var_type=var_info["type"],
                )
                var_callee.is_variable = True
                self._register(var_callee, scope)

    def _get_namespace(self, source: str) -> str:
        """Derive namespace from import source."""
        if source.startswith("<") and source.endswith(">"):
            return source[1:-1]  # <math> -> math
        elif "&" in source:
            # Scoped import: X&Y -> X
            return source.split("&")[0]
        else:
            return source  # "utils" -> utils

    def get_struct_info(self, name):
        """Get StructInfo by struct name or typedef target."""
        return self._structs.get(name)

    def resolve_typedef(self, type_name):
        """Resolve typedef chain to canonical type."""
        if type_name in self._typedefs:
            return self.resolve_typedef(self._typedefs[type_name].actual_type)
        return type_name

    def get_structs(self):
        """Return all registered struct infos."""
        return self._structs

    def get_typedefs(self):
        """Return all registered typedef infos."""
        return self._typedefs

    def get_imports(self):
        """Return all using declarations."""
        return self._imports

    def get_exposes(self):
        """Return all expose declarations."""
        return self._exposes

    def get_import_table(self):
        """Return the import table."""
        return self._import_table

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _link_callee_children(self):
        for obj in self.objects.values():
            if isinstance(obj, Caller) and obj.dependencies:
                callee_node = obj.dependencies[0][0]
                obj.callee_children = {
                    "callees": callee_node.scope.callees,
                    "callers": callee_node.scope.callers,
                    "generic": callee_node.scope.children,
                }

    def _compute_struct_info(self):
        """Compute sizes and alignments for all structs."""
        for struct_info in self._structs.values():
            offset = 0
            max_align = 1
            for field_type, field_name in struct_info.fields:
                field_size = self._sizeof_type(field_type)
                field_align = self._alignof_type(field_type)
                if offset % field_align != 0:
                    offset = (offset // field_align + 1) * field_align
                struct_info.offset_of[field_name] = offset
                offset += field_size
                if field_align > max_align:
                    max_align = field_align
            if offset % max_align != 0:
                offset = (offset // max_align + 1) * max_align
            struct_info.size = offset
            struct_info.alignment = max_align

    def _sizeof_type(self, type_name):
        """Return size of a type in bytes."""
        if type_name is None:
            return 0
        type_str = str(type_name)
        if type_str in C11_SIZEOF:
            return C11_SIZEOF[type_str]
        if type_str.endswith("*"):
            return 8
        if type_str.endswith("]"):
            base = type_str.split("[")[0]
            return self._sizeof_type(base)
        return 4

    def _alignof_type(self, type_name):
        """Return alignment of a type in bytes."""
        if type_name is None:
            return 1
        type_str = str(type_name)
        if type_str in C11_SIZEOF:
            return C11_SIZEOF.get(type_str, 1)
        if type_str.endswith("*"):
            return 8
        return 1


# ============================================================
# Self-test
# ============================================================

if __name__ == "__main__":
    main_scope = Scope("main")
    stdio = Lib("stdio", main_scope)

    def double(x):
        print(f"double called with {x}")
        return x * 2

    printf = Callee("printf", stdio.scope, double)
    x = Callee("x", main_scope, 5)
    y = Caller("y", main_scope, 3)
    y.call(x)
    y.call(printf, x)
    print("y.eval() =", y.eval())  # 3 + 5 + 10 = 18
