from src.lexer import Lexer
from src.codegen import CodeGenerator
from libs.stdio import StandardLibrary
from src.token import TokenType
import os


class SyntaxChecker:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errors = []
    
    def check(self):
        self.check_structure()
        return self.errors
    
    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    
    def advance(self):
        self.pos += 1
    
    def add_error(self, message, token=None):
        if token:
            self.errors.append(f"Line {token.line}: {message}")
        else:
            current = self.current_token()
            if current:
                self.errors.append(f"Line {current.line}: {message}")
            else:
                self.errors.append(message)
    
    def check_structure(self):
        stack = []
        
        while self.pos < len(self.tokens):
            token = self.current_token()
            
            if token.type == TokenType.EOF:
                break
            
            if token.type == TokenType.IF:
                stack.append(('if', token.line))
            elif token.type == TokenType.FOR:
                stack.append(('for', token.line))
            elif token.type == TokenType.WHILE:
                stack.append(('while', token.line))
            elif token.type == TokenType.FUNC:
                stack.append(('func', token.line))
            elif token.type == TokenType.ELIF:
                if not stack or stack[-1][0] != 'if':
                    self.add_error("'elif' without matching 'if'", token)
            elif token.type == TokenType.ELSE:
                if not stack or stack[-1][0] != 'if':
                    self.add_error("'else' without matching 'if'", token)
            elif token.type == TokenType.ENDIF:
                if not stack or stack[-1][0] != 'if':
                    self.add_error("'endif' without matching 'if'", token)
                else:
                    stack.pop()
            elif token.type == TokenType.ENDFOR:
                if not stack or stack[-1][0] != 'for':
                    self.add_error("'endfor' without matching 'for'", token)
                else:
                    stack.pop()
            elif token.type == TokenType.ENDWHILE:
                if not stack or stack[-1][0] != 'while':
                    self.add_error("'endwhile' without matching 'while'", token)
                else:
                    stack.pop()
            elif token.type == TokenType.ENDFUNC:
                if not stack or stack[-1][0] != 'func':
                    self.add_error("'endfunc' without matching 'func'", token)
                else:
                    stack.pop()
            
            self.advance()
        
        for struct_type, line in stack:
            self.errors.append(f"Line {line}: Unclosed '{struct_type}' statement")

# ============================================
# COMPILER
# ============================================

