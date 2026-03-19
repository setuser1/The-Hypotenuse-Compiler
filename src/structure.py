class Scope:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = {}  # generic children (non-Callee/Caller)
        self.callees = {}  # name -> Callee objects
        self.callers = {}  # name -> Caller objects

    def __repr__(self):
        """Readable representation showing the scope name and its parent."""
        parent_name = self.parent.name if self.parent else None
        return f"Scope(name={self.name!r}, parent={parent_name!r})"

    def add_child(self, node):
        """Register a node in the appropriate collection.

        * Callee -> ``self.callees``
        * Caller -> ``self.callers``
        * Anything else -> ``self.children``
        """
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
        if name in self.children:
            return self.children[name]
        if name in self.callees:
            return self.callees[name]
        if name in self.callers:
            return self.callers[name]
        if self.parent:
            return self.parent.called(name)
        return None


class Node:
    """Base node for values and dependencies."""

    def __init__(self, name, scope):
        self.name = name
        self.scope = scope
        self.scope.add_child(self)
        self.dependencies = []

    def eval(self):
        raise NotImplementedError


class Callee(Node):
    """Node that provides a value or a function."""

    def __init__(self, name, scope, value):
        super().__init__(name, scope)
        self.value = value

    def __repr__(self):
        val_repr = (
            repr(self.value)
            if not isinstance(self.value, Node)
            else f"<Node {type(self.value).__name__}>"
        )
        return (
            f"Callee(name={self.name!r}, value={val_repr}, scope={self.scope.name!r})"
        )

    def eval(self, *args, **kwargs):
        if callable(self.value):
            resolved_args = [
                arg.eval() if isinstance(arg, Node) else arg for arg in args
            ]
            return self.value(*resolved_args)
        if isinstance(self.value, Node):
            return self.value.eval()
        return self.value


class Caller(Node):
    """Node that can depend on other nodes and call function nodes."""

    def __init__(self, name, scope, value=None):
        super().__init__(name, scope)
        self.value = value
        self.callee_children: dict | None = None

    def __repr__(self):
        if not self.dependencies:
            return f"Caller(name={self.name!r}, scope={self.scope.name!r}, args=[])"
        callee_node, args = self.dependencies[0]
        args_repr = []
        for arg_tokens in args:
            token_strs = ", ".join(f"{t[0]}:{t[1]!r}" for t in arg_tokens)
            args_repr.append(f"[{token_strs}]")
        return (
            f"Caller(name={self.name!r}, scope={self.scope.name!r}, "
            f"callee={callee_node.name!r}, args={args_repr})"
        )

    def call(self, node, *args):
        """Depend on a node. Arguments can be nodes or literals."""
        self.dependencies.append((node, args))

    def eval(self):
        if isinstance(self.value, Node):
            result = self.value.eval()
        else:
            result = self.value if isinstance(self.value, (int, float)) else 0

        for node, args in self.dependencies:
            if node is None:
                raise ValueError(f"callee '{node.name}' not found")
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


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r})"


