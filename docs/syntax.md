# C△ Syntax Guide

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

A complete reference for C△ syntax with examples. C△ inherits C11 syntax and extends it with new constructs.

---

## File Extensions

| Extension | Purpose |
|---|---|
| `.ctri` | C△ source file |
| `.plib` | C△ library file |

The compiler detects whether a file is an **executable** (has a `main` function) or a **library** (`.plib` extension).

---

## Imports

```c
// Import a specific symbol from a system library
// Import an entire plib (project-specific library)
using <plstd>

// Import a specific symbol from a system library
using random from <math>

// Import from a local library
using helper from "utils"

// Globalize an entire library (all symbols in scope)
show plstd

// Globalize one module from plstd
show lib:io

// Intra-file immutable reference
using scope&myVar
```

> The compiler auto-imports what is used — manual `using` is optional style.

---

## Variables

```c
// Standard C types
int x = 5;
float pi = 3.14;
char c = 'A';

// C△ string type *NEW*
string name = "Hypotenuse";

// Dynamic / inferred type *NEW*
auto value = 42;
auto label = "hello";

// Multiple variable packing *NEW*
auto x, z, w = 10;   // all three initialized to 10
```

---

## Control Flow

```c
// Standard if/else
if (x > 0) {
    printd(x);
} else {
    printd(0);
}

// For loop
for (int i = 0; i < 10; i++) {
    printd(i);
}

// While loop
while (x > 0) {
    x--;
}
```

---

## Functions

```c
// Standard function
int add(int a, int b) {
    return a + b;
}

// Variadic argument stream *NEW*
int sum(auto args*) {
    // args is a pointer to the argument stream
}
```

---

## Lambdas (`lamb`) *NEW*

Named lambdas — return type is optional.

```c
lamb double(int num) = num*2;
lamb add(int a, int b) = a + b;

auto result = double(5);  // result = 10
```

---

## Structs

### Plain Struct

```c
struct Point(int x, int y) {
    init {
        self.x = x;
        self.y = y;
    }

    int distanceTo(Point other) {
        // ...
    }
    end {...}
}
```

### Typed Struct (Native Type + Inheritance) *NEW*

```c
typed struct Animal(string name) {
    init {...}
    string speak() {
        return "...";
    }
    end {...}
}

// Single inheritance
typed struct Dog&Animal(string name) {
    init {...}
    string speak() {
        return "Woof!";
    }
    end {...}
}

// Multiple inheritance *NEW*
Typed struct PoliceDog&Dog&Animal(string name, int badge) {
    init {...}
    // conflicts resolved via parent namespace: obj.Dog.speak()
    end {...}
}
```

---

## Memory

```c
// Heap allocation *NEW*
allocate int arr[100];
free arr;

// Auto-freed at last use *NEW*
autoremove allocate int buf[512];

// Custom size types
allocate int x(200) = 100000000000;

// Robbery: another pointer takes ownership *NEW*
autoremove allocate int p[10];
int* q = &p;   // q becomes a plain variable, p drops
```

---

## Dynamic Arrays (`dynam`) *NEW*

```c
dynam int numbers = [1, 2, 3, 4, 5];
numbers.push(6);
numbers.remove(0);
int len = len(numbers);
```

---

## Tuples *NEW*

```c
tuple t = [1, "hello", 3.14];
auto first = t[0];
```

---

## Inline Assembly (`asm`) *NEW*

```c
asm addInts(int a, int b) {
    syntax x86_64_linux
    .section .text
    mov rax, a
    mov rbx, b
    add rax, rbx
    return
}

// Anonymous assembly block
asm {
    .syntax x86_64_linux
    section .data
    char[20] msg = "Hello, World!\n"
    section .text
    ; assembly code here
}
```

See [assembly.md](assembly.md) for full details.

---

## Namespace Access

```c
// Access a namespace member with ':'
myspace:random()

// Globalize a namespace
show myspace
random()   // now accessible directly
```
