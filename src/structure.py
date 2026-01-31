class Scope:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = {}  # generic children (non‑Callee/Caller)
        self.callees = {}  # name → Callee objects
        self.callers = {}  # name → Caller objects

    def __repr__(self):
        """Readable representation showing the scope name and its parent."""
        parent_name = self.parent.name if self.parent else None
        return f"Scope(name={self.name!r}, parent={parent_name!r})"

    def add_child(self, node):
        """Register a node in the appropriate collection.

        * Callee → ``self.callees``
        * Caller → ``self.callers``
        * Anything else → ``self.children``
        """
        # Determine the target dictionary based on node type.
        if isinstance(node, Callee):
            target = self.callees
        elif isinstance(node, Caller):
            target = self.callers
        else:
            target = self.children

        # Avoid accidental overwrites.
        if node.name in target:
            raise ValueError(
                f"Child named `{node.name}` already exists in scope `{self.name}`"
            )
        target[node.name] = node
        return node

    def called(self, name):
        # Search in the generic children first
        if name in self.children:
            return self.children[name]
        # Then look for a callee (e.g., functions or variables)
        if name in self.callees:
            return self.callees[name]
        # Finally check callers (useful for reverse lookup)
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
        """Readable representation of a Callee."""
        # Show the value succinctly; for functions it may be None.
        val_repr = (
            repr(self.value)
            if not isinstance(self.value, Node)
            else f"<Node {type(self.value).__name__}>"
        )
        return (
            f"Callee(name={self.name!r}, value={val_repr}, scope={self.scope.name!r})"
        )

    def eval(self, *args, **kwargs):
        # If value is callable, call it with resolved args.
        if callable(self.value):
            resolved_args = [
                arg.eval() if isinstance(arg, Node) else arg for arg in args
            ]
            return self.value(*resolved_args)
        # If value is a Node, evaluate it and return its value.
        if isinstance(self.value, Node):
            return self.value.eval()
        # Otherwise return the literal value.
        return self.value


class Caller(Node):
    """Node that can depend on other nodes and call function nodes."""

    def __init__(self, name, scope, value=None):
        super().__init__(name, scope)
        self.value = value
        # Placeholder for a reference to the callee's children/objects.
        self.callee_children: dict | None = None

    def __repr__(self):
        """Readable representation of a Caller, including its argument tokens."""
        if not self.dependencies:
            return f"Caller(name={self.name!r}, scope={self.scope.name!r}, args=[])"
        # Show arguments for the first dependency (callee, args)
        callee_node, args = self.dependencies[0]
        # Render each argument token list as a compact string
        args_repr = []
        for arg_tokens in args:
            # arg_tokens is a list of token tuples (type, lexeme)
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
        # Evaluate self.value if it's a Node, otherwise start with numeric value or 0.
        if isinstance(self.value, Node):
            result = self.value.eval()
        else:
            result = self.value if isinstance(self.value, (int, float)) else 0

        for node, args in self.dependencies:
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
        # Node constructors already register themselves with the scope.
        # Avoid attempting to add the same node twice.
        if node.name in self.scope.children:
            return self.scope.children[node.name]
        return self.scope.add_child(node)

    def called(self, name):
        return self.scope.called(name)


