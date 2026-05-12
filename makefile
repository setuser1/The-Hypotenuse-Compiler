.PHONY: run install test lint typecheck all build binary clean full-install uninstall

# Path to the parseable regression fixture (quoted where expanded to the shell
# so paths containing spaces work).
BASELINE := $(CURDIR)/test/baseline.ctri

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
	python3 -m pyflakes src/lexer.py src/parser.py src/structure.py src/codegen.py src/assembler.py src/main.py

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
	@echo "  Checking: $(DYNAM)"
	@echo "  Checking: $(STRING)"
	@echo "  Checking: $(STRING_CONCAT)"
	@echo "  Checking: $(LEN_TEST)"
	@echo "--- All inputs passed ---"

# ---------------------------------------------------------------
# test: assert specific expected outputs from the structurer so
#       regressions in scope tracking or value parsing are caught
#       immediately on every push.
#
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

	@echo "--- Test: no libc string functions in compiler-generated code ---"
	@python3 src/main.py test/test_no_libc_strings.ctri 2>&1 | grep "#include <string.h>" > /dev/null && \
		(echo "FAIL: <string.h> must not be included" && exit 1) || true
	@python3 src/main.py test/test_no_libc_strings.ctri 2>&1 | grep -E '\b(strlen|strcpy|strcat|strdup)\(' > /dev/null && \
		(echo "FAIL: bare libc string call found (expected __ctri_*)" && exit 1) || true
	@python3 src/main.py test/test_no_libc_strings.ctri 2>&1 | grep "__ctri_strlen" > /dev/null || \
		(echo "FAIL: expected __ctri_strlen helper" && exit 1)
	@python3 src/main.py test/test_no_libc_strings.ctri 2>&1 | grep "__ctri_strdup" > /dev/null || \
		(echo "FAIL: expected __ctri_strdup helper" && exit 1)
	@echo "PASS: no libc strings"

	@echo "--- Test: intra-file variable imports from asm and normal functions ---"
	@python3 -c "\
import sys; sys.path.insert(0,'src'); \
import lexer, parser as p, structure, codegen; \
asm_src = 'asm int asm_owner() {\\n    syntax arm64_macho\\n    .section __TEXT,__text\\n    int asm_value = 42\\n    return asm_value\\n}\\nusing asm_owner&asm_value\\nint main() { return asm_value; }\\n'; \
normal_src = 'int normal_owner() {\\n    int normal_value = 7;\\n    return normal_value;\\n}\\nusing normal_owner&normal_value\\nint main() { return normal_value; }\\n'; \
bad_src = 'asm int missing_section() {\\n    syntax x86_64_elf\\n    return 1\\n}\\n'; \
exec('def gen(src):\\n    ast = p.Parser(lexer.Lexer(src).lex()).parse_program()\\n    s = structure.Structor(ast)\\n    s.build_from_ast()\\n    return codegen.CodeGen(ast, s).generate()'); \
asm_c = gen(asm_src); \
normal_c = gen(normal_src); \
assert 'extern int asm_value;' in asm_c, asm_c; \
assert 'return asm_value;' in asm_c, asm_c; \
assert 'int normal_owner_normal_value = 7;' in normal_c, normal_c; \
assert 'return normal_owner_normal_value;' in normal_c, normal_c; \
exec('try:\\n    p.Parser(lexer.Lexer(bad_src).lex()).parse_program()\\n    raise AssertionError(\"missing asm text section did not fail\")\\nexcept SyntaxError as exc:\\n    assert \"text section\" in str(exc), exc'); \
print('PASS: intra-file variable imports')"

	@echo "=== All tests passed ==="

# ---------------------------------------------------------------
# all: full clean build + test (useful for CI)
# ---------------------------------------------------------------
all: install lint test

# ---------------------------------------------------------------
# build: build PyInstaller executable
# ---------------------------------------------------------------
build: install
	pyinstaller --onefile --name hypotenuse --add-data "src:src" src/main.py

# ---------------------------------------------------------------
# binary: run the compiled binary (must run 'make build' first)
# ---------------------------------------------------------------
binary: build
	./dist/hypotenuse

# ---------------------------------------------------------------
# clean: remove build artifacts
# ---------------------------------------------------------------
clean:
	rm -rf build dist *.spec __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------------------------
# full-install: install the binary to system and set up PLIBS folder
# ---------------------------------------------------------------
full-install: build
	@if [ -w /usr/local/bin ]; then \
		cp dist/hypotenuse /usr/local/bin/hypotenuse; \
		chmod +x /usr/local/bin/hypotenuse; \
		echo "Installed to /usr/local/bin/hypotenuse"; \
		sudo mkdir -p /usr/lib/PLIBS/plstd; \
		echo "Created /usr/lib/PLIBS/plstd"; \
		sudo cp -r plstd/* /usr/lib/PLIBS/plstd/; \
		echo "Copied plstd contents to /usr/lib/PLIBS/plstd"; \
	else \
		mkdir -p ~/.local/bin; \
		cp dist/hypotenuse ~/.local/bin/hypotenuse; \
		chmod +x ~/.local/bin/hypotenuse; \
		echo "Installed to ~/.local/bin/hypotenuse"; \
		mkdir -p ~/.local/lib/PLIBS/plstd; \
		echo "Created ~/.local/lib/PLIBS/plstd"; \
		cp -r plstd/* ~/.local/lib/PLIBS/plstd/; \
		echo "Copied plstd contents to ~/.local/lib/PLIBS/plstd"; \
		echo "Add ~/.local/bin to your PATH if not already present"; \
	fi

# ---------------------------------------------------------------
# uninstall: remove the binary from system
# ---------------------------------------------------------------
uninstall:
	@if [ -f /usr/local/bin/hypotenuse ]; then \
		rm /usr/local/bin/hypotenuse; \
		echo "Removed /usr/local/bin/hypotenuse"; \
	elif [ -f ~/.local/bin/hypotenuse ]; then \
		rm ~/.local/bin/hypotenuse; \
		echo "Removed ~/.local/bin/hypotenuse"; \
	else \
		echo "hypotenuse not found in /usr/local/bin or ~/.local/bin"; \
	fi
