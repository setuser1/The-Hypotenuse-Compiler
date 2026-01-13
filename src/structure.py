
# new stuff guys!
class Scope:
    def __init__(self, name):
        self.name = name
        self.children = []
    def add_child(self, child):
        self.children.append(child)
        return self

class Callee:
    def __init__(self, name, scope, value):
        self.name = name
        self.scope = scope
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


class Lib:
    def __init__(self, name, scope):
        self.name = name
        self.functions = []
        scope.add_child(self)
    def add_function(self, function):
        self.functions.append(function)


if __name__ == '__main__':
    new = Scope('main')
    x = Callee("random_variable", new, 5)
    y = Caller("int y", new, 3)

    y.call(x)
    b = y.value + y.dependencies[0].value
    print(b)