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
        for line_num, line in enumerate(self.lines, 1):
            original_line = line
            line = line.strip()
            
            if not line or line.startswith(';'):
                self.tokens.append(Token(TokenType.ASM_LINE, original_line, line_num))
                continue
            
            first_word = line.split()[0].lower() if line.split() else ''
            
            if first_word in self.keywords:
                self.tokenize_line(line, line_num)
            else:
                self.tokens.append(Token(TokenType.ASM_LINE, original_line, line_num))
        
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
