using "../plstd/string"

int test_basic_calls() {
    string a = "hello";
    string b = "world";
    
    // Test basic func@lib calls
    int result1 = strcmp@string(a, b);
    int result2 = strlen@string(a);
    
    // Test nested calls
    int result3 = strlen@string(strcpy@string(a, b));
    
    // Test in expressions
    int total = strlen@string(a) + strlen@string(b);
    
    // Test as function arguments
    int result4 = strcmp@string(strcpy@string(a, "test"), b);
    
    return total;
}

int test_multiple_libs() {
    // Test using different libraries
    string s1 = "hello";
    string s2 = "world";
    
    int len1 = strlen@string(s1);
    int cmp1 = strcmp@string(s1, s2);
    
    return len1 + cmp1;
}
