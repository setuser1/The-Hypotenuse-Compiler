// Test that compiler-generated string operations don't depend on libc

string base = "hello";

int main() {
    string a = "foo";
    string b = "bar";

    // Test: len() on strings
    int n = len(a);

    // Test: string concatenation with +
    string c = a + b;

    // Test: string reassignment with literal
    a = "newvalue";

    // Test: string reassignment with concatenation
    a = a + "more";

    return n;
}
