# C△ Type System

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

C△ supports all C11 primitive types plus several new first-class types designed for modern systems programming.

---

## Primitive Types (inherited from C11)

| Type | Size | Description |
|---|---|---|
| `int` | 4 bytes | Signed 32-bit integer |
| `unsigned int` | 4 bytes | Unsigned 32-bit integer |
| `short` | 2 bytes | Signed 16-bit integer |
| `long` | 8 bytes | Signed 64-bit integer |
| `char` | 1 byte | Single byte / ASCII character |
| `float` | 4 bytes | Single-precision float |
| `double` | 8 bytes | Double-precision float |
| `void` | — | No type |

---

## Pointers

C△ supports standard C-style pointers with the `*` syntax.

### Declaration

```c
int* ptr;           // Pointer to int
int** ptr2;         // Pointer to pointer
char* str;          // Pointer to char (string)
```

### Address-of and Dereference

```c
int x = 42;
int* ptr = &x;      // Address-of operator &
int y = *ptr;       // Dereference operator *
```

---

## *NEW* C△ New Types

### `string` — First-class string

```c
string greeting = "Hello, world!";
string name = "Hypotenuse";

// Concatenation
string full = greeting + " " + name;

// f-string printing via plstd
printfs("{greeting}, {name}!");
```

---

### `auto` — Dynamic / Inferred Type

```c
auto x = 42;          // inferred as int
auto s = "hello";     // inferred as string
auto f = 3.14;        // inferred as double

// Use %k format specifier for auto in printfs
printf("%k", x);
```

> `auto` is type-aware at runtime via the simulation pass.

---

### `dynam` — Dynamic Array

```c
dynam int numbers = [1, 2, 3, 4, 5];
numbers.push(6);
numbers.pop();       // removes last
numbers.remove(0);   // removes by index
int size = len(numbers);
```

> `dynam` arrays grow and shrink at runtime. No fixed capacity.

---

### `tuple` — Heterogeneous List

```c
tuple t = [1, "hello", 3.14, 'x'];
auto first = t[0];    // 1
auto second = t[1];   // "hello"
```

> Tuples are declared with `[]` and can hold mixed types.

---

## Struct Types

### Plain Struct

Constructors, member functions, **no inheritance**, not a native type.

```c
struct Vec2(float x, float y) {
    init { self.x = 0.0; self.y = 0.0; }
    end { /* cleanup */ }

    float length() {
        return sqrt(x*x + y*y);
    }
}

Vec2 v = Vec2(3.0, 4.0);
printd(v.length());   // 5.0
```

---

### `Typed` Struct — Native Type + Inheritance

Constructors, member functions, **inheritance**, becomes a native type.

```c
typed struct Animal(string name) {
    init {...}
    string speak() { return "..."; }
    end {...}
}

typed struct Dog&Animal(string name) {
    init {...}
    string speak() { return "Woof!"; }
    end {...}
}

Dog d = Dog("Rex");
printfs(d.speak());   // Woof!
```

#### Multiple Inheritance

```c
typed struct PoliceDog&Dog&Animal(string name, int badge) {
    init {...}
    // Constructor order: Animal -> Dog -> PoliceDog
    // Conflict resolution: obj.Animal.speak(), obj.Dog.speak()
    end {...}
}
```

---

## Type Format Specifiers

| Specifier | Type |
|---|---|
| `%d` | `int` |
| `%f` | `float` / `double` |
| `%s` | `string` / `char*` |
| `%c` | `char` |
| `%k` | `auto` (type-aware) *NEW* |
