"""C11 code generator for C△ compiler."""

from parser import (
    Function,
    Declaration,
    Compound,
    If,
    While,
    Do,
    For,
    Return,
    Break,
    Continue,
    Goto,
    Label,
    ExprStmt,
    Binary,
    Unary,
    Literal,
    Var,
    Call,
    ArrayAccess,
    Cast,
    Assignment,
    Include,
    InitList,
    Switch,
    StructDef,
    Typedef,
    FieldAccess,
    DesignatedInit,
    TypeExpr,
    Generic,
    CompoundLiteral,
)


TYPE_MAP = {
    "string": "char*",
    "int": "int",
    "float": "float",
    "double": "double",
    "char": "char",
    "void": "void",
    "short": "short",
    "long": "long",
    "signed": "signed",
    "unsigned": "unsigned",
}


class CodeGen:
    def __init__(self, ast, structor, layouts=None):
        self.ast = ast
        self.structor = structor
        self.layouts = layouts or {}
        self._lines = []
        self._indent = 0

    def generate(self) -> str:
        """Main entry point. Returns generated C code as string."""
        self._lines = []
        self._gen_program(self.ast)
        return "\n".join(self._lines)

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    def _emit(self, line: str = ""):
        """Emit one complete source line at the current indent level."""
        indent = "    " * self._indent
        self._lines.append(indent + line)

    def _emit_raw(self, text: str):
        """Emit a pre-indented block of text verbatim (e.g. asm blocks)."""
        for line in text.splitlines():
            self._lines.append(line)

    # ------------------------------------------------------------------
    # Type mapping
    # ------------------------------------------------------------------

    def _map_type(self, typ: str) -> str:
        """Map C△ type to C type."""
        if not typ:
            return typ
        if typ.startswith("dynam "):
            typ = typ[7:]
        if typ.startswith("tuple "):
            typ = typ[6:]
        if typ == "string":
            return "char*"
        return TYPE_MAP.get(typ, typ)

    def _contains_assignment(self, node) -> bool:
        """Recursively check if an expression contains an assignment."""
        if node is None:
            return False
        if isinstance(node, Assignment):
            return True
        if isinstance(node, Binary):
            return self._contains_assignment(node.left) or self._contains_assignment(
                node.right
            )
        if isinstance(node, Unary):
            return self._contains_assignment(node.operand)
        if isinstance(node, Call):
            return any(self._contains_assignment(a) for a in node.args)
        return False

    # ------------------------------------------------------------------
    # Expression serialiser
    # ------------------------------------------------------------------

    def _expr(self, node) -> str:
        """Recursively serialise an expression node to a C string.

        This is the single source of truth for expression rendering.
        All statement generators call this rather than recursing through
        _gen_node, which avoids the interleaved-emit ordering bugs that
        arise when half the code uses end='' streaming and the other half
        uses full-line emission.
        """
        if node is None:
            return ""

        if isinstance(node, Literal):
            val = node.value
            if isinstance(val, str):
                # Already a string lexeme — pass through as-is if it looks
                # like a number or a quoted literal; otherwise wrap in quotes.
                stripped = val.lstrip("-")
                if (
                    stripped.startswith("0x")
                    or stripped.startswith("0X")
                    or stripped.startswith("0b")
                    or stripped.startswith("0B")
                    or stripped.isdigit()
                    or stripped.replace(".", "", 1).isdigit()
                    or val.startswith('"')
                    or val.startswith("'")
                    or any(
                        stripped.rstrip("uUlLfF").replace(".", "", 1).isdigit()
                        for _ in [None]
                    )
                ):
                    return val
                return f'"{val}"'
            return str(val)

        if isinstance(node, Var):
            return node.name

        if isinstance(node, TypeExpr):
            return self._map_type(node.type_name)

        if isinstance(node, Binary):
            if node.op == "?:":
                # Ternary: condition ?  true_val : false_val
                # Parser encodes as Binary("?:", cond, Binary("branch", t, f))
                cond = self._expr(node.left)
                if isinstance(node.right, Binary) and node.right.op == "branch":
                    true_val = self._expr(node.right.left)
                    false_val = self._expr(node.right.right)
                    return f"({cond}) ? {true_val} : {false_val}"
                return f"({cond}) ? {self._expr(node.right)}"
            left = self._expr(node.left)
            right = self._expr(node.right)
            # Wrap the whole expression in parens when the operator has lower
            # precedence than what surrounds it — simple heuristic: always
            # parenthesise compound binary sub-expressions.
            return f"{left} {node.op} {right}"

        if isinstance(node, Unary):
            if node.op == "sizeof":
                operand = self._expr(node.operand)
                return f"sizeof({operand})"
            operand = self._expr(node.operand)
            if node.prefix:
                return f"{node.op}{operand}"
            return f"{operand}{node.op}"

        if isinstance(node, Assignment):
            target = self._expr(node.target)
            value = self._expr(node.value)
            return f"{target} = {value}"

        if isinstance(node, Call):
            callee = (
                node.callee.name
                if isinstance(node.callee, Var)
                else self._expr(node.callee)
            )
            args = ", ".join(self._expr(a) for a in node.args)
            return f"{callee}({args})"

        if isinstance(node, ArrayAccess):
            arr = self._expr(node.array)
            idx = self._expr(node.index)
            return f"{arr}[{idx}]"

        if isinstance(node, Cast):
            operand = self._expr(node.operand)
            return f"({node.cast_type}){operand}"

        if isinstance(node, FieldAccess):
            obj = self._expr(node.obj)
            return f"{obj}.{node.field_name}"

        if isinstance(node, InitList):
            elems = ", ".join(self._expr(e) for e in node.elements)
            return f"{{{elems}}}"

        if isinstance(node, DesignatedInit):
            return f".{node.field} = {self._expr(node.value)}"

        if isinstance(node, CompoundLiteral):
            typ = self._map_type(node.lit_type)
            elems = ", ".join(self._expr(e) for e in node.elements)
            return f"({typ}){{{elems}}}"

        if isinstance(node, Generic):
            expr = self._expr(node.expr)
            assocs = ", ".join(f"{t}: {self._expr(v)}" for t, v in node.associations)
            return f"_Generic({expr}, {assocs})"

        # Fallback
        return f"/* unknown expr: {node.__class__.__name__} */"

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def _gen_program(self, node):
        for decl in node.declarations:
            self._gen_node(decl)

    # ------------------------------------------------------------------
    # Statement / declaration dispatcher
    # ------------------------------------------------------------------

    def _gen_node(self, node):
        """Dispatch to the appropriate generator."""
        if isinstance(node, Function):
            self._gen_function(node)
        elif isinstance(node, Declaration):
            self._gen_declaration(node)
        elif isinstance(node, Compound):
            self._gen_compound_block(node)
        elif isinstance(node, If):
            self._gen_if(node)
        elif isinstance(node, While):
            self._gen_while(node)
        elif isinstance(node, Do):
            self._gen_do(node)
        elif isinstance(node, For):
            self._gen_for(node)
        elif isinstance(node, Return):
            self._gen_return(node)
        elif isinstance(node, Break):
            self._emit("break;")
        elif isinstance(node, Continue):
            self._emit("continue;")
        elif isinstance(node, Goto):
            self._emit(f"goto {node.label};")
        elif isinstance(node, Label):
            # Labels are dedented by one level in C convention
            indent = "    " * max(0, self._indent - 1)
            self._lines.append(f"{indent}{node.name}:")
        elif isinstance(node, ExprStmt):
            self._gen_expr_stmt(node)
        elif isinstance(node, Include):
            self._gen_include(node)
        elif isinstance(node, Switch):
            self._gen_switch(node)
        elif isinstance(node, StructDef):
            self._gen_struct_def(node)
        elif isinstance(node, Typedef):
            self._gen_typedef(node)
        elif hasattr(node, "node_type") and node.node_type == "ASM":
            self._gen_asm_block(node)
        elif hasattr(node, "__class__") and node.__class__.__name__ == "AsmBlock":
            self._gen_asm_block(node)
        else:
            # Expression used as a statement (e.g. bare assignment at top level)
            self._emit(f"{self._expr(node)};")

    # ------------------------------------------------------------------
    # Statement generators
    # ------------------------------------------------------------------

    def _gen_function(self, node: Function):
        ret_type = self._map_type(node.ret_type)
        params = []
        for ptype, pname in node.params:
            if ptype == "...":
                params.append("...")
            else:
                params.append(f"{self._map_type(ptype)} {pname}")
        param_str = ", ".join(params) if params else "void"
        self._emit(f"{ret_type} {node.name}({param_str}) {{")
        self._indent += 1
        if isinstance(node.body, Compound):
            for stmt in node.body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.body)
        self._indent -= 1
        self._emit("}")
        self._emit("")  # blank line after function

    def _gen_declaration(self, node: Declaration):
        typ = self._map_type(node.var_type)
        name = node.name
        array_size = getattr(node, "array_size", None)
        if array_size is not None:
            if isinstance(array_size, list):
                dims = "".join(f"[{s}]" for s in array_size)
                name = f"{node.name}{dims}"
            else:
                name = f"{node.name}[{array_size}]"
        if node.initializer is not None:
            val = self._expr(node.initializer)
            self._emit(f"{typ} {name} = {val};")
        else:
            self._emit(f"{typ} {name};")

    def _gen_compound_block(self, node: Compound):
        """Emit a braced block.  Used when a Compound appears as a standalone
        statement rather than as a function body (which is handled inline)."""
        self._emit("{")
        self._indent += 1
        for stmt in node.stmts:
            self._gen_node(stmt)
        self._indent -= 1
        self._emit("}")

    def _gen_if(self, node: If):
        cond = self._expr(node.cond)
        self._emit(f"if ({cond}) {{")
        self._indent += 1
        body = node.then_branch
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        if node.else_branch is not None:
            self._emit("} else {")
            self._indent += 1
            if isinstance(node.else_branch, Compound):
                for stmt in node.else_branch.stmts:
                    self._gen_node(stmt)
            else:
                self._gen_node(node.else_branch)
            self._indent -= 1
            self._emit("}")
        else:
            self._emit("}")

    def _gen_while(self, node: While):
        cond = self._expr(node.cond)
        # Wrap condition in extra parens ONLY if it contains an assignment
        has_assignment = isinstance(node.cond, Assignment) or (
            isinstance(node.cond, Binary) and self._contains_assignment(node.cond)
        )
        if has_assignment:
            self._emit(f"while (({cond})) {{")
        else:
            self._emit(f"while ({cond}) {{")
        self._indent += 1
        body = node.body
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        self._emit("}")

    def _gen_do(self, node: Do):
        cond = self._expr(node.cond)
        self._emit("do {")
        self._indent += 1
        body = node.body
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        self._emit(f"}} while ({cond});")

    def _gen_for(self, node: For):
        # Init clause
        if node.init is None:
            init_str = ""
        elif isinstance(node.init, Declaration):
            typ = self._map_type(node.init.var_type)
            name = node.init.name
            if node.init.initializer is not None:
                init_str = f"{typ} {name} = {self._expr(node.init.initializer)}"
            else:
                init_str = f"{typ} {name}"
        else:
            init_str = self._expr(node.init)

        cond_str = self._expr(node.cond) if node.cond else ""
        post_str = self._expr(node.post) if node.post else ""

        self._emit(f"for ({init_str}; {cond_str}; {post_str}) {{")
        self._indent += 1
        body = node.body
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        self._emit("}")

    def _gen_return(self, node: Return):
        if node.expr is not None:
            self._emit(f"return {self._expr(node.expr)};")
        else:
            self._emit("return;")

    def _gen_expr_stmt(self, node: ExprStmt):
        if node.expr is not None:
            self._emit(f"{self._expr(node.expr)};")

    def _gen_include(self, node: Include):
        if node.is_system:
            self._emit(f"#include <{node.path}>")
        else:
            self._emit(f'#include "{node.path}"')

    def _gen_switch(self, node: Switch):
        expr = self._expr(node.expr)
        self._emit(f"switch ({expr}) {{")
        self._indent += 1
        for case_val, body in node.cases:
            if case_val is None:
                self._emit("default:")
            else:
                self._emit(f"case {self._expr(case_val)}:")
            self._indent += 1
            if isinstance(body, Compound):
                for stmt in body.stmts:
                    self._gen_node(stmt)
            else:
                self._gen_node(body)
            self._indent -= 1
        self._indent -= 1
        self._emit("}")

    def _gen_struct_def(self, node):
        name = getattr(node, "name", "") or ""
        fields = getattr(node, "fields", []) or []
        header = f"struct {name}" if name else "struct"
        self._emit(f"{header} {{")
        self._indent += 1
        for field_type, field_name in fields:
            self._emit(f"{field_type} {field_name};")
        self._indent -= 1
        self._emit("};")  # struct definition always ends with ;

    def _gen_typedef(self, node):
        actual = getattr(node, "actual_type", "")
        alias = getattr(node, "alias", "")
        self._emit(f"typedef {actual} {alias};")

    def _gen_asm_block(self, node):
        """Pass asm blocks through verbatim."""
        content = getattr(node, "content", "") or str(node)
        self._emit_raw(content)
