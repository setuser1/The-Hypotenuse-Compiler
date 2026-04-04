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
)


# ============================================================
# Scope / graph nodes
# ============================================================


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
            raise ValueError(
                f"Child named `{node.name}` already exists in scope `{self.name}`"
            )
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

    def __init__(self, name, scope, value, var_type=None):
        super().__init__(name, scope)
        self.value = value
        self.var_type = var_type  # Store variable type for pointers

    def __repr__(self):
        val_repr = repr(self.value)
        # Determine kind based on type (for pointers) or value
        if self.var_type and "*" in self.var_type:
            kind = f"{self.var_type}"
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


class Caller(Node):
    """A node that depends on and calls other nodes."""

    def __init__(self, name, scope, value=None):
        super().__init__(name, scope)
        self.value = value
        self.callee_children: dict | None = None

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


# ============================================================
# Callee value display (issue #83)
# ============================================================


def callee_value_display_parts(value):
    """Return (kind_label, repr_string) for a Callee.value."""
    if value is None:
        return "unknown", "None"
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
    return "other", repr(value)


# ============================================================
# Literal value extraction from AST expressions
# ============================================================


def _is_int_const(x):
    """True for plain int constants (not bool, which is a Python int subclass)."""
    return type(x) is int


def _c_int_div(a: int, b: int) -> int:
    """C integer division: truncates toward zero (C99), not Python floor division."""
    c = abs(a) // abs(b)
    if (a < 0) ^ (b < 0):
        c = -c
    return c


def _c_int_mod(a: int, b: int) -> int:
    """C integer remainder: a - (a/b)*b using truncation division (C99)."""
    return a - _c_int_div(a, b) * b


def _numeric_binary(op, left, right):
    """Apply a binary op to two numeric constants; None if unsupported or invalid.

    Integer ``/`` and ``%`` follow C99 truncation-toward-zero rules, not Python's
    ``//`` (floor) or ``%`` (divisor-sign remainder).
    """
    if right == 0 and op in ("/", "%"):
        return None
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
    return None


