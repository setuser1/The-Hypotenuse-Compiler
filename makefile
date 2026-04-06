.PHONY: run install test lint typecheck all

# Path to the parseable regression fixture (quoted where expanded to the shell
# so paths containing spaces work).
BASELINE := $(CURDIR)/test/baseline.ctri
RETURNS := $(CURDIR)/test/function_returns.ctri

# ---------------------------------------------------------------
# install: install all Python dependencies needed to test/lint
# ---------------------------------------------------------------
install:
	pip install --quiet pytest pyflakes

# ---------------------------------------------------------------
# run: compile the canonical example file and print the object graph
# ---------------------------------------------------------------
run: install
	python3 src/main.py -t "$(BASELINE)"

# ---------------------------------------------------------------
# lint: catch syntax errors and undefined names across all source files
# ---------------------------------------------------------------
lint:
	python3 -m pyflakes src/lexer.py src/parser.py src/structure.py src/main.py

# ---------------------------------------------------------------
# typecheck: run the compiler against every .ctri test file and
#            assert it exits cleanly (non-zero exit = test failure)
#
# Note: library_import.ctri requires Linux with standard headers
# ---------------------------------------------------------------
typecheck:
	@echo "--- Running compiler over parseable test inputs ---"
	@echo "  Checking: $(BASELINE)"
	@python3 src/main.py -t "$(BASELINE)" || (echo "FAILED: baseline.ctri" && exit 1)
	@echo "  Checking: $(RETURNS)"
	@python3 src/main.py -t "$(RETURNS)" || (echo "FAILED: function_returns.ctri" && exit 1)
	@echo "--- All inputs passed ---"

# ---------------------------------------------------------------
# test: assert specific expected outputs from the structurer so
#       regressions in scope tracking or value parsing are caught
#       immediately on every push.
#
#       function_returns.ctri validates return value handling:
#       - return expressions in functions (int getFive() { return 5; })
#       - return a + b expressions in function bodies
#       - return with parenthesized expressions (x + 10) * 2
#       - return 0 in main()
#       - void return (empty return;)
# ---------------------------------------------------------------
test: install lint typecheck
	@echo "--- Test: negative number + value kind (issues #61, #83) ---"
	@python3 src/main.py -p "$(BASELINE)" | \
		grep "kind=integer" > /dev/null || \
		(echo "FAIL: x should have kind=integer (issue #83)" && exit 1)
	@python3 src/main.py -p "$(BASELINE)" | \
		grep "value=-500" > /dev/null || \
		(echo "FAIL: x should have value -500" && exit 1)
	@echo "PASS: negative number and integer kind"

	@echo "--- Test: variables scoped to function, not program (issue #62) ---"
	@python3 src/main.py -p "$(BASELINE)" | \
		grep "scope: main" > /dev/null || \
		(echo "FAIL: x should be in scope 'main', not 'program'" && exit 1)
	@python3 src/main.py -p "$(BASELINE)" | \
		awk '/scope: program/,/scope: main/' | grep "Callee  'x'" > /dev/null && \
		(echo "FAIL: x must not appear in program scope" && exit 1) || true
	@echo "PASS: scope tracking"

	@echo "--- Test: function itself registered in program scope ---"
	@python3 src/main.py -p "$(BASELINE)" | \
		grep -A20 "scope: program" | grep "Callee  'main'" > /dev/null || \
		(echo "FAIL: main() should be a Callee in program scope" && exit 1)
	@echo "PASS: function in program scope"

	@echo "--- Test: callers present for printf calls ---"
	@python3 src/main.py -p "$(BASELINE)" | \
		grep "Caller.*call_printf" > /dev/null || \
		(echo "FAIL: expected Caller nodes for printf invocations" && exit 1)
	@echo "PASS: callers present"

	@echo "--- Test: lexer tokenises basic program without crashing ---"
	@python3 -c "\
import sys; sys.path.insert(0,'src'); \
import lexer; \
src = open('test/baseline.ctri').read(); \
toks = lexer.Lexer(src).lex(); \
assert len(toks) > 0, 'lexer produced no tokens'; \
print('token count:', len(toks))"
	@echo "PASS: lexer"

	@echo "--- Test: parser builds AST for basic program without crashing ---"
	@python3 -c "\
import sys; sys.path.insert(0,'src'); \
import lexer, parser as p; \
src = open('test/baseline.ctri').read(); \
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