class Compiler:
    def __init__(self, input_file, output_file=None, verbose=False):
        self.input_file = input_file
        self.output_file = output_file or input_file.replace('.asm', '_compiled.asm')
        self.verbose = verbose
        self.stdlib = StandardLibrary()
    
    def log(self, message):
        if self.verbose:
            print(message)
    
    def compile(self):
        self.log(f"[*] Compiling {self.input_file}...")
        
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                source = f.read()
        except FileNotFoundError:
            print(f"[!] Error: File '{self.input_file}' not found")
            return False
        except Exception as e:
            print(f"[!] Error reading file: {e}")
            return False
        
        self.log("[*] Tokenizing source code...")
        try:
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            self.log(f"    Generated {len(tokens)} tokens")
        except SyntaxError as e:
            print(f"[!] Lexer error: {e}")
            return False
        except Exception as e:
            print(f"[!] Unexpected lexer error: {e}")
            return False
        
        self.log("[*] Checking syntax...")
        try:
            checker = SyntaxChecker(tokens)
            errors = checker.check()
            
            if errors:
                print("[!] Syntax errors found:")
                for error in errors:
                    print(f"    {error}")
                return False
            
            self.log("    Syntax OK")
        except Exception as e:
            print(f"[!] Syntax checker error: {e}")
            return False
        
        self.log("[*] Generating assembly code...")
        try:
            codegen = CodeGenerator(tokens)
            generated_code, data_section, stdlib_used = codegen.generate()
            self.log(f"    Generated {len(generated_code.split(chr(10)))} lines")
            self.log(f"    Using stdlib functions: {', '.join(stdlib_used) if stdlib_used else 'none'}")
        except Exception as e:
            print(f"[!] Code generation error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        self.log("[*] Building final assembly file...")
        try:
            output = self.build_assembly(generated_code, data_section, stdlib_used)
        except Exception as e:
            print(f"[!] Assembly building error: {e}")
            return False
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            self.log(f"[+] Compilation successful: {self.output_file}")
            print(f"[+] Successfully compiled to: {self.output_file}")
        except Exception as e:
            print(f"[!] Error writing output file: {e}")
            return False
        
        return True
    
    def build_assembly(self, code_lines, data_section, stdlib_used):
        output = []
        
        output.append("; ========================================")
        output.append("; Generated by Advanced Assembly Compiler v2.0")
        output.append("; Target: Windows x64 (NASM)")
        output.append("; ========================================")
        output.append("")
        
        # Get stdlib dependencies
        deps = self.stdlib.get_dependencies(stdlib_used)
        
        # Add externs
        output.append("; External dependencies")
        output.append("extern ExitProcess")
        for ext in sorted(deps['externs']):
            output.append(f"extern {ext}")
        output.append("")
        
        # Data section
        output.append("; ========================================")
        output.append("; Data Section")
        output.append("; ========================================")
        output.append("section .data")
        
        if deps['data']:
            output.append("    ; Standard library data")
            for data_line in deps['data']:
                output.append(f"    {data_line}")
        
        if data_section:
            output.append("    ; User-defined strings")
            for data_line in data_section:
                output.append(f"    {data_line}")
        
        if not deps['data'] and not data_section:
            output.append("    ; No data")
        
        output.append("")
        
        # BSS section
        output.append("; ========================================")
        output.append("; BSS Section")
        output.append("; ========================================")
        output.append("section .bss")
        
        if deps['bss']:
            output.append("    ; Standard library variables")
            for bss_line in deps['bss']:
                output.append(f"    {bss_line}")
        else:
            output.append("    ; Define uninitialized variables here")
        
        output.append("")
        
        # Code section
        output.append("; ========================================")
        output.append("; Code Section")
        output.append("; ========================================")

        # If the user-supplied code already contains its own section/global/main
        # directives we should not inject another `section .text` or `main:` wrapper
        user_has_own_sections = False
        if isinstance(code_lines, str):
            lower = code_lines.lower()
            if 'section .text' in lower or '\nsection .text' in lower or 'global main' in lower or '\nmain:' in lower:
                user_has_own_sections = True

        if not user_has_own_sections:
            output.append("section .text")
            output.append("    global main")
            output.append("")

        # Standard library functions (always place them before user code so symbols are defined)
        if deps['code']:
            output.append("; ========================================")
            output.append("; Standard Library Functions")
            output.append("; ========================================")
            output.append(deps['code'])
            output.append("")

        # If we injected our own `main:` wrapper, do so and optionally initialize stdlib
        if not user_has_own_sections:
            output.append("; ========================================")
            output.append("; Main Program")
            output.append("; ========================================")
            output.append("main:")

            # Only call _init_stdio if we actually emitted stdlib code (so the symbol exists)
            if deps['code'] and ('_init_stdio' in deps['code'] or '_init_stdio' in deps.get('bss', [])):
                output.append("    ; Initialize standard library")
                output.append("    sub rsp, 40")
                output.append("    call _init_stdio")
                output.append("    add rsp, 40")
                output.append("")

            output.append("    ; User code begins")
            output.append(code_lines)
            output.append("    ; User code ends")
            output.append("")

            output.append("    ; Exit program")
            output.append("    xor rcx, rcx")
            output.append("    call ExitProcess")
        else:
            # User provides their own sections and likely their own entrypoint; just append
            output.append(code_lines)
        
        return '\n'.join(output)
    
    def get_output_file(self):
        return self.output_file
