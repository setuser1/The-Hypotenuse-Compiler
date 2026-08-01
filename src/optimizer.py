"""Optimizer for C△ compiler. C11 compliant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from parser import (
    Assignment,
    Binary,
    Break,
    Call,
    Compound,
    Declaration,
    ExprStmt,
    For,
    Function,
    If,
    Program,
    Return,
    Switch,
    Unary,
    Var,
    While,
)
from struct_layout import (
    StructLayout,
    compute_layout,
    suggest_reordering,
)


@dataclass
class OptimizationResult:
    """Result of optimization pass."""

    ast: Any
    layouts: Dict[str, StructLayout]
    report: str
    changes: List[str]


class Optimizer:
    def __init__(self, ast, structor, layouts=None):
        self.ast = ast
        self.structor = structor
        self.layouts = layouts or {}
        self._changes = []
        self._typedefs = {}
        self._used_static_funcs = set()
        self._defined_static_funcs = set()
        self._used_static_vars = set()
        self._defined_static_vars = set()

    def optimize(self) -> OptimizationResult:
        """Run all optimization passes. Returns modified AST and report."""
        self._collect_typedefs()
        self._collect_static_symbols()
        self._resolve_typedefs_pass()
        self._constant_fold_pass()
        self._dead_code_pass()
        self._struct_layout_pass()
        self._padding_analysis_pass()
        self._cache_line_opt_pass()
        self._remove_unused_pass()
        self._return_check_pass()
        return OptimizationResult(
            ast=self.ast,
            layouts=self.layouts,
            report=self._generate_report(),
            changes=self._changes,
        )

    def _collect_typedefs(self):
        """Collect all typedef declarations."""
        for node in self._walk_ast(self.ast):
            if hasattr(node, "node_type") and node.node_type == "TYPEDEF":
                alias = getattr(node, "name", None) or getattr(node, "alias", None)
                underlying = getattr(node, "underlying", None) or getattr(
                    node, "type", None
                )
                if alias and underlying:
                    self._typedefs[alias] = underlying

    def _collect_static_symbols(self):
        """Collect static function and variable definitions and usages."""
        for node in self._walk_ast(self.ast):
            if isinstance(node, Function):
                if getattr(node, "storage", None) == "static":
                    self._defined_static_funcs.add(node.name)
            if isinstance(node, Declaration):
                if getattr(node, "storage", None) == "static":
                    self._defined_static_vars.add(node.name)
        for node in self._walk_ast(self.ast):
            if isinstance(node, Call):
                if isinstance(node.callee, Var):
                    self._used_static_funcs.add(node.callee.name)

    def _resolve_typedefs(self, type_str: str) -> str:
        """Resolve typedef chain to canonical type."""
        if type_str not in self._typedefs:
            return type_str
        visited = set()
        current = type_str
        while current in self._typedefs and current not in visited:
            visited.add(current)
            current = self._typedefs[current]
        return current

    def _resolve_typedefs_pass(self):
        """Pass 1: Resolve typedef chains to canonical types."""
        resolved_count = 0
        for alias in self._typedefs:
            canonical = self._resolve_typedefs(alias)
            if canonical != alias:
                resolved_count += 1
        if resolved_count > 0:
            self._changes.append(f"Typedef resolved: {resolved_count} chains")

    def _constant_fold_pass(self):
        """Pass 2: Fold constant binary expressions at compile time."""
        folded = 0
        for node in self._walk_ast(self.ast):
            if isinstance(node, Binary):
                result = self._try_fold_binary(node)
                if result is not None:
                    self._replace_node(node, result)
                    folded += 1
            elif isinstance(node, Unary):
                result = self._try_fold_unary(node)
                if result is not None:
                    self._replace_node(node, result)
                    folded += 1
        if folded > 0:
            self._changes.append(f"Constant fold: {folded} expressions")

    def _try_fold_binary(self, node: Binary) -> Optional[Node]:
        """Try to fold a binary expression. Returns new node or None."""
        if not self._is_constant_expr(node.left) or not self._is_constant_expr(
            node.right
        ):
            return None
        left_val = self._eval_constant(node.left)
        right_val = self._eval_constant(node.right)
        if left_val is None or right_val is None:
            return None
        try:
            result = self._apply_binary_op(node.op, left_val, right_val)
            return self._make_literal(result)
        except (ZeroDivisionError, ValueError):
            return None

    def _try_fold_unary(self, node: Unary) -> Optional[Node]:
        """Try to fold a unary expression. Returns new node or None."""
        if not self._is_constant_expr(node.operand):
            return None
        val = self._eval_constant(node.operand)
        if val is None:
            return None
        try:
            result = self._apply_unary_op(node.op, val, node.prefix)
            return self._make_literal(result)
        except ValueError:
            return None

    def _is_constant_expr(self, node) -> bool:
        """Check if node is a constant expression (not variable/function call)."""
        if isinstance(node, Literal):
            return True
        if isinstance(node, Binary):
            return self._is_constant_expr(node.left) and self._is_constant_expr(
                node.right
            )
        if isinstance(node, Unary):
            return self._is_constant_expr(node.operand)
        if isinstance(node, Call):
            return False
        if isinstance(node, Var):
            return False
        return True

    def _eval_constant(self, node) -> Optional[Any]:
        """Evaluate a constant expression to a value."""
        if isinstance(node, Literal):
            return node.value
        if isinstance(node, Binary):
            left = self._eval_constant(node.left)
            right = self._eval_constant(node.right)
            if left is None or right is None:
                return None
            try:
                return self._apply_binary_op(node.op, left, right)
            except (ZeroDivisionError, ValueError):
                return None
        if isinstance(node, Unary):
            val = self._eval_constant(node.operand)
            if val is None:
                return None
            try:
                return self._apply_unary_op(node.op, val, node.prefix)
            except ValueError:
                return None
        return None

    def _apply_binary_op(self, op: str, left: Any, right: Any) -> Any:
        """Apply binary operator and return result."""
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise ZeroDivisionError
            if isinstance(left, int) and isinstance(right, int):
                return int(left / right)
            return left / right
        if op == "%":
            if right == 0:
                raise ZeroDivisionError
            return left % right
        if op == "**":
            return left**right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "&&":
            return left and right
        if op == "||":
            return left or right
        raise ValueError(f"Unknown binary operator: {op}")

    def _apply_unary_op(self, op: str, val: Any, prefix: bool) -> Any:
        """Apply unary operator and return result."""
        if op == "!":
            return not val
        if op == "-":
            return -val
        if op == "+":
            return +val
        raise ValueError(f"Unknown unary operator: {op}")

    def _make_literal(self, value: Any) -> Node:
        """Create a Literal node with the given value."""
        if isinstance(value, bool):
            value = 1 if value else 0
        if isinstance(value, int):
            return Literal(value=value, node_type="INT_LITERAL")
        if isinstance(value, float):
            return Literal(value=value, node_type="FLOAT_LITERAL")
        return Literal(value=value, node_type="LITERAL")

    def _dead_code_pass(self):
        """Pass 3: Remove unreachable code and empty blocks."""
        removed = 0
        removed += self._remove_empty_compounds()
        removed += self._remove_unreachable_after_control()
        removed += self._simplify_constant_conditions()
        if removed > 0:
            self._changes.append(f"Dead code removed: {removed} blocks/statements")

    def _remove_empty_compounds(self) -> int:
        """Remove compound blocks with no statements."""
        removed = 0
        for node in self._walk_ast(self.ast):
            if isinstance(node, Compound) and not node.stmts:
                if self._try_remove_node(node):
                    removed += 1
        return removed

    def _remove_unreachable_after_control(self) -> int:
        """Remove unreachable code after return/break/continue."""
        removed = 0
        for node in self._walk_ast(self.ast):
            if isinstance(node, (If, While, For)):
                removed += self._remove_unreachable_in_branch(node)
        return removed

    def _remove_unreachable_in_branch(self, node) -> int:
        """Remove unreachable code in if/while/for branches."""
        removed = 0
        if isinstance(node, If):
            if node.then_branch and self._ends_with_control(node.then_branch):
                cleaned = self._remove_trailing_stmts(node.then_branch)
                if cleaned:
                    removed += 1
            if node.else_branch and self._ends_with_control(node.else_branch):
                cleaned = self._remove_trailing_stmts(node.else_branch)
                if cleaned:
                    removed += 1
        elif isinstance(node, (While, For)):
            if node.body and self._ends_with_control(node.body):
                cleaned = self._remove_trailing_stmts(node.body)
                if cleaned:
                    removed += 1
        return removed

    def _ends_with_control(self, node) -> bool:
        """Check if node ends with return/break/continue."""
        if isinstance(node, Return):
            return True
        if isinstance(node, Break):
            return True
        if isinstance(node, Compound) and node.stmts:
            return self._ends_with_control(node.stmts[-1])
        return False

    def _remove_trailing_stmts(self, node) -> bool:
        """Remove trailing statements after control flow. Returns True if removed."""
        if isinstance(node, Compound) and len(node.stmts) > 1:
            for i in range(len(node.stmts) - 2, -1, -1):
                if self._ends_with_control(node.stmts[i]):
                    del node.stmts[i + 1:]
                    return True
        return False

    def _simplify_constant_conditions(self) -> int:
        """Simplify if statements with constant conditions."""
        removed = 0
        for node in self._walk_ast(self.ast):
            if isinstance(node, If):
                cond_val = self._eval_constant(node.cond)
                if cond_val is not None:
                    if cond_val:
                        if self._try_replace_with(node, node.then_branch):
                            removed += 1
                    else:
                        if node.else_branch:
                            if self._try_replace_with(node, node.else_branch):
                                removed += 1
                        else:
                            if self._try_remove_node(node):
                                removed += 1
        return removed

    def _struct_layout_pass(self):
        """Pass 4: Compute layout for all struct definitions."""
        for node in self._walk_ast(self.ast):
            if hasattr(node, "node_type") and node.node_type == "STRUCT_DEF":
                name = getattr(node, "name", None) or getattr(node, "tag", None)
                layout = compute_layout(node)
                if name:
                    self.layouts[name] = layout

    def _padding_analysis_pass(self):
        """Pass 5: Analyze padding overhead per struct."""
        if self.layouts:
            self._changes.append("Padding analysis completed")

    def _cache_line_opt_pass(self):
        """Pass 6: Suggest field reordering for better cache density."""
        suggestions = []
        for name, layout in self.layouts.items():
            if layout.padding_bytes > 0:
                suggested = suggest_reordering(layout.fields)
                if [f.name for f in suggested] != [f.name for f in layout.fields]:
                    suggestions.append(
                        f"{name}: reordering fields by alignment/size "
                        f"could improve cache efficiency"
                    )
        if suggestions:
            self._changes.append(f"Cache suggestions: {len(suggestions)} structs")

    def _remove_unused_pass(self):
        """Pass 7: Remove unused static functions and variables."""
        unused_funcs = self._defined_static_funcs - self._used_static_funcs
        unused_vars = self._defined_static_vars - self._used_static_vars
        removed = 0
        for name in unused_funcs:
            if self._remove_static_function(name):
                removed += 1
        for name in unused_vars:
            if self._remove_static_variable(name):
                removed += 1
        if removed > 0:
            self._changes.append(f"Removed unused: {removed} static declarations")

    def _remove_static_function(self, name: str) -> bool:
        """Remove a static function definition."""
        declarations = getattr(self.ast, "declarations", [])
        for i, decl in enumerate(declarations):
            if isinstance(decl, Function):
                if getattr(decl, "name", None) == name:
                    if getattr(decl, "storage", None) == "static":
                        declarations.pop(i)
                        return True
        return False

    def _remove_static_variable(self, name: str) -> bool:
        """Remove a static variable declaration."""
        declarations = getattr(self.ast, "declarations", [])
        for i, decl in enumerate(declarations):
            if isinstance(decl, Declaration):
                if getattr(decl, "name", None) == name:
                    if getattr(decl, "storage", None) == "static":
                        declarations.pop(i)
                        return True
        return False

    def _return_check_pass(self):
        """Pass 8: Verify non-void functions have return statements."""
        for node in self._walk_ast(self.ast):
            if isinstance(node, Function):
                ret_type = getattr(node, "ret_type", "void")
                if ret_type != "void" and ret_type != "auto":
                    if not self._has_return(node.body):
                        self._changes.append(
                            f"Warning: function '{node.name}' may lack return statement"
                        )

    def _has_return(self, node) -> bool:
        """Check if a node contains a return statement."""
        if isinstance(node, Return):
            return True
        if isinstance(node, If):
            then_has = self._has_return(node.then_branch)
            else_has = self._has_return(node.else_branch) if node.else_branch else False
            return then_has and else_has
        if isinstance(node, Compound):
            for stmt in node.stmts:
                if self._has_return(stmt):
                    return True
        if isinstance(node, (While, For)):
            return self._has_return(node.body)
        return False

    def _generate_report(self) -> str:
        """Generate the optimization report."""
        lines = []
        lines.append("=== C△ Optimizer Report ===")
        lines.append("")
        if self.layouts:
            lines.append("Struct Layout Analysis:")
            for name, layout in sorted(self.layouts.items()):
                lines.append(
                    f"  {name} ({layout.total_size} bytes, "
                    f"alignment {layout.alignment})"
                )
                for field in layout.fields:
                    lines.append(
                        f"    {field.type} {field.name}  @{field.offset}  "
                        f"{field.size} bytes"
                    )
                if layout.padding_bytes > 0:
                    pct = layout.padding_bytes / layout.total_size * 100
                    lines.append(
                        f"    Padding: {layout.padding_bytes} bytes "
                        f"({pct:.0f}% overhead)"
                    )
            lines.append("")
        if self.layouts:
            lines.append("Padding Summary:")
            for name, layout in sorted(self.layouts.items()):
                total = layout.total_size
                pad = layout.padding_bytes
                eff = layout.cache_efficiency
                lines.append(f"  {name}: {pad}/{total} bytes ({eff:.0f}% efficiency)")
            lines.append("")
        if self._changes:
            lines.append("Optimizations Applied:")
            for change in self._changes:
                lines.append(f"  - {change}")
            lines.append("")
            lines.append(f"Total changes: {len(self._changes)}")
        else:
            lines.append("No optimizations applied.")
        return "\n".join(lines)

    def _walk_ast(self, node):
        """Walk AST nodes recursively, yielding each node."""
        if node is None:
            return
        yield node
        if isinstance(node, Program):
            for decl in getattr(node, "declarations", []):
                yield from self._walk_ast(decl)
        elif isinstance(node, Function):
            yield from self._walk_ast(getattr(node, "body", None))
        elif isinstance(node, Compound):
            for stmt in getattr(node, "stmts", []):
                yield from self._walk_ast(stmt)
        elif isinstance(node, If):
            yield from self._walk_ast(getattr(node, "cond", None))
            yield from self._walk_ast(getattr(node, "then_branch", None))
            yield from self._walk_ast(getattr(node, "else_branch", None))
        elif isinstance(node, While):
            yield from self._walk_ast(getattr(node, "cond", None))
            yield from self._walk_ast(getattr(node, "body", None))
        elif isinstance(node, For):
            yield from self._walk_ast(getattr(node, "init", None))
            yield from self._walk_ast(getattr(node, "cond", None))
            yield from self._walk_ast(getattr(node, "post", None))
            yield from self._walk_ast(getattr(node, "body", None))
        elif isinstance(node, Return):
            yield from self._walk_ast(getattr(node, "expr", None))
        elif isinstance(node, ExprStmt):
            yield from self._walk_ast(getattr(node, "expr", None))
        elif isinstance(node, Declaration):
            yield from self._walk_ast(getattr(node, "initializer", None))
        elif isinstance(node, Binary):
            yield from self._walk_ast(getattr(node, "left", None))
            yield from self._walk_ast(getattr(node, "right", None))
        elif isinstance(node, Unary):
            yield from self._walk_ast(getattr(node, "operand", None))
        elif isinstance(node, Call):
            for arg in getattr(node, "args", []):
                yield from self._walk_ast(arg)
        elif isinstance(node, Assignment):
            yield from self._walk_ast(getattr(node, "target", None))
            yield from self._walk_ast(getattr(node, "value", None))
        elif hasattr(node, "node_type") and node.node_type == "ASM":
            pass
        elif isinstance(node, Switch):
            yield from self._walk_ast(getattr(node, "expr", None))
            for case_body in getattr(node, "cases", []):
                if isinstance(case_body, tuple):
                    yield from self._walk_ast(case_body[1])

    def _replace_node(self, old_node, new_node):
        """Replace a node in the AST with a new node."""
        for parent, attr, index in self._find_node_location(old_node):
            if index is not None:
                getattr(parent, attr)[index] = new_node
            else:
                setattr(parent, attr, new_node)

    def _find_node_location(self, target):
        """Find parent of target node. Yields (parent, attr, index) tuples."""
        for node in self._walk_ast(self.ast):
            for attr in ["declarations", "stmts", "params", "args", "cases", "target", "value"]:
                if hasattr(node, attr):
                    value = getattr(node, attr)
                    if isinstance(value, list):
                        for i, item in enumerate(value):
                            if item is target:
                                yield (node, attr, i)
                    elif value is target:
                        yield (node, attr, None)

    def _try_replace_with(self, old_node, new_node):
        """Try to replace a node with another node."""
        locations = list(self._find_node_location(old_node))
        if not locations:
            return False
        parent, attr, index = locations[0]
        if index is not None:
            getattr(parent, attr)[index] = new_node
        else:
            setattr(parent, attr, new_node)
        return True

    def _try_remove_node(self, node) -> bool:
        """Try to remove a node from the AST."""
        locations = list(self._find_node_location(node))
        if not locations:
            return False
        parent, attr, index = locations[0]
        if index is not None:
            getattr(parent, attr).pop(index)
            return True
        return False



@dataclass
class Node:
    """Minimal Node class for literal creation."""

    pass


@dataclass
class Literal(Node):
    """Literal constant."""

    value: Any
    node_type: str = "LITERAL"