def _extract_literal(expr):
    """Return a Python value from a simple AST expression, or None.

    Handles:
    - Literal nodes          -> the literal value cast to int/float where possible
    - Unary('-', Literal)    -> negative numeric literal (fix for issue #61)
    - Unary('+', Literal)    -> unary plus on a constant
    - Unary('&' / '*', ...)  -> no constant value (issue #87 groundwork)
    - Binary on constants    -> folded + - * / ** % (issue #43)
    - Anything else          -> None (non-constant expression)
    """
    if isinstance(expr, Literal):
        return _cast_literal(expr.value)
    if isinstance(expr, Unary) and expr.prefix:
        if expr.op == "-":
            inner = _extract_literal(expr.operand)
            if isinstance(inner, (int, float)):
                return -inner
        elif expr.op == "+":
            inner = _extract_literal(expr.operand)
            if isinstance(inner, (int, float)):
                return inner
        elif expr.op in ("&", "*"):
            return None
    if isinstance(expr, Binary):
        left = _extract_literal(expr.left)
        right = _extract_literal(expr.right)
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

    Scope rules (matching C scoping semantics):
    - ``Program``    -> root ``program`` scope
    - ``Function``   -> named child scope pushed for the function body
    - ``For``        -> anonymous ``for_<name>`` child scope covering the
                        init declaration *and* the loop body (fix for issue
                        where ``int i`` leaked into the enclosing scope)
    - ``Compound`` / ``If`` / ``While`` bodies share the enclosing scope
    """

    def __init__(self, ast: Program):
        self.ast = ast
        self.objects = {}
        self._order = {}
        self._counter = 0
        self._func_callee_stack: list = []

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
        user_funcs = {d.name for d in self.ast.declarations if isinstance(d, Function)}
        self._seed_stdlib(program_scope, skip=user_funcs)
        self._walk_program(self.ast, program_scope)
        self._link_callee_children()
        sorted_keys = sorted(self._order, key=lambda k: self._order[k])
        return [self.objects[k] for k in sorted_keys]

    # ------------------------------------------------------------------
    # Walkers
    # ------------------------------------------------------------------

    def _seed_stdlib(self, scope: Scope, skip: set | frozenset | None = None):
        """Register common libc symbols so calls resolve without lazy stubs (issue #88)."""
        skip = skip or frozenset()
        for name in ("printf",):
            if name in skip:
                continue
            if name in scope.callees:
                continue
            callee = Callee(name, scope, None)
            self._register(callee, scope)

    def _walk_program(self, node: Program, scope: Scope):
        for decl in node.declarations:
            self._walk_node(decl, scope)

    def _walk_node(self, node, scope: Scope):
        """Dispatch to the appropriate walker based on AST node type."""
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
                    v = _extract_literal(node.expr)
                    if v is not None:
                        self._func_callee_stack[-1].value = v
        elif isinstance(node, ExprStmt):
            if node.expr is not None:
                self._walk_expr(node.expr, scope)
        elif isinstance(
            node, (Assignment, Binary, Unary, Call, ArrayAccess, Var, Literal)
        ):
            self._walk_expr(node, scope)
        # Other node types (Break, Continue, etc.) have no graph impact yet

    def _walk_function(self, node: Function, parent_scope: Scope):
        """Register function as a Callee in the parent scope, then walk its
        body in a new child scope named after the function."""
        callee = Callee(node.name, parent_scope, None)
        self._register(callee, parent_scope)
        func_scope = Scope(node.name, parent_scope)
        self._func_callee_stack.append(callee)
        try:
            self._walk_compound(node.body, func_scope)
        finally:
            self._func_callee_stack.pop()

    def _walk_declaration(self, node: Declaration, scope: Scope):
        """Register a variable declaration as a Callee with its initial value."""
        value = (
            _extract_literal(node.initializer) if node.initializer is not None else None
        )
        callee = Callee(node.name, scope, value, var_type=node.var_type)
        self._register(callee, scope)
        # Also walk initializer for any embedded calls
        if node.initializer is not None:
            self._walk_expr(node.initializer, scope)

    def _walk_for(self, node: For, parent_scope: Scope):
        """Push a new scope for the for-loop so that the init declaration
        (e.g. 'int i = 0') is scoped to the loop, not the enclosing function.
        The loop body shares the same for-scope."""
        for_scope = Scope(f"for_{self._next_id()}", parent_scope)
        if node.init is not None:
            self._walk_node(node.init, for_scope)
        if node.cond is not None:
            self._walk_expr(node.cond, for_scope)
        if node.post is not None:
            self._walk_expr(node.post, for_scope)
        self._walk_node(node.body, for_scope)

    def _walk_compound(self, node: Compound, scope: Scope):
        """Walk all statements in a block. Does NOT push a new scope —
        the caller is responsible for creating the appropriate scope."""
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
        """Walk an expression node, registering any Call nodes as Callers."""
        if isinstance(node, Call):
            self._walk_call(node, scope)
        elif isinstance(node, Assignment):
            self._walk_expr(node.target, scope)
            self._walk_expr(node.value, scope)
        elif isinstance(node, Binary):
            self._walk_expr(node.left, scope)
            self._walk_expr(node.right, scope)
        elif isinstance(node, Unary):
            self._walk_expr(node.operand, scope)
        elif isinstance(node, ArrayAccess):
            self._walk_expr(node.array, scope)
            self._walk_expr(node.index, scope)
        # Var and Literal have no sub-expressions to walk

    def _walk_call(self, node: Call, scope: Scope):
        """Register a function call as a Caller node linked to its Callee."""
        # Resolve callee name
        if isinstance(node.callee, Var):
            callee_name = node.callee.name
        else:
            # Complex callee expression (e.g. function pointer) — walk it and skip
            self._walk_expr(node.callee, scope)
            for arg in node.args:
                self._walk_expr(arg, scope)
            return

        # Look up or lazily create the Callee node
        callee_key = self._obj_key(callee_name, scope)
        callee_node = self.objects.get(callee_key)
        if callee_node is None:
            # Search up the scope chain
            found = scope.called(callee_name)
            if found is not None and isinstance(found, Callee):
                callee_node = found
            else:
                # Forward declaration / extern — register lazily in current scope
                callee_node = Callee(callee_name, scope, None)
                self._register(callee_node, scope)

        # Build arg list (raw AST nodes for now)
        args = list(node.args)

        caller_name = f"call_{callee_name}_{self._next_id()}"
        caller = Caller(caller_name, scope)
        caller.call(callee_node, *args)
        self._register(caller, scope)

        # Walk args for nested calls
        for arg in node.args:
            self._walk_expr(arg, scope)

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _link_callee_children(self):
        """Link each Caller to its callee's child scope for downstream use."""
        for obj in self.objects.values():
            if isinstance(obj, Caller) and obj.dependencies:
                callee_node = obj.dependencies[0][0]
                obj.callee_children = {
                    "callees": callee_node.scope.callees,
                    "callers": callee_node.scope.callers,
                    "generic": callee_node.scope.children,
                }


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
