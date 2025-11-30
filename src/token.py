from enum import Enum
from dataclasses import dataclass
from typing import Any


class TokenType(Enum):
    EOF = 0
    IF = 1
    ELIF = 2
    ELSE = 3
    ENDIF = 4
    FOR = 5
    ENDFOR = 6
    WHILE = 7
    ENDWHILE = 8
    BREAK = 9
    CONTINUE = 10
    FUNC = 11
    ENDFUNC = 12
    RETURN = 13
    CALL = 14
    INCLUDE = 40
    VAR = 15
    LET = 16
    ASM_LINE = 17
    NEWLINE = 18
    STRING = 19
    NUMBER = 20
    EQ = 21
    NE = 22
    LT = 23
    GT = 24
    LE = 25
    GE = 26
    ASSIGN = 27
    COMMA = 28
    LPAREN = 29
    RPAREN = 30
    LBRACKET = 31
    RBRACKET = 32
    PLUS = 33
    MINUS = 34
    MULTIPLY = 35
    DIVIDE = 36
    MODULO = 37
    REGISTER = 38
    IDENTIFIER = 39
    ASTERISK = 41


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    col: int = 0
