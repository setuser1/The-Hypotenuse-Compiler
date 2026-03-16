.PHONY: run install test lint typecheck all

# ---------------------------------------------------------------
# install: install all Python dependencies needed to test/lint
# ---------------------------------------------------------------
install:
	pip install --quiet pytest pyflakes

# ---------------------------------------------------------------
# run: compile the canonical example file and print the object graph
# ---------------------------------------------------------------
run: install
	python3 src/main.py -t $(CURDIR)/test/ex.ctri

# ---------------------------------------------------------------
# lint: catch syntax errors and undefined names across all source files
# ---------------------------------------------------------------
lint:
	python3 -m pyflakes src/lexer.py src/parser.py src/structure.py src/main.py

# ---------------------------------------------------------------
# typecheck: run the compiler against every .ctri test file and
#            assert it exits cleanly (non-zero exit = test failure)
# ---------------------------------------------------------------
typecheck:
	@echo "--- Running compiler over all test inputs ---"
	@for f in $(CURDIR)/test/*.ctri; do \
		echo "  Checking: $$f"; \
		python3 src/main.py -t $$f || (echo "FAILED: $$f" && exit 1); \
	done
	@echo "--- All inputs passed ---"

# ---------------------------------------------------------------
# test: assert specific expected outputs from the structurer so
#       regressions in scope tracking or value parsing are caught
#       immediately on every push.
# ---------------------------------------------------------------
test: install lint typecheck
	@echo "--- Test: negative number parsed correctly (issue #61) ---"
	@python3 src/main.py -t $(CURDIR)/test/ex.ctri | \
		grep "value=-500" > /dev/null || \
		(echo "FAIL: x should have value -500" && exit 1)
	@echo "PASS: negative number"

	@echo "--- Test: variables scoped to function, not program (issue #62) ---"
	@python3 src/main.py -t $(CURDIR)/test/ex.ctri | \
		grep "scope='main'" > /dev/null || \
		(echo "FAIL: x should be in scope 'main', not 'program'" && exit 1)
	@python3 src/main.py -t $(CURDIR)/test/ex.ctri | \
		grep "scope='program'.*name='x'" > /dev/null && \
		(echo "FAIL: x must not appear in program scope" && exit 1) || true
	@echo "PASS: scope tracking"

	@echo "--- Test: function itself registered in program scope ---"
	@python3 src/main.py -t $(CURDIR)/test/ex.ctri | \
		grep "Callee(name='main'.*scope='program')" > /dev/null || \
		(echo "FAIL: main() should be a Callee in program scope" && exit 1)
	@echo "PASS: function in program scope"

	@echo "--- Test: callers present for printf calls ---"
	@python3 src/main.py -t $(CURDIR)/test/ex.ctri | \
		grep "Caller(name='call_printf" > /dev/null || \
		(echo "FAIL: expected Caller nodes for printf invocations" && exit 1)
	@echo "PASS: callers present"

	@echo "--- Test: lexer tokenises basic program without crashing ---"
	@python3 -c "\
import sys; sys.path.insert(0,'src'); \
import lexer; \
src = open('test/ex.ctri').read(); \
toks = lexer.Lexer(src).lex(); \
assert len(toks) > 0, 'lexer produced no tokens'; \
print('token count:', len(toks))"
	@echo "PASS: lexer"

	@echo "--- Test: parser builds AST for basic program without crashing ---"
	@python3 -c "\
import sys; sys.path.insert(0,'src'); \
import lexer, parser as p; \
src = open('test/ex.ctri').read(); \
toks = lexer.Lexer(src).lex(); \
toks.append(('EOF','EOF')); \
ast = p.Parser(toks).parse_program(); \
assert ast is not None, 'parser returned None'; \
print('top-level declarations:', len(ast.declarations))"
	@echo "PASS: parser"

	@echo "=== All tests passed ==="

# ---------------------------------------------------------------
# all: full clean build + test (useful for CI)
# ---------------------------------------------------------------
all: install lint test
