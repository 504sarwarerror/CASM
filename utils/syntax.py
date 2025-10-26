from src.lexer import Lexer
from src.codegen import CodeGenerator
from libs.stdio import StandardLibrary
from src.token import TokenType
from .formatter import format_and_merge
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
        # Put all compiler outputs under a single `build/` directory at repo root.
        # Use provided output_file when given, otherwise default to
        # build/<basename>-gen.asm
        repo_root = os.getcwd()
        build_dir = os.path.join(repo_root, 'build')
        try:
            os.makedirs(build_dir, exist_ok=True)
        except Exception:
            pass

        base = os.path.splitext(os.path.basename(input_file))[0]
        default_out = os.path.join(build_dir, f"{base}-gen.asm")
        self.output_file = output_file or default_out
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
        # Read the original input file and keep it intact as the base of the output.
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                original = f.read()
        except Exception:
            original = ''

        # If this file already contains a previous compiler-generated block,
        # strip that block to avoid repeatedly appending generated content.
        marker = '; Compiler-generated additions'
        if original and marker in original:
            original = original.split(marker, 1)[0].rstrip()

        # Parse generated code blocks (if any) emitted by the code generator.
        # Blocks are delimited by markers written into `code_lines`:
        #   ; __GEN_START__ <id> <start_line>
        #   ... generated asm ...
        #   ; __GEN_END__ <id> <end_line>
        gen_blocks = {}
        other_gen_lines = []
        if code_lines:
            collecting = False
            cur_id = None
            cur_start = None
            cur_lines = []
            for ln in code_lines.splitlines():
                s = ln.strip()
                if s.startswith('; __GEN_START__'):
                    parts = s.split()
                    if len(parts) >= 3:
                        cur_id = parts[2]
                        # third token might be the start line
                        try:
                            cur_start = int(parts[3]) if len(parts) > 3 else None
                        except Exception:
                            cur_start = None
                    else:
                        cur_id = None
                    collecting = True
                    cur_lines = []
                    continue
                if s.startswith('; __GEN_END__') and collecting:
                    parts = s.split()
                    end_id = parts[2] if len(parts) >= 3 else None
                    try:
                        cur_end = int(parts[3]) if len(parts) > 3 else None
                    except Exception:
                        cur_end = None
                    if cur_id is not None and (end_id is None or end_id == cur_id):
                        gen_blocks[cur_start] = {
                            'start': cur_start,
                            'end': cur_end,
                            'lines': cur_lines.copy()
                        }
                    collecting = False
                    cur_id = None
                    cur_start = None
                    cur_lines = []
                    continue

                if collecting:
                    cur_lines.append(ln)
                else:
                    # collect any other generated helper lines (not part of blocks)
                    other_gen_lines.append(ln)

        # If we found generated blocks, replace the corresponding source
        # line ranges in the original file with the generated assembly.
        processed_original = original
        if gen_blocks and original:
            orig_lines = original.splitlines()
            new_lines = []
            i = 1
            max_i = len(orig_lines)
            # create quick lookup by start line
            starts = {k: v for k, v in gen_blocks.items() if k}
            while i <= max_i:
                if i in starts:
                    blk = starts[i]
                    # append generated assembly for that block
                    new_lines.extend(blk['lines'])
                    # skip original lines up to end (if end provided)
                    end_line = blk.get('end') or i
                    i = end_line + 1
                else:
                    new_lines.append(orig_lines[i-1])
                    i += 1
            processed_original = '\n'.join(new_lines).rstrip()

        # Use formatter to produce final merged content
        deps = self.stdlib.get_dependencies(stdlib_used)
        final = format_and_merge(processed_original, other_gen_lines, gen_blocks, deps, data_section)
        return final

    def get_output_file(self):
        return self.output_file