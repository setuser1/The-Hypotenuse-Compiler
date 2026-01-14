import parser as p
# new stuff guys!
class Scope:
    def __init__(self, name):
        self.name = name
        self.children = []
    def add_child(self, child):
        self.children.append(child)
        return self
    def called(self, callee):
        """
        Return the child that matches *callee*.
        Matching is based on the name (which is unique for our tiny model) rather
        than object identity, because callers often pass a different instance that
        represents the same logical entity.
        """
        for child in self.children:
            if getattr(child, "name", None) == getattr(callee, "name", None):
                return child
        return None

class Callee:
    def __init__(self, name, scope, value):
        self.name = name
        self.scope = scope
        # Store the payload as a scalar (or more generally as whatever the caller passes)
        self.value = value
        scope.add_child(self)

class Caller:
    def __init__(self, name, scope, value):
        self.name = name
        self.scope = scope
        self.value = value
        self.dependencies = []
        self.callee = Callee(self.name, self.scope, self.value)
    def call(self, callee):
        self.dependencies.append(callee)
    def utilize(self, callee):
        self.dependencies.append(callee.callee)

class Lib:
    def __init__(self, name, scope=None):
        self.name = name
        self.parent = scope
        # Create a dedicated Scope for the library and, if a parent scope was
        # supplied, register this library as a child of that parent.
        self.scope = Scope(name)
        if scope is not None:
            scope.add_child(self.scope)
    def add_child(self, child):
        # Accept both Callee/Caller objects and raw Scope objects.
        # If a Scope is added, we want it to be reachable via the library’s
        # own scope hierarchy.
        if isinstance(child, Scope):
            self.scope.add_child(child)
        else:
            self.scope.add_child(child)
    def called(self, callee):
        return self.scope.called(callee)


class Structor:
    """Used for automatically structuring each line of code,
    taking tokens from lexer and sorting them into the appropriate
    representations."""
    def __init__(self, tokens_array, scope):
        self.tokens = tokens_array
        self.pos = 0
        self.objects = {}
        # The scope in which the generated objects will live
        self.scope = scope

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        tok = self.peek()
        self.pos += 1
        return tok
    def match(self,*types):
        tok = self.peek()
        if tok and tok.type in types:
            return self.advance()
        return None
    def structure(self):
        while self.peek():
            self.statement()
    def statement(self):
        # Assignment / object creation
        if (self.peek().type == "NAME" and
                self.tokens[self.pos + 1].type == "EQUALS" and
                self.tokens[self.pos + 2].type == "NAME"):
            # variable name on the left‑hand side
            var_name = self.advance().value
            # skip the '=' token
            self.advance()
            # class name (Callee or Caller) on the right‑hand side
            class_name = self.advance().value
            # skip the opening '('
            self.advance()
            # collect arguments until ')'
            args = self.collect_args()

            # Build the appropriate object and register it
            if class_name == "Callee":
                obj = Callee(args[0], self.scope, args[2])
            elif class_name == "Caller":
                obj = Caller(args[0], self.scope, args[2])
            else:
                raise SyntaxError("Unknown class")

            self.objects[var_name] = obj
            return
        if self.peek().type == "NAME" and self.tokens[self.pos + 1].type == "DOT":
            caller_name = self.advance().value
            self.advance()
            method = self.advance().value
            self.advance()
            callee_name = self.advance().value
            self.advance()
                
            if method == "call":
                caller = self.objects[caller_name]
                callee = self.objects[callee_name]
                caller.call(callee)
            return
        self.advance()
    # Argument Collecting
    def collect_args(self):
        args = []
        while self.peek().type != "RPAREN":
            tok = self.advance()
            if tok.type in ("STRING", "NUMBER","NAME"):
                args.append(tok.value.strip('"\''))
        self.advance()
        return args

if __name__ == '__main__':
    new = Scope('main')
    std = Lib('stdio')
    printf = Caller('printf', std, "print()")
    std.add_child(printf)
    x = Callee("random_variable", new, 5)
    y = Caller("int y", new, 3)

    y.call(x)

    y.call(std.called(printf))
    y.utilize(printf)
    print(y.dependencies[1].value)

    b = y.value + y.dependencies[0].value
    print(b)
