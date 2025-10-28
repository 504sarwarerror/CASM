from src.token import Token, TokenType


class Lexer:
    def __init__(self, source):
        self.source = source
        self.lines = source.split('\n')
        self.tokens = []
        
        self.registers = {
            'rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp',
            'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15',
            'eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp', 'esp',
            'ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
            'al', 'bl', 'cl', 'dl', 'ah', 'bh', 'ch', 'dh'
        }
        
        self.keywords = {
            'if': TokenType.IF, 'elif': TokenType.ELIF,
            'else': TokenType.ELSE, 'endif': TokenType.ENDIF,
            'for': TokenType.FOR, 'endfor': TokenType.ENDFOR,
            'while': TokenType.WHILE, 'endwhile': TokenType.ENDWHILE,
            'break': TokenType.BREAK, 'continue': TokenType.CONTINUE,
            'func': TokenType.FUNC, 'endfunc': TokenType.ENDFUNC,
            'return': TokenType.RETURN, 'call': TokenType.CALL,
            'var': TokenType.VAR, 'let': TokenType.LET
        }
    
    def tokenize(self):
        i = 0
        total = len(self.lines)
        while i < total:
            line_num = i + 1
            original_line = self.lines[i]
            line = original_line.strip()

            # Preserve blank lines and pure-ASM/comment lines as ASM_LINE
            if not line or line.startswith(';'):
                self.tokens.append(Token(TokenType.ASM_LINE, original_line, line_num))
                i += 1
                continue

            # If this line starts a macro (%macro or macro) we want to preserve
            # the header and footer exactly as ASM_LINE, but still tokenize the
            # lines inside the macro so high-level constructs (if/endif, etc.)
            # are processed by the compiler. This allows macros to contain
            # high-level language features while keeping the macro directives
            # intact.
            lstripped = original_line.lstrip()
            first_word = lstripped.split()[0].lower() if lstripped.split() else ''
            if first_word.startswith('%'):
                maybe = first_word[1:]
            else:
                maybe = first_word

            if maybe == 'macro':
                # emit the header as a raw ASM_LINE so the exact directive is
                # preserved (we'll normalize to %macro later when writing out)
                self.tokens.append(Token(TokenType.ASM_LINE, original_line, line_num))
                # consume the header line and tokenize body lines until endmacro
                i += 1
                while i < total:
                    inner_line = self.lines[i]
                    inner_lstr = inner_line.strip().lower()
                    # if this line is endmacro or %endmacro, emit as ASM_LINE
                    if inner_lstr.startswith('endmacro') or inner_lstr.startswith('%endmacro'):
                        self.tokens.append(Token(TokenType.ASM_LINE, inner_line, i + 1))
                        i += 1
                        break
                    # otherwise tokenize the inner line normally
                    self.tokenize_line(inner_line, i + 1)
                    i += 1
                continue

            # otherwise continue normal handling for single line
            
            first_word = line.split()[0].lower() if line.split() else ''

            # Handle include directives specially (e.g. %include "file.asm" or include file.asm)
            if first_word in ('%include', 'include'):
                # extract the rest of the line after the directive
                rest = line[len(first_word):].strip()
                # strip surrounding quotes if present
                if rest.startswith('"') and rest.endswith('"'):
                    path = rest[1:-1]
                elif rest.startswith("'") and rest.endswith("'"):
                    path = rest[1:-1]
                else:
                    # take the first token (unquoted path)
                    path = rest.split()[0] if rest.split() else rest

                self.tokens.append(Token(TokenType.INCLUDE, path, line_num, 0))
                # preserve newline token for consistency
                self.tokens.append(Token(TokenType.NEWLINE, '\n', line_num))
                i += 1
                continue

            if first_word in self.keywords:
                self.tokenize_line(line, line_num)
                i += 1
            else:
                self.tokens.append(Token(TokenType.ASM_LINE, original_line, line_num))
                i += 1
        
        self.tokens.append(Token(TokenType.EOF, None, len(self.lines) + 1))
        return self.tokens
    
    def tokenize_line(self, line, line_num):
        i = 0
        
        while i < len(line):
            if line[i].isspace():
                i += 1
                continue
            
            if line[i] == ';':
                break
            
            # String literals
            if line[i] == '"':
                j = i + 1
                escaped = False
                while j < len(line):
                    if escaped:
                        escaped = False
                        j += 1
                        continue
                    if line[j] == '\\':
                        escaped = True
                        j += 1
                        continue
                    if line[j] == '"':
                        break
                    j += 1
                
                if j < len(line):
                    string_val = line[i+1:j]
                    string_val = string_val.replace('\\n', '\n').replace('\\t', '\t')
                    string_val = string_val.replace('\\r', '\r').replace('\\"', '"')
                    string_val = string_val.replace('\\\\', '\\')
                    self.tokens.append(Token(TokenType.STRING, string_val, line_num, i))
                    i = j + 1
                else:
                    raise SyntaxError(f"Line {line_num}: Unterminated string")
                continue
            
            # Numbers
            if line[i].isdigit() or (line[i] == '0' and i+1 < len(line) and line[i+1] in 'xXbB'):
                j = i
                if line[i] == '0' and i+1 < len(line):
                    if line[i+1] in 'xX':
                        j += 2
                        while j < len(line) and line[j] in '0123456789abcdefABCDEF':
                            j += 1
                    elif line[i+1] in 'bB':
                        j += 2
                        while j < len(line) and line[j] in '01':
                            j += 1
                    else:
                        while j < len(line) and line[j].isdigit():
                            j += 1
                else:
                    while j < len(line) and line[j].isdigit():
                        j += 1
                
                self.tokens.append(Token(TokenType.NUMBER, line[i:j], line_num, i))
                i = j
                continue
            
            # Two-character operators
            if i + 1 < len(line):
                two_char = line[i:i+2]
                token_type = None
                
                if two_char == '==':
                    token_type = TokenType.EQ
                elif two_char == '!=':
                    token_type = TokenType.NE
                elif two_char == '<=':
                    token_type = TokenType.LE
                elif two_char == '>=':
                    token_type = TokenType.GE
                
                if token_type:
                    self.tokens.append(Token(token_type, two_char, line_num, i))
                    i += 2
                    continue
            
            # Single-character operators
            char_tokens = {
                '<': TokenType.LT, '>': TokenType.GT,
                '=': TokenType.ASSIGN, ',': TokenType.COMMA,
                '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
                '+': TokenType.PLUS, '-': TokenType.MINUS,
                '*': TokenType.MULTIPLY, '/': TokenType.DIVIDE,
                '%': TokenType.MODULO
            }
            
            if line[i] in char_tokens:
                self.tokens.append(Token(char_tokens[line[i]], line[i], line_num, i))
                i += 1
                continue
            
            # Identifiers and keywords
            if line[i].isalpha() or line[i] == '_':
                j = i
                while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                    j += 1
                
                word = line[i:j]
                word_lower = word.lower()
                
                if word_lower in self.keywords:
                    self.tokens.append(Token(self.keywords[word_lower], word_lower, line_num, i))
                elif word_lower in self.registers:
                    self.tokens.append(Token(TokenType.REGISTER, word, line_num, i))
                else:
                    self.tokens.append(Token(TokenType.IDENTIFIER, word, line_num, i))
                
                i = j
                continue
            
            i += 1
        
        self.tokens.append(Token(TokenType.NEWLINE, '\n', line_num))
