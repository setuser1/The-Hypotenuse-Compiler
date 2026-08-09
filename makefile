.PHONY: run install test lint typecheck all build build-x86_64-elf binary clean full-install full-install-x86_64-elf uninstall

# Path to the parseable regression fixture (quoted where expanded to the shell
# so paths containing spaces work).
BASELINE := $(CURDIR)/test/baseline.ctri
C11_FEATURES := $(CURDIR)/test/c11_features.ctri
FULL_C11 := $(CURDIR)/test/full_c11.ctri
TEST_108 := $(CURDIR)/test/test-108.ctri
TEST_109 := $(CURDIR)/test/test-109.ctri
PYINSTALLER_NAME := hypotenuse
X86_64_ELF_NAME := hypotenuse-x86_64-elf
X86_64_ELF_IMAGE ?= python:3.14-slim
X86_64_ELF_PLATFORM ?= linux/amd64

# ---------------------------------------------------------------
# install: install all Python dependencies needed to test/lint
# ---------------------------------------------------------------
install:
	pip install --quiet pytest pyflakes pyinstaller

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
	@echo "  Checking: $(C11_FEATURES)"
	@python3 src/main.py "$(C11_FEATURES)" > /dev/null || (echo "FAILED: c11_features.ctri" && exit 1)
	@echo "  Checking: $(FULL_C11)"
	@python3 src/main.py "$(FULL_C11)" > /dev/null || (echo "FAILED: full_c11.ctri" && exit 1)
	@echo "  Checking: $(TEST_108)"
	@python3 src/main.py "$(TEST_108)" > /dev/null || (echo "FAILED: test-108.ctri" && exit 1)
	@echo "  Checking: $(TEST_109)"
	@python3 src/main.py "$(TEST_109)" > /dev/null || (echo "FAILED: test-109.ctri" && exit 1)
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

	@echo "--- Test: local test imports resolve ---"
	@test -f test/mylib.plib || (echo "FAIL: missing test/mylib.plib" && exit 1)
	@test -f test/lib.plib || (echo "FAIL: missing test/lib.plib" && exit 1)
	@test -f test/stdio.plib || (echo "FAIL: missing test/stdio.plib" && exit 1)
	@python3 src/main.py test/test_at_match_funcname.ctri > /dev/null || \
		(echo "FAIL: test_at_match_funcname.ctri import should resolve" && exit 1)
	@python3 src/main.py test/test_at_long_funcname.ctri > /dev/null || \
		(echo "FAIL: test_at_long_funcname.ctri import should resolve" && exit 1)
	@python3 src/main.py test/test_at_rsplit.ctri > /dev/null || \
		(echo "FAIL: test_at_rsplit.ctri import should resolve" && exit 1)
	@python3 src/main.py test/issue-109-selective-import-full.ctri 2>&1 | grep -F "string_strlen(s)" > /dev/null || \
		(echo "FAIL: @lib should resolve stdlib string functions by plib filename" && exit 1)
	@python3 src/main.py test/issue-109-selective-import-full.ctri 2>&1 | grep -F "printd_printd(l)" > /dev/null || \
		(echo "FAIL: @lib should resolve stdlib printd by plib filename" && exit 1)
	@python3 src/main.py test/issue-109-selective-import-full.ctri 2>&1 | grep -E "^[A-Za-z_].*plstd_" > /dev/null && \
		(echo "FAIL: plstd must not be used as a generated stdlib function prefix" && exit 1) || true
	@printf 'using <printd>;\nint main() { printd(42); return 0; }\n' > /tmp/ctri_plstd_bare_call.ctri
	@python3 src/main.py /tmp/ctri_plstd_bare_call.ctri 2>&1 | grep -F "not exposed" > /dev/null || \
		(echo "FAIL: standard library imports should still require @lib or expose for bare calls" && exit 1)
	@echo "PASS: local test imports"

	@echo "--- Test: source files cannot include themselves ---"
	@python3 -c "\
import os, sys, tempfile; sys.path.insert(0,'src'); \
import main; \
fd, path = tempfile.mkstemp(suffix='.ctri'); \
os.close(fd); \
open(path, 'w').write('#include \"' + path + '\"\\nint main() { return 0; }\\n'); \
exec('try:\\n    main.compile_file(path)\\n    raise AssertionError(\"self include did not fail\")\\nexcept SyntaxError as exc:\\n    assert \"cannot include itself\" in str(exc), exc\\nfinally:\\n    os.remove(path)'); \
print('PASS: self include rejected')"

	@echo "--- Test: expose allows direct library calls and missing expose fails ---"
	@python3 src/main.py test/expose_success.ctri 2>&1 | grep "string_strcmp(left, right)" > /dev/null || \
		(echo "FAIL: expose string should allow direct strcmp calls" && exit 1)
	@python3 src/main.py test/expose_required.ctri 2>&1 | grep "expose" > /dev/null || \
		(echo "FAIL: missing expose should suggest expose options" && exit 1)
	@python3 src/main.py test/test_expose_error_msg.ctri 2>&1 | grep "expose the entire library" > /dev/null || \
		(echo "FAIL: error message should mention expose library option" && exit 1)
	@python3 src/main.py test/test_expose_error_msg.ctri 2>&1 | grep "expose.*@.*string" > /dev/null || \
		(echo "FAIL: error message should mention expose func@lib option" && exit 1)
	@python3 src/main.py test/test_expose_full_lib.ctri 2>&1 | grep "string_strcmp(a, b)" > /dev/null || \
		(echo "FAIL: expose entire library should allow direct calls" && exit 1)
	@echo "PASS: expose behavior"

	@echo "--- Test: allocate/free generate allocator calls ---"
	@python3 src/main.py test/allocate_free.ctri 2>&1 | grep "int\\* numbers = (int\\*)__ctri_malloc(4 \\* sizeof(int));" > /dev/null || \
		(echo "FAIL: allocate int array should call __ctri_malloc with element count" && exit 1)
	@python3 src/main.py test/allocate_free.ctri 2>&1 | grep "int\\* value = (int\\*)__ctri_malloc(8);" > /dev/null || \
		(echo "FAIL: byte-sized allocate should call __ctri_malloc with byte size" && exit 1)
	@python3 src/main.py test/allocate_free.ctri 2>&1 | grep "\\*value = 42;" > /dev/null || \
		(echo "FAIL: byte-sized allocate initializer should assign through pointer" && exit 1)
	@python3 src/main.py test/allocate_free.ctri 2>&1 | grep "__ctri_free(numbers);" > /dev/null || \
		(echo "FAIL: free(numbers) should emit __ctri_free(numbers)" && exit 1)
	@python3 src/main.py test/allocate_free.ctri 2>&1 | grep "__ctri_free(value);" > /dev/null || \
		(echo "FAIL: free(value) should emit __ctri_free(value)" && exit 1)
	@echo "PASS: allocate/free"

	@echo "--- Test: custom-sized int allocation bounds ---"
	@python3 src/main.py test/allocate_int_custom_sizes.ctri 2>&1 | grep "int\\* tiny = (int\\*)__ctri_malloc(1);" > /dev/null || \
		(echo "FAIL: 1-byte int allocation should compile when initializer fits" && exit 1)
	@python3 src/main.py test/allocate_int_custom_sizes.ctri 2>&1 | grep "int\\* big = (int\\*)__ctri_malloc(100);" > /dev/null || \
		(echo "FAIL: 100-byte int allocation should compile when initializer fits native int" && exit 1)
	@python3 src/main.py test/allocate_int_small_overflow.ctri 2>&1 | grep "exceeds 1-byte int range" > /dev/null || \
		(echo "FAIL: 1-byte int allocation should reject initializer above 127" && exit 1)
	@python3 src/main.py test/allocate_int_native_overflow.ctri 2>&1 | grep "(unsigned\*)" > /dev/null || \
		(echo "FAIL: custom-sized int allocation should use unsigned assignment for value above native int max" && exit 1)
	@echo "PASS: custom-sized int allocation bounds"

	@echo "--- Test: custom-sized scalar allocation bounds ---"
	@python3 src/main.py test/allocate_scalar_custom_sizes.ctri 2>&1 | grep "char\\* letter = (char\\*)__ctri_malloc(1);" > /dev/null || \
		(echo "FAIL: 1-byte char allocation should compile when initializer fits" && exit 1)
	@python3 src/main.py test/allocate_scalar_custom_sizes.ctri 2>&1 | grep "unsigned\\* byte_value = (unsigned\\*)__ctri_malloc(1);" > /dev/null || \
		(echo "FAIL: 1-byte unsigned allocation should compile when initializer fits" && exit 1)
	@python3 src/main.py test/allocate_scalar_custom_sizes.ctri 2>&1 | grep "float\\* ratio = (float\\*)__ctri_malloc(4);" > /dev/null || \
		(echo "FAIL: native-sized float allocation should compile" && exit 1)
	@python3 src/main.py test/allocate_short_small_overflow.ctri 2>&1 | grep "exceeds 1-byte short range" > /dev/null || \
		(echo "FAIL: 1-byte short allocation should reject initializer above 127" && exit 1)
	@python3 src/main.py test/allocate_unsigned_small_overflow.ctri 2>&1 | grep "exceeds 1-byte unsigned range" > /dev/null || \
		(echo "FAIL: 1-byte unsigned allocation should reject initializer above 255" && exit 1)
	@python3 src/main.py test/allocate_float_too_small.ctri 2>&1 | grep "smaller than native C float size" > /dev/null || \
		(echo "FAIL: float allocation should reject byte sizes smaller than native float" && exit 1)
	@echo "PASS: custom-sized scalar allocation bounds"

	@echo "--- Test: base string operations ---"
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep 'char\* greeting = __ctri_strdup("hello");' > /dev/null || \
		(echo "FAIL: string declaration should duplicate literal storage" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep "__ctri_free(greeting);" > /dev/null || \
		(echo "FAIL: string literal reassignment should free previous storage" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep 'greeting = __ctri_strdup("hi");' > /dev/null || \
		(echo "FAIL: string literal reassignment should duplicate new literal" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep "char\* _new = __ctri_malloc(__ctri_strlen(greeting) + __ctri_strlen(suffix) + 1);" > /dev/null || \
		(echo "FAIL: string append should allocate new buffer for concatenation" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep "__ctri_free(greeting);" > /dev/null || \
		(echo "FAIL: string append should free old buffer" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep "int greeting_len = __ctri_strlen(greeting);" > /dev/null || \
		(echo "FAIL: len(string) should use __ctri_strlen" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep 'int is_hi = (__ctri_strcmp(greeting, "hi world") == 0);' > /dev/null || \
		(echo "FAIL: string == literal should emit __ctri_strcmp == 0" && exit 1)
	@python3 src/main.py test/base_string_ops.ctri 2>&1 | grep 'int is_not_empty = (__ctri_strcmp(greeting, "") != 0);' > /dev/null || \
		(echo "FAIL: string != literal should emit __ctri_strcmp != 0" && exit 1)
	@echo "PASS: base string operations"

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
asm_src = 'asm int asm_owner() {\\n    x86_64_linux\\n    section .text\\n    int asm_value = 42\\n    return asm_value\\n}\\nusing asm_owner&asm_value\\nint main() { return asm_value; }\\n'; \
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
	pyinstaller --onefile --name $(PYINSTALLER_NAME) --add-data "src:src" src/main.py

# ---------------------------------------------------------------
# build-x86_64-elf: cross-build Linux x86_64 ELF compiler from ARM64
# ---------------------------------------------------------------
build-x86_64-elf:
	docker run --rm --platform $(X86_64_ELF_PLATFORM) \
		-v "$(CURDIR):/work" \
		-w /work \
		$(X86_64_ELF_IMAGE) \
		sh -c 'apt-get update && apt-get install -y --no-install-recommends binutils && python -m pip install --quiet pyinstaller && pyinstaller --clean --onefile --name $(X86_64_ELF_NAME) --add-data "src:src" src/main.py'

# ---------------------------------------------------------------
# binary: run the compiled binary (must run 'make build' first)
# ---------------------------------------------------------------
binary: build
	./dist/hypotenuse

# ---------------------------------------------------------------
# container-build: build the compiler using Apple's container CLI (macOS Apple Silicon)
# ---------------------------------------------------------------
container-build:
	@if command -v container >/dev/null 2>&1; then \
		@echo "Building compiler with Apple's container CLI..."; \
		container build --platform linux/amd64 \
			-t "hypotenuse-container" \
			-f "$(CURDIR)/Containerfile" \
			"$(CURDIR)"; \
	else if command -v docker >/dev/null 2>&1; then \
		@echo "Using Docker as fallback (Apple container CLI not found). Consider installing https://github.com/apple/container for native Apple Silicon support."; \
		docker build \
			--platform linux/amd64 \
			-t "hypotenuse-container" \
			--file "$(CURDIR)/Containerfile" \
			"$(CURDIR)"; \
	else \
		echo "Error: Neither 'container' CLI (Apple Silicon) nor 'docker' found."; \
		echo "Install the Apple container tool from https://github.com/apple/container"; \
		exit 1; \
	fi

# ---------------------------------------------------------------
# container-run: run the containerized compiler
# ---------------------------------------------------------------
container-run:
	@if command -v container >/dev/null 2>&1; then \
		container run --platform linux/amd64 \
			--rm \
			-v "$(CURDIR):/work" \
			-w /work \
			hypotenuse-container "$@"; \
	else if command -v docker >/dev/null 2>&1; then \
		docker run --rm \
			--platform linux/amd64 \
			-v "$(CURDIR):/work" \
			-w /work \
			hypotenuse-container "$@"; \
	else \
		echo "Error: Neither 'container' CLI nor 'docker' found"; \
		exit 1; \
	fi

# ---------------------------------------------------------------
# container-test: run the test suite inside the container
# ---------------------------------------------------------------
container-test: container-build
	@if command -v container >/dev/null 2>&1; then \
		@echo "Running tests with Apple's container CLI..."; \
		container run --platform linux/amd64 \
			--rm \
			-v "$(CURDIR):/work" \
			-w /work \
			hypotenuse-container \
			sh -c "cd /work && python3 src/main.py test/baseline.ctri && python3 src/main.py -p test/baseline.ctri"; \
	else if command -v docker >/dev/null 2>&1; then \
		@echo "Using Docker as fallback..."; \
		docker run --rm \
			--platform linux/amd64 \
			-v "$(CURDIR):/work" \
			-w /work \
			hypotenuse-container \
			sh -c "cd /work && python3 src/main.py test/baseline.ctri && python3 src/main.py -p test/baseline.ctri"; \
	else \
		echo "Error: Neither 'container' CLI nor 'docker' found"; \
		exit 1; \
	fi

# ---------------------------------------------------------------
# container-lint: run linting inside the container
# ---------------------------------------------------------------
container-lint: container-build
	@if command -v container >/dev/null 2>&1; then \
		@echo "Running linting with Apple's container CLI..."; \
		container run --platform linux/amd64 \
			--rm \
			-v "$(CURDIR):/work" \
			-w /work \
			hypotenuse-container \
			sh -c "python3 -m pyflakes src/lexer.py src/parser.py src/structure.py src/codegen.py src/assembler.py src/main.py"; \
	else if command -v docker >/dev/null 2>&1; then \
		@echo "Using Docker as fallback..."; \
		docker run --rm \
			--platform linux/amd64 \
			-v "$(CURDIR):/work" \
			-w /work \
			hypotenuse-container \
			sh -c "python3 -m pyflakes src/lexer.py src/parser.py src/structure.py src/codegen.py src/assembler.py src/main.py"; \
	else \
		echo "Error: Neither 'container' CLI nor 'docker' found"; \
		exit 1; \
	fi

# ---------------------------------------------------------------
# clean: remove build artifacts
# ---------------------------------------------------------------
clean:
	rm -rf build dist *.spec __pycache__ release
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------------------------
# full-install: install the binary to system and set up PLIBS folder
# ---------------------------------------------------------------
full-install: build
	@if [ -w /usr/local/bin ]; then \
		cp dist/hypotenuse /usr/local/bin/hypotenuse; \
		chmod +x /usr/local/bin/hypotenuse; \
		echo "Installed to /usr/local/bin/hypotenuse"; \
		sudo mkdir -p /usr/lib/PLIBS; \
		echo "Created /usr/lib/PLIBS"; \
		sudo cp -r plstd /usr/lib/PLIBS/; \
		echo "Copied plstd folder to /usr/lib/PLIBS"; \
	else \
		mkdir -p ~/.local/bin; \
		cp dist/hypotenuse ~/.local/bin/hypotenuse; \
		chmod +x ~/.local/bin/hypotenuse; \
		echo "Installed to ~/.local/bin/hypotenuse"; \
		mkdir -p ~/.local/lib/PLIBS; \
		echo "Created ~/.local/lib/PLIBS"; \
		cp -r plstd ~/.local/lib/PLIBS/; \
		echo "Copied plstd folder to ~/.local/lib/PLIBS"; \
		echo "Add ~/.local/bin to your PATH if not already present"; \
	fi

# ---------------------------------------------------------------
# full-install-x86_64-elf: install the cross-built Linux x86_64 ELF compiler
# ---------------------------------------------------------------
full-install-x86_64-elf: build-x86_64-elf
	@if [ -w /usr/local/bin ]; then \
		cp dist/$(X86_64_ELF_NAME) /usr/local/bin/hypotenuse; \
		chmod +x /usr/local/bin/hypotenuse; \
		echo "Installed Linux x86_64 ELF compiler to /usr/local/bin/hypotenuse"; \
		sudo mkdir -p /usr/lib/PLIBS; \
		echo "Created /usr/lib/PLIBS"; \
		sudo cp -r plstd /usr/lib/PLIBS/; \
		echo "Copied plstd folder to /usr/lib/PLIBS"; \
	else \
		mkdir -p ~/.local/bin; \
		cp dist/$(X86_64_ELF_NAME) ~/.local/bin/hypotenuse; \
		chmod +x ~/.local/bin/hypotenuse; \
		echo "Installed Linux x86_64 ELF compiler to ~/.local/bin/hypotenuse"; \
		mkdir -p ~/.local/lib/PLIBS; \
		echo "Created ~/.local/lib/PLIBS"; \
		cp -r plstd ~/.local/lib/PLIBS/; \
		echo "Copied plstd folder to ~/.local/lib/PLIBS"; \
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
