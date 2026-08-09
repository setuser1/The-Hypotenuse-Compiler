# Issue #109 Investigation: Compiler imports unused library functions

**Status**: BUG CONFIRMED ✗

## Overview

Tested whether the C△ compiler correctly implements tree-shaking (selective code inclusion) for library imports. The issue claims that the compiler imports ALL functions from a library, even when only a subset is used.

## Test Files Created

1. **`test/issue-109-selective-import.ctri`** - Selective import of printd
2. **`test/issue-109-multi-unused.ctri`** - Selective import of multiple functions
3. **`test/issue-109-import-all.ctri`** - Import entire library

## Key Finding: Selective Import Bug

### Test Case: Selective Import of strlen

```c
using strlen from <string>;

int main() {
    strlen@lib("hello");
    return 0;
}
```

**Expected**: Generated C code includes the strlen function definition
**Actual**: Generated C code calls strlen but never defines it
**Result**: GCC compilation fails with "undefined symbol"

### Error Message
```
error: call to undeclared function 'plstd_strlen'; ISO C99 and later 
do not support implicit function declarations
```

### Root Cause

The bug exists in the codegen's tree-shaking logic for selective imports of top-level functions:

1. **Parsing** ✓ - Parser correctly identifies `using strlen from <string>;`
2. **Marking** ✓ - Codegen marks `strlen` as a used function
3. **Code Generation** ✗ - **FAILS to emit the function body**
4. **Call Emission** ✓ - Call to `plstd_strlen()` is emitted
5. **Result** ✗ - Undefined reference at link time

### Why Printd Works but Strlen Doesn't

The bug only manifests for **top-level functions** in libraries:

#### ✓ Works: Functions in Namespaces (spaces)
- `printd.plib` defines functions inside `space printd { }`
- Selective import of printd collects the entire space
- Tree-shaking includes all dependencies correctly
- **Compilation succeeds**

#### ✗ Broken: Top-level Functions
- `string.plib` defines strlen as a top-level function
- Selective import tries to mark strlen as "used"
- Tree-shaking logic fails to identify the library-prefixed name
- Function definition is skipped
- **Compilation fails - undefined symbol**

## Detailed Behavior Analysis

### Case 1: Selective Import (Broken) 
```ctri
using strlen from <string>;
strlen@lib("hello");
```
- Generated: `plstd_strlen("hello");`
- Defined: ❌ NO definition of plstd_strlen
- Result: ❌ Link fails

### Case 2: Full Import with Namespace (Works)
```ctri
using <string>;
using <printd>;
strlen@string("hello");
```
- Generated: `string_strlen("hello");`
- Defined: ✅ YES (with architecture-specific variants)
- Result: ✅ Compiles (with caveats for arch-specific code)

### Case 3: Full Import + Expose (Should work but has issues)
```ctri
using <string>;
using <printd>;
expose string;
expose printd;
```
- Issue: Expose doesn't expose nested namespaces
- Result: ❌ Functions in `space` blocks not accessible

## Impact Assessment

**Severity**: HIGH
- Selective imports don't work for top-level library functions
- Documentation claims selective imports should work
- Code compiles but fails to link
- Affects users trying to use tree-shaking

**Scope**: Affects any library with top-level functions (string, math, etc.)

**Workaround**: Use the full namespace reference instead of selective import
```c
// DON'T:
using strlen from <string>;
strlen@lib("hello");  // ❌ BROKEN

// DO:
using <string>;
using <printd>;
strlen@string("hello");  // ✅ WORKS
```

## Tree-Shaking Status

**Overall**: Tree-shaking WORKS correctly for what DOES get emitted
- When functions are included, only their dependencies are included
- Unused functions are correctly pruned
- No bloat from unused library code

**But**: Tree-shaking has a NAME MATCHING bug with selective imports
- Selective imports register the bare function name
- Tree-shaking checks for the library-prefixed name
- Names don't match → function skipped

## Recommendation

**Fix in codegen.py**: 
When processing selective imports (`using FUNC from <LIB>`), ensure that tree-shaking logic checks BOTH:
1. The bare function name (e.g., `strlen`)
2. The library-prefixed name (e.g., `plstd_strlen`, `string_strlen`)

This will allow `_should_emit_plib_function` to correctly identify and emit functions that were selectively imported.
