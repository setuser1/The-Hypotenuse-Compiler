
# new stuff guys!
class Scope:
    def __init__(self, name):
        self.name = name
        self.children = []
    def add_child(self, child):
        self.children.append(child)
        return self

class Caller:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.points = []
    def start(self, scope):
        scope.add_child(self)
        return self
    def call(self, point, scopes):
        for scope in scopes:
            if point in scope.children:
                self.points.append(point)


class Lib:
    def __init__(self, name, scope):
        self.name = name
        self.functions = []
        scope.add_child(self)
    def add_function(self, function):
        self.functions.append(function)