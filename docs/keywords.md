# C△ Keyword Reference

---

## Base C Keywords (C11 Compatible)

All standard C11 keywords are supported unless listed as deprecated.

| Keyword | Description |
|---|---|
| `auto` | Repurposed — see C△ specific keywords |
| `break` | Exit from loop or switch |
| `case` | Case in switch |
| `char` | Character type |
| `const` | Immutable variable |
| `continue` | Skip to next iteration |
| `default` | Default case in switch |
| `do` | do-while loop |
| `double` | Double precision floating type |
| `else` | Else branch |
| `enum` | Enumerated type |
| `extern` | External linkage |
| `float` | Floating point type |
| `for` | for loop |
| `goto` | Jump to label |
| `if` | Conditional branch |
| `inline` | Inline function hint |
| `int` | Integer type |
| `long` | Long integer type |
| `register` | Register storage hint |
| `return` | Return from function |
| `short` | Short integer type |
| `signed` | Signed integer |
| `sizeof` | Size of type or object |
| `static` | Static storage class |
| `struct` | Plain structure type — constructors and member functions, not a native type, no inheritance |
| `switch` | Multi-way conditional |
| `typedef` | Type alias |
| `union` | Union type |
| `unsigned` | Unsigned integer |
| `void` | Empty return type |
| `volatile` | Prevent compiler optimizations |
| `while` | while loop |
| `NULL` | Null value, behaves like none/nullptr |
| `#include` | Include C headers — preprocessor macro, C compatible |

---

## Deprecated From C

These keywords are removed from C△ and will cause a compiler error if used.

| Keyword | Reason |
|---|---|
| `auto` (C11 storage class) | Repurposed as C△ dynamic type |
| `restrict` | Compiler handles automatically |
| `_Bool` | Replaced by cleaner boolean handling |
| `_Complex` | Handled via user libraries instead |
| `_Imaginary` | Handled via user libraries instead |

---

## C△ Specific Keywords

### Types

| Keyword | Description |
|---|---|
| `auto` | Dynamic type — inference at compile time, dynamic at runtime, usable as parameter type, return type, and variadic via `auto args*` |
| `string` | Native string type — dynamic char* with length and capacity |
| `dynam` | Dynamic array — `dynam int arr = [1,2,3]`, supports `.push()`, `.pop()`, `.remove()` |
| `tuple` | Dynamic tuple — `tuple t = [1, "hello", 3.14]`, indexable, mixed types |
| `char[n]` | Sized char array — `char[20] buffer = "hello"` |

### Memory

| Keyword | Description |
|---|---|
| `allocate` | Heap allocation with optional custom size — `allocate int x (256)` |
| `free` | Manual heap deallocation |
| `autoremove` | Auto free at last use — `autoremove allocate int* ptr = &x` — compiler simulation pass finds last use |

### Functions and Lambdas

| Keyword | Description |
|---|---|
| `lamb` | Named lambda — always named, always typed params — `lamb add(int a, int b) = a + b` |
| `init` | Struct lifecycle constructor function |
| `end` | Struct lifecycle destructor function |
| `self` | Optional struct self reference — `self.value` |
| `len()` | Returns length of array, tuple, string, or digit count of integer |

### Structs

| Keyword | Description |
|---|---|
| `struct` | Plain struct — constructors via params on name line, member functions, no inheritance, not a native type |
| `typed struct` | First class type struct — constructors, member functions, inheritance via `&`, native type — `typed struct A&B&C` |

### Assembly

| Keyword | Description |
|---|---|
| `asm` | Native assembly block or function — `asm funcname(params) { syntax_x86_64_linux ... }` |
| `syntax_x86_64_linux` | Assembly syntax target declaration — inside asm block, first line |

### Imports and Scope

| Keyword | Description |
|---|---|
| `using` | Import or intra file reference — `using x from <lib>`, `using x from "lib"`, `using scope&var` |
| `show` | Globalize a namespace or entire plstd — `show lib`, `show plstd`, `show namespace` |
| `space` | Declare a namespace |

### Standard Library

| Keyword | Description |
|---|---|
| `lib:` | plstd access prefix — `lib:printd("hello")` |
| `printd` | Type aware print — handles all native types including dynam, tuple, string |
| `printfs` | F-string print — `printfs("hello {name}")` |

---

## Operators and Special Symbols

| Symbol | Description |
|---|---|
| `.` | Struct member access — `structure.display()` |
| `->` | C pointer member access — `p->x` |
| `:` | Namespace member access — `myspace:random()` |
| `&` | Reference, struct inheritance, pointer to object — `typed struct A&B`, `&ptr1` |
| `*` | Pointer declaration or dereference — `int* ptr` |
| `%k` | Format specifier for auto typed values — `printf("%k", autovar)` |
| `[]` | Tuple and dynam array literal — `tuple t = [1, "hello", 3.14]` |
| `{}` | F-string expression interpolation — `printfs("value is {x}")` |
| `auto x, z, w = t` | Multiple variable packing — all initialized to t in one line |

---

## Assembly Syntax Targets

| Target | Platform |
|---|---|
| `syntax_x86_64_linux` | Linux ELF x86_64 |
| `syntax_x86_64_windows` | Windows PE x86_64 |
| `syntax_x86_64_macos` | macOS Mach-O x86_64 |

---

## Notes

- All function parameters must have a type — explicit or `auto`, no bare untyped params
- `autoremove` is exclusively for heap allocated variables via `allocate`
- Robbery: when an `autoremove` pointer drops, another pointer inherits the space via `&ptr1` and automatically becomes a plain variable — no `free` needed
- Intra file `using` references are always immutable
- `show lib` globalizes library scope only — linking is always automatic based on actual usage
- Compiler auto imports what you use — manual `using` is optional
- Each `asm` block or function is compiled to a separate `.asm` file, assembled with NASM, linked into binary
- `return` inside `asm` replaces `ret` — implicit return defaults to `rax` on x86_64
- Function name in `asm` IS the label — no `global` declaration needed
