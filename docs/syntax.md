# C△ Syntax Guide

This document covers every syntactic construct in C△ with formal definitions and annotated examples.

---

## 1. Variables

### Declaration

Variables in C△ follow C11 syntax. Every variable must have a declared type.

```c
int x = 5;
float y = 3.14;
char c = 'A';
double d = 2.718;
```

### Multiple Variable Packing

Multiple variables can be initialized to the same value on a single line.

```c
auto x, z, w = someValue;
// equivalent to:
auto x = someValue;
auto z = someValue;
auto w = someValue;
```

### The `auto` Type

`auto` is a first class dynamic type. It can hold any value and change type at runtime.

```c
auto val = 42;          // inferred as int at compile time
val = "hello";          // now a string at runtime
val = 3.14;             // now a float at runtime
```

When used as a function parameter, `auto` accepts any type:

```c
void print_anything(auto value) {
    printf("%k\n", value);    // %k is the format specifier for auto
}
```

### Sized Char Arrays

```c
char[20] buffer = "Hello, World!";
char[64] name;
```

---

## 2. Functions

### Basic Function Declaration

```c
return_type function_name(type param1, type param2) {
    // body
}
```

All parameters must have a declared type. `auto` is a valid type for dynamic parameters.

```c
int add(int a, int b) {
    return a + b;
}

auto describe(auto value) {
    return value;
}
```

### Variadic Functions

**Pointer stream** — arguments passed as a pointer to a stream:

```c
void log_ptr(int count, auto args*) {
    for(int i = 0; i < count; i++) {
        printf("%k\n", args[i]);
    }
}
```

### Lambda Functions

Lambdas in C△ are always named and always require typed parameters.

```c
lamb name(type param1, type param2) = expression;
```

```c
lamb add(int a, int b) = a + b;
lamb greet(string name) = printd(name);
lamb scale(float x, float factor) = x * factor;

int result = add(5, 10);    // 15
```

Return type is inferred from the expression.

```c
int lamb add(int a, int b) = a + b;
```

---

## 3. Structs

### Plain Struct

A plain struct is a data container with optional constructors and member functions. It is not a native type and does not support inheritance.

```c
struct Point(int x, int y) {
    int self.x = x;
    int self.y = y;

    void display() {
        printf("Point(%d, %d)\n", self.x, self.y);
    }
}

Point p(1, 2);
p.display();
```

Constructor parameters are declared on the struct name line with explicit types.

### Typed Struct

A `typed struct` elevates a struct to a first class native type. It supports constructors, member functions, and inheritance. Once declared it can be used anywhere a native type like `int` or `float` can be used.

```c
typed struct Vec3(float x, float y, float z) {
    float self.x = x;
    float self.y = y;
    float self.z = z;

    init(float x, float y, float z) {
        self.x = x;
        self.y = y;
        self.z = z;
    }

    end() {
        // cleanup
    }

    float magnitude() {
        return self.x * self.x + self.y * self.y + self.z * self.z;
    }
}

Vec3 position(1.0, 2.0, 3.0);
dynam Vec3 positions;           // usable inside dynam
auto foo(Vec3 v) { ... }        // usable as parameter type
```

### Lifecycle Functions

`init` and `end` are optional lifecycle functions for structs.

```c
typed struct Example {
    init(int value) {
        self.value = value;
    }

    end() {
        // called when struct goes out of scope
    }
}
```

### The `self` Keyword

`self` is optional. It explicitly references the struct's own members.

```c
typed struct Counter {
    int self.count = 0;

    void increment() {
        self.count = self.count + 1;    // explicit self
        count = count + 1;              // also valid
    }
}
```

### Inheritance

Only `typed struct` supports inheritance via `&`.

```c
typed struct Animal(string name) {
    string self.name = name;
    void speak() { printf("..."); }
}

typed struct Dog&Animal(string name) {
    init(string name) {
        self.name = name;
    }
    void speak() { printf("Woof!\n"); }
}
```

Multiple inheritance is supported by chaining `&`:

```c
typed struct C&A&B {
    // inherits from both A and B
    // constructor order: A first, then B, then C
}
```

Conflicting member names are resolved via parent namespace:

```c
obj.A.display()    // calls A's display
obj.B.display()    // calls B's display
obj.A.value        // accesses A's value
obj.B.value        // accesses B's value
```

---

## 4. Dynamic Arrays

`dynam` declares a dynamic array that can grow and shrink at runtime.

```c
dynam int numbers = [1, 2, 3, 4, 5];

numbers.push(6);         // append element
numbers.pop();           // remove last element
numbers.remove(2);       // remove element at index 2
len(numbers);            // get current length
numbers[0];              // index access
```

`dynam` works with any type including typed structs:

```c
dynam string names = [];
dynam Vec3 positions = [];
```

---

## 5. Tuples

A tuple is a dynamic mixed-type collection declared with `[]`.

```c
tuple t = [1, "hello", 3.14];

t[0]        // 1
t[1]        // "hello"
t[2]        // 3.14
len(t)      // 3
```

Tuples can be passed to and returned from functions:

```c
tuple get_info() {
    return [42, "answer", true];
}

tuple result = get_info();
```

---

## 6. Strings

`string` is a native type in C△. It wraps `char*` with length and capacity management.

```c
string name = "hello";

name.append(" world");    // "hello world"
len(name);                // 11
name[0];                  // 'h'
name.raw;                 // access underlying char* for C interop
```

---

## 7. Memory Management

```c
// stack
int x = 5;

// heap
allocate int y = 10;
free y;

// heap with auto cleanup
autoremove allocate int* ptr = &x;
int z = ptr;    // last use — ptr freed here automatically

// robbery
allocate int* ptr2 = &ptr;    // ptr2 inherits ptr's space, becomes plain variable
```

---

## 8. Assembly Blocks

```c
asm void my_func(int x) {
    syntax_x86_64_linux

    section .text
        mov rax, x
        add rax, 1
        return
}
```

---

## 9. Imports

```c
#include <stdio.h>              // C library
using printd from <plstd>       // explicit plstd import (optional)
show lib                        // globalize all of plstd
using Arena from "arena"        // local library
using vars&a                    // intra file reference (immutable)
```

---

## 10. Namespaces

```c
// declaration
space myspace {
    void random() {
        printd("nothing");
    }
}

// access
myspace:random();

// globalize
show myspace;
random();    // no prefix needed after show
```

---

## 11. Printing

### `printd`

Type aware print. No format string needed.

```c
printd(42);             // 42
printd(3.14);           // 3.14
printd("hello");        // hello
printd(arr);            // [1, 2, 3, 4, 5]
```

### `printfs`

F-string print. Expressions inside `{}` are evaluated inline.

```c
string name = "world";
int x = 42;
printfs("Hello {name}!");          // Hello world!
printfs("x * 2 is {x * 2}");      // x * 2 is 84
```

---

## 12. C Interoperability

C△ is 100% C11 compatible minus a small deprecated list.

```c
#include <stdio.h>
#include <math.h>

int main() {
    printf("Hello from C!\n");    // works perfectly
    double x = sqrt(16.0);        // works perfectly
    return 0;
}
```

C functions, structs, macros, and preprocessor directives all work as they do in C11. C△ features can be mixed freely with C code in the same file.
