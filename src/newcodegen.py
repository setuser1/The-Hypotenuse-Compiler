import os
import sys
from typing import Optional
import error_msgs

from parser import (
    Alloc,
    ArrayAccess,
    ArrayDesignation,
    Assignment,
    Binary,
    Comma,
    Break,
    Call,
    Cast,
    Compound,
    CompoundLiteral,
    Continue,
    Declaration,
    Define,
    DesignatedInit,
    Do,
    ExposeDecl,
    ExprStmt,
    FieldAccess,
    For,
    Free,
    Function,
    Generic,
    Goto,
    If,
    Include,
    InitList,
    Label,
    LibAccess,
    Literal,
    Return,
    SpaceDecl,
    StructDef,
    Switch,
    Typedef,
    TypeExpr,
    Unary,
    UsingDecl,
    Var,
    While
)

DEFAULT_DYNAM_CAPACITY = 4

TYPE_MAP = {
    "string": "char*",
    "int": "int",
    "float": "float",
    "double": "double",
    "char": "char",
    "void": "void",
    "short": "short",
    "long": "long",
    "signed": "signed",
    "unsigned": "unsigned",
}

class CodeGen:
    def __init__(self, ast, structor, source_path=None, target_arch=None): 
        self.ast = ast
        self.structor = structor
        self.source_path = source_path
        self.target_arch = target_arch
        
        
        self._asm_blocks = []
        self.indent_level = 0 #tracks indentation
# new PR