class Structor:
    """Automatically structures each line of code.

    The parser implementation is injected via the ``parser`` argument to the
    constructor, removing the need for a hard-coded import.
    """

    def __init__(self, tokens_array, parser):
        self.tokens = tokens_array
        self.pos = 0
        self.objects = {}
        self.parser = parser

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def match(self, *types):
        tok = self.peek()
        if tok is None:
            return None
        tok_type = tok[0] if isinstance(tok, tuple) else getattr(tok, "type", None)
        if tok_type in types:
            return self.advance()
        return None

    def collect_args(self):
        """Collect function-call arguments as lists of raw tokens."""
        raw_args = []
        current = []
        while True:
            tok_peek = self.peek()
            if tok_peek is None:
                break
            t_type = (
                tok_peek[0]
                if isinstance(tok_peek, tuple)
                else getattr(tok_peek, "type", None)
            )
            if t_type == "RPAREN":
                break
            tok = self.advance()
            if isinstance(tok, tuple):
                t_type = tok[0]
            else:
                t_type = getattr(tok, "type", None)
            if t_type == "COMMA":
                raw_args.append(current)
                current = []
                continue
            current.append(tok)
        if current:
            raw_args.append(current)
        # Fix: peek() returns a (type, value) tuple, not a bare string.
        # Use _type() style check so the closing ')' is actually consumed.
        nxt = self.peek()
        if nxt is not None and (
            nxt[0] if isinstance(nxt, tuple) else getattr(nxt, "type", None)
        ) == "RPAREN":
            self.advance()
        return raw_args

    # ------------------------------------------------------------------
    # Helper: parse a numeric literal value from a token list.
    # Handles optional leading MINUS for negative numbers.
    # Fix for issue #61: correctly resolves '-500' instead of '-'.
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_literal_value(value_tokens, _type_fn, _value_fn):
        """Return a Python int/float/str from a list of value tokens.

        Recognises an optional leading MINUS token so that '-500' is stored
        as the integer -500 rather than the string '-'.
        """
        if not value_tokens:
            return None

        is_negative = False
        token_iter = iter(value_tokens)
        first = next(token_iter, None)

        if _type_fn(first) == "MINUS":
            second = next(token_iter, None)
            if second is not None and _type_fn(second) in ("INT_LITERAL", "FLOAT_LITERAL"):
                is_negative = True
                first = second
            else:
                # Not a negative literal - fall through and store raw value
                return _value_fn(first)

        val_type = _type_fn(first)
        val_content = _value_fn(first)

        if val_type == "INT_LITERAL" and val_content is not None:
            try:
                result = int(val_content)
            except ValueError:
                result = float(val_content)
            return -result if is_negative else result

        if val_type == "FLOAT_LITERAL" and val_content is not None:
            try:
                result = float(val_content)
            except ValueError:
                result = val_content
            return -result if is_negative else result

        if val_type == "STRING_LITERAL" and val_content is not None:
            return val_content

        return val_content

    def build_and_sort(self):
        """Create Callee and Caller objects from the token stream and order them.

        Fix for issue #62: tracks current_scope so that symbols declared
        inside a function body are registered in the function's own scope
        rather than the global program scope.
        """
        program = Scope("program")
        # Fix #62: maintain a scope stack so nested scopes work correctly.
        # current_scope starts as the program scope and is pushed/popped as
        # function bodies are entered and exited.
        #
        # NOTE: only function-definition braces push a new scope. Control-flow
        # braces (if/while/for) intentionally share the enclosing function
        # scope so that variables declared inside them are visible in the
        # same function body — matching C scoping semantics at this stage.
        # When full block-scope support is needed, introduce a scope_kind tag.
        scope_stack = [program]
        # Track which LBRACE pushes were function-scope pushes so we only
        # pop on the matching RBRACE.
        is_function_scope = [False]  # parallel stack; index 0 = program (never popped)

        def current_scope():
            return scope_stack[-1]

        self._order = {}

        # Unique key for objects that may appear in multiple scopes
        def obj_key(name, scope):
            return f"{scope.name}::{name}"

        def _type(tok):
            if tok is None:
                return None
            if isinstance(tok, tuple):
                return tok[0]
            return getattr(tok, "type", None)

        def _value(tok):
            if tok is None:
                return None
            if isinstance(tok, tuple):
                return tok[1]
            return getattr(tok, "value", getattr(tok, "lexeme", None))

        TYPE_KEYWORDS = (
            "IF", "ELSE", "WHILE", "FOR", "RETURN", "BREAK", "CONTINUE",
            "SWITCH", "CASE", "DEFAULT", "DO", "GOTO",
            "INT", "CHAR", "VOID", "FLOAT", "DOUBLE", "SHORT", "LONG",
            "SIGNED", "UNSIGNED", "STRUCT", "UNION", "ENUM", "TYPEDEF",
            "STATIC", "CONST", "VOLATILE", "EXTERN", "INLINE", "REGISTER",
            "AUTO", "SIZEOF", "RESTRICT", "BOOLEAN",
        )

        while True:
            cur = self.peek()
            if cur is None:
                break

            typ = _type(cur)
            val = _value(cur)

            # ----------------------------------------------------------
            # Handle closing brace: only pop if this was a function scope
            # ----------------------------------------------------------
            if typ == "RBRACE":
                self.advance()
                if len(scope_stack) > 1 and is_function_scope[-1]:
                    scope_stack.pop()
                    is_function_scope.pop()
                continue

            # ----------------------------------------------------------
            # Handle opening brace that is NOT part of a function def
            # (e.g. if/while bodies): advance but do NOT push a new scope
            # ----------------------------------------------------------
            if typ == "LBRACE":
                self.advance()
                is_function_scope.append(False)
                continue

            # ----------------------------------------------------------
            # Type-keyword-led declarations: int x = -500;
            # Also detects function definitions: int main() { ...
            # Fix #61: use _parse_literal_value for correct negative numbers.
            # Fix #62: function body opens a new scope.
            # ----------------------------------------------------------
            if typ in TYPE_KEYWORDS:
                self.advance()
                name_tok = self.peek()
                if _type(name_tok) == "IDENTIFIER":
                    name = _value(name_tok)
                    self.advance()  # consume identifier

                    # Function definition: int main() {
                    if _type(self.peek()) == "LPAREN":
                        self.advance()  # consume '('
                        # Skip parameter list
                        depth = 1
                        while depth > 0:
                            t = self.peek()
                            if t is None:
                                break
                            if _type(t) == "LPAREN":
                                depth += 1
                            elif _type(t) == "RPAREN":
                                depth -= 1
                            self.advance()
                        # Register function as a Callee in the current (parent) scope
                        func_callee = Callee(name, current_scope(), None)
                        key = obj_key(name, current_scope())
                        self.objects[key] = func_callee
                        self._order.setdefault(key, self.pos)
                        # If followed by '{', push a new function scope
                        if _type(self.peek()) == "LBRACE":
                            self.advance()  # consume '{'
                            func_scope = Scope(name, current_scope())
                            scope_stack.append(func_scope)
                            is_function_scope.append(True)
                        continue

                    # Variable declaration with initializer
                    if self.match("ASSIGN"):
                        value_tokens = []
                        while True:
                            nxt_tok = self.peek()
                            if nxt_tok is None or _type(nxt_tok) == "SEMICOLON":
                                break
                            self.advance()
                            value_tokens.append(nxt_tok)
                        assigned_value = self._parse_literal_value(value_tokens, _type, _value)
                        var_callee = Callee(name, current_scope(), assigned_value)
                        key = obj_key(name, current_scope())
                        self.objects[key] = var_callee
                        self._order.setdefault(key, self.pos)
                        if _type(self.peek()) == "SEMICOLON":
                            self.advance()
                    else:
                        var_callee = Callee(name, current_scope(), None)
                        key = obj_key(name, current_scope())
                        self.objects[key] = var_callee
                        self._order.setdefault(key, self.pos)
                continue

            # ----------------------------------------------------------
            # Identifier-led statements
            # ----------------------------------------------------------
            if typ == "IDENTIFIER":
                name = val
                self.advance()
                nxt = self.peek()
                nxt_type = _type(nxt)

                # Variable assignment: x = -500;
                # Fix #61: use _parse_literal_value for correct negative numbers.
                if nxt_type == "ASSIGN":
                    self.advance()  # consume '='
                    value_tokens = []
                    while True:
                        nxt_tok = self.peek()
                        if nxt_tok is None or _type(nxt_tok) == "SEMICOLON":
                            break
                        self.advance()
                        value_tokens.append(nxt_tok)
                    assigned_value = self._parse_literal_value(value_tokens, _type, _value)
                    var_callee = Callee(name, current_scope(), assigned_value)
                    key = obj_key(name, current_scope())
                    self.objects[key] = var_callee
                    self._order.setdefault(key, self.pos)
                    if _type(self.peek()) == "SEMICOLON":
                        self.advance()
                    continue

                # Function call: printf("hello");
                if nxt_type == "LPAREN":
                    self.advance()  # consume '('
                    args = self.collect_args()
                    # Resolve or lazily create the callee in the nearest scope
                    lookup_key = obj_key(name, current_scope())
                    callee_node = self.objects.get(lookup_key)
                    if callee_node is None:
                        # Try program scope as fallback
                        program_key = obj_key(name, program)
                        callee_node = self.objects.get(program_key)
                    if callee_node is None:
                        callee_node = Callee(name, current_scope(), None)
                        lookup_key = obj_key(name, current_scope())
                        self.objects[lookup_key] = callee_node
                        self._order.setdefault(lookup_key, self.pos)
                    caller_name = f"call_{name}_{self.pos}"
                    caller_node = Caller(caller_name, current_scope())
                    caller_node.call(callee_node, *args)
                    caller_key = obj_key(caller_name, current_scope())
                    self.objects[caller_key] = caller_node
                    self._order.setdefault(caller_key, self.pos)
                    if _type(self.peek()) == "SEMICOLON":
                        self.advance()
                    continue

                continue
            else:
                self.advance()

        # Link each Caller to its callee's children/objects.
        for obj in self.objects.values():
            if isinstance(obj, Caller):
                if obj.dependencies:
                    callee_node = obj.dependencies[0][0]
                    obj.callee_children = {
                        "callees": callee_node.scope.callees,
                        "callers": callee_node.scope.callers,
                        "generic": callee_node.scope.children,
                    }

        sorted_keys = sorted(self._order.keys(), key=lambda k: self._order[k])
        return [self.objects[k] for k in sorted_keys]


if __name__ == "__main__":
    main = Scope("main")
    stdio = Lib("stdio", main)

    def double(x):
        print(f"double called with {x}")
        return x * 2

    printf = Callee("printf", stdio.scope, double)

    x = Callee("x", main, 5)
    y = Caller("y", main, 3)

    y.call(x)
    y.call(printf, x)

    print("y.eval() =", y.eval())  # 3 + 5 + 10 = 18
