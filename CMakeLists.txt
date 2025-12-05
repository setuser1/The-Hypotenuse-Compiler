cmake_minimum_required(VERSION 3.28.0)
project(C_Triangle C)

set(CMAKE_C_STANDARD 11)

add_executable(C_Triangle src/main.c
        src/lexer.c
        src/parser.c
        src/compiler.h
        src/main.c
)