class Structor:
    """Automatically structures each line of code.

    The parser implementation is injected via the ``parser`` argument to the
    constructor, removing the need for a hard‑coded import.
    """

    def __init__(self, tokens_array, parser):
        self.tokens = tokens_array
        self.pos = 0
        self.objects = {}
        self.parser = parser  # injected parser module/object

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def match(self, *types):
        tok = self.peek()
        if tok and getattr(tok, "type", None) in types:
            return self.advance()
        return None

    # Function Argument collecting
    def collect_args(self):
        """Collect function‑call arguments and return a list of parsed AST nodes.

        Tokens are gathered until a matching RPAREN is found. The raw token
        list for each argument (separated by commas) is fed to the injected
        parser's ``Parser`` class and ``parse_expression`` is invoked, so the
        caller receives fully parsed expression objects rather than raw strings.
        """
        raw_args = []  # List of token lists, one per argument
        current = []
        while True:
            tok_peek = self.peek()
            if tok_peek is None:
                break
            # Determine the token type (tuple or object) to check for a closing RPAREN.
            t_type = (
                tok_peek[0]
                if isinstance(tok_peek, tuple)
                else getattr(tok_peek, "type", None)
            )
            if t_type == "RPAREN":
                break
            tok = self.advance()
            # ``tok`` may be a tuple (type, lexeme) or a token object.
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
        # Consume the closing RPAREN.
        if self.peek() == "RPAREN":
            self.advance()
        # NOTE: The original implementation tried to parse each argument
        # using ``self.parser.Parser``.  To keep the compiler functional
        # without a full expression parser, we simply return the raw token
        # lists for each argument.
        return raw_args

    def build_and_sort(self):
        """Create Callee and Caller objects from the token stream and order them.

        This method walks the token list, uses the full parser only for
        expressions and function‑call arguments, and builds lightweight
        ``Callee``/``Caller`` nodes. The resulting objects are returned sorted
        by their original appearance (pointer‑line order).
        """
        # Global scope that will contain the nodes.
        program = Scope("program")
        # Mapping of name -> first appearance index for sorting later.
        self._order = {}

        # Helper functions to safely extract token type/value regardless of
        # representation (tuple, object, or None).
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

        while True:
            cur = self.peek()
            if cur is None:
                break

            typ = _type(cur)
            val = _value(cur)

            if typ == "IDENTIFIER":
                name = val
                self.advance()  # consume identifier
                nxt = self.peek()
                nxt_type = _type(nxt)

                # -------------------------------------------------
                # 1. Variable/value definition: IDENTIFIER ASSIGN expr SEMICOLON
                # -------------------------------------------------
                if nxt_type == "ASSIGN":
                    # Skip variable/value definitions – they are not needed for
                    # the current structural analysis. Advance past the '=' and
                    # any tokens until the terminating semicolon.
                    self.advance()  # consume '='
                    while True:
                        nxt_tok = self.peek()
                        if nxt_tok is None or _type(nxt_tok) == "SEMICOLON":
                            break
                        self.advance()
                    # Consume the semicolon if present.
                    if _type(self.peek()) == "SEMICOLON":
                        self.advance()
                    # No Callee is created for plain assignments.
                    continue

                # -------------------------------------------------
                # 2. Function‑like call: IDENTIFIER LPAREN ... RPAREN
                # -------------------------------------------------
                if nxt_type == "LPAREN":
                    self.advance()  # consume '('
                    args = self.collect_args()  # returns parsed AST nodes
                    # Resolve (or lazily create) the callee.
                    callee_node = self.objects.get(name)
                    if callee_node is None:
                        callee_node = Callee(name, program, None)
                        self.objects[name] = callee_node
                        self._order.setdefault(name, self.pos)
                    # Create a Caller representing this invocation.
                    caller_name = f"call_{name}_{self.pos}"
                    caller_node = Caller(caller_name, program)
                    caller_node.call(callee_node, *args)
                    self.objects[caller_name] = caller_node
                    self._order.setdefault(caller_name, self.pos)
                    # Optional trailing semicolon.
                    if _type(self.peek()) == "SEMICOLON":
                        self.advance()
                    continue

                # Any other identifier usage is ignored for structuring purposes.
                continue
            else:
                # Non‑identifier tokens are ignored.
                self.advance()

        # Return objects sorted by their first appearance (pointer order).
        # -------------------------------------------------
        # Link each Caller to its callee's children/objects.
        # -------------------------------------------------
        for obj in self.objects.values():
            if isinstance(obj, Caller):
                # A Caller stores its dependencies as a list of (node, args) tuples.
                # The first element of the first tuple is the callee node.
                if obj.dependencies:
                    callee_node = obj.dependencies[0][0]
                    # Expose the callee's scope collections for easy inspection.
                    obj.callee_children = {
                        "callees": callee_node.scope.callees,
                        "callers": callee_node.scope.callers,
                        "generic": callee_node.scope.children,
                    }
        sorted_names = sorted(self._order.keys(), key=lambda k: self._order[k])
        return [self.objects[n] for n in sorted_names]


if __name__ == "__main__":
    main = Scope("main")
    stdio = Lib("stdio", main)

    # First-class function
    def double(x):
        print(f"double called with {x}")
        return x * 2

    printf = Callee("printf", stdio.scope, double)

    # Values
    x = Callee("x", main, 5)
    y = Caller("y", main, 3)

    # Dependencies
    y.call(x)  # y depends on x
    y.call(printf, x)  # y calls printf with x as argument

    print("y.eval() =", y.eval())  # 3 + 5 + 10 = 18
