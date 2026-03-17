# C△ Type System

This document describes every type available in C△, their storage layout, valid operations, and how they interact with the `auto` dynamic type.

---

## Primitive Types

All C11 primitive types are available without change.

| Type | Size | Description |
|---|---|---|
| `char` | 1 byte | Single character or small integer |
| `short` | 2 bytes | Short integer |
| `int` | 4 bytes | Standard integer |
| `long` | 8 bytes (x86_64) | Long integer |
| `float` | 4 bytes | Single precision floating point |
| `double` | 8 bytes | Double precision floating point |
| `void` | — | Absence of value, only valid as return type or pointer base |
| `unsigned` | varies | Unsigned modifier for integer types |
| `signed` | varies | Signed modifier for integer types |

All C11 integer promotions, implicit conversions, and arithmetic rules apply to these types.

---

## The `auto` Type

`auto` is a first-class dynamic type. It is not the C11 storage-class `auto` — that keyword is deprecated and repurposed.

```c
auto x = 42;          // compile-time inference: int
auto y = "hello";     // compile-time inference: string
auto z = 3.14;        // compile-time inference: float
```

**At compile time:** the Structor and simulation pass infer the concrete type from the right-hand side where possible. If the concrete type is statically known, the `auto` variable is treated identically to a typed variable during code generation.

**At runtime:** when the type cannot be determined statically (e.g. the value comes from a dynamic source), the variable is stored with a runtime type tag.

**As a parameter type:**

```c
void print_anything(auto value) {
    printf("%k\n", value);    // %k format specifier handles any auto value
}
```

**As a return type:**

```c
auto identity(auto x) {
    return x;
}
```

**Multiple variable packing:**

```c
auto x, z, w = someValue;    // x, z, and w all initialized to someValue
```

**Format specifier:** `%k` is the format specifier for `auto` typed values in `printf`-style calls. It resolves to the correct format at runtime.

---

## The `string` Type

`string` is a native C△ type. It wraps a heap-allocated `char*` with an integer length and capacity.

```c
string name = "hello";
string greeting = "world";
```

**Operations:**

| Operation | Description |
|---|---|
| `name.append(s)` | Append another string or string literal |
| `len(name)` | Number of characters |
| `name[i]` | Character at index `i` — returns `char` |
| `name.raw` | Underlying `char*` — for C library interop |

**Interoperability:** passing a `string` to a C function expecting `char*` requires `.raw`:

```c
string path = "/etc/hosts";
FILE* f = fopen(path.raw, "r");
```

---

## Sized Char Arrays

`char[n]` declares a fixed-size character buffer on the stack.

```c
char[20] buffer = "Hello, World!";
char[64] name;
```

This is distinct from `string`. A `char[n]` is a plain C array with a fixed compile-time size. It does not carry length or capacity metadata and cannot be resized.

---

## Dynamic Arrays — `dynam`

`dynam` declares a resizable array of a single type.

```c
dynam int numbers = [1, 2, 3, 4, 5];
dynam string names = [];
```

**Operations:**

| Operation | Description |
|---|---|
| `.push(value)` | Append an element |
| `.pop()` | Remove and return the last element |
| `.remove(i)` | Remove element at index `i` |
| `arr[i]` | Index access |
| `len(arr)` | Current element count |

`dynam` works with any type including `typed struct` types:

```c
dynam Vec3 positions = [];
positions.push(Vec3(1.0, 2.0, 3.0));
```

---

## Tuples

A tuple is a fixed-on-creation, mixed-type ordered collection. Elements may have different types.

```c
tuple t = [1, "hello", 3.14];

t[0]        // 1       (int)
t[1]        // "hello" (string)
t[2]        // 3.14    (float)
len(t)      // 3
```

Tuples can be returned from functions:

```c
tuple get_info() {
    return [42, "answer"];
}
```

Tuple element types are tracked at runtime. Assigning a tuple element to an `auto` variable preserves the runtime type.

---

## Plain Structs

A plain `struct` is a data container. It is not a native type — it cannot be used as the element type of `dynam`, as a parameter type without a pointer, or as a return type in the same way a primitive can. It supports constructors declared on the struct name line and optional member functions.

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

---

## Typed Structs

A `typed struct` is a first-class native type. Once declared, it can be used anywhere a primitive type can: as a `dynam` element, `auto` value, function parameter, or return type.

```c
typed struct Vec3(float x, float y, float z) {
    float self.x = x;
    float self.y = y;
    float self.z = z;

    float magnitude() {
        return self.x * self.x + self.y * self.y + self.z * self.z;
    }
}

Vec3 v(1.0, 0.0, 0.0);
dynam Vec3 path;
auto foo(Vec3 v) { return v.magnitude(); }
```

**Inheritance** is supported only for `typed struct` via `&`:

```c
typed struct Dog&Animal(string name) {
    init(string name) {
        self.name = name;
    }
    void speak() { printf("Woof!\n"); }
}
```

Multiple inheritance chains `&` types. Constructor order is left to right. Name conflicts are resolved via parent namespace:

```c
typed struct C&A&B { ... }

C obj(...);
obj.A.method();    // calls A's method
obj.B.method();    // calls B's method
```

---

## Pointer Types

C pointer syntax is fully supported:

```c
int* ptr = &x;
ptr->field;       // C pointer member access
*ptr;             // dereference
```

Pointers to heap-allocated objects are created via `allocate`:

```c
allocate int* buf [256];    // heap, 256 ints
free buf;                   // manual deallocation
```

See `memory.md` for `autoremove` and robbery.

---

## Type Coercion and Compatibility

- C△ inherits all C11 implicit arithmetic conversions between primitive types.
- `string` and `char*` are not implicitly interchangeable — use `.raw` to extract the underlying `char*`.
- `auto` accepts any value. Passing a concrete type to an `auto` parameter is always valid.
- A `typed struct` can be passed to an `auto` parameter; the runtime type tag records its concrete type.
- `dynam` and `tuple` cannot be implicitly cast to each other.

---

## The `Typed` Keyword (Library Files Only)

Inside `.plib` library files, `Typed` declares a template struct for native types — effectively a parameterised typedef.

```c
Typed Stack(T) {
    dynam T items;
    void push(T val) { items.push(val); }
    T pop() { return items.pop(); }
}
```

Users instantiate a `Typed` template with a concrete type:

```c
Stack(int) int_stack;
int_stack.push(42);
```

`Typed` is exclusively a `.plib` construct and cannot appear in `.ctri` source files, except as a plain `typedef` alias.

---

## The `Worded` Keyword (Library Files Only)

`Worded` defines a keyword alias — a template for language extension inside `.plib` files. It allows library authors to introduce new syntax sugar without modifying the compiler.

Protected C△ keywords cannot be shadowed by `Worded`.

---

## `len()`

`len()` is a compiler built-in that returns the logical length of any collection or string.

| Argument | Return value |
|---|---|
| `string` | Number of characters |
| `dynam` | Number of elements |
| `tuple` | Number of elements |
| `char[n]` | Declared size `n` |
| integer | Number of decimal digits |
