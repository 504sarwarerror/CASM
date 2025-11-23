from src.lexer import Lexer
from src.codegen import CodeGenerator
from libs.stdio import StandardLibrary
from src.token import TokenType
from .formatter import format_and_merge
from .cli import CLI
from src.c_asm_converter import CAsmConverter
import os
import re
import pathlib


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
    def __init__(self, input_file, output_file=None, verbose=False, **kwargs):
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
        ext = os.path.splitext(input_file)[1]
        if ext.lower() == '.c':
            default_out = os.path.join(build_dir, f"{base}-gen.c")
        else:
            default_out = os.path.join(build_dir, f"{base}-gen.asm")
        self.output_file = output_file or default_out
        self.verbose = verbose
        self.target = kwargs.get('target', 'windows')
        self.stdlib = StandardLibrary(target=self.target)

    def log(self, message):
        if self.verbose:
            CLI.info(message)

    def compile(self, _included=None):
        if self.input_file.lower().endswith('.c'):
            try:
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                converter = CAsmConverter(source)
                output = converter.convert()
                
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                self.log(f"C conversion successful: {self.output_file}")
                CLI.success(f"Converted {os.path.basename(self.input_file)}")
                return True
            except Exception as e:
                CLI.error(f"C conversion error: {e}")
                import traceback
                traceback.print_exc()
                return False

        # CLI.step(f"Compiling {self.input_file}...") # Removed, spinner handles this

        # Track included files to avoid recursive inclusion loops.
        if _included is None:
            _included = set()

        # Scan the source for include directives and compile included files
        # before compiling this file. Supported forms (case-insensitive):
        #   include "path"
        #   include 'path'
        #   %include path
        # Paths are resolved relative to the including file's directory.
        include_re = re.compile(r'''^\s*(?:%?include)\s+(?:"([^"]+)"|'([^']+)'|([^\s;]+))''', re.IGNORECASE)
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                raw_lines = f.read().splitlines()
        except FileNotFoundError:
            CLI.error(f"File '{self.input_file}' not found")
            return False
        except Exception as e:
            CLI.error(f"Error reading file: {e}")
            return False

        includes_to_process = []
        for ln in raw_lines:
            m = include_re.match(ln)
            if m:
                path = m.group(1) or m.group(2) or m.group(3)
                if path:
                    # expand environment vars and user (~)
                    path = os.path.expandvars(path)
                    path = os.path.expanduser(path)
                    includes_to_process.append(path)

        for inc_path in includes_to_process:
            # resolve relative to this file
            if not os.path.isabs(inc_path):
                inc_abspath = os.path.normpath(os.path.join(os.path.dirname(self.input_file), inc_path))
            else:
                inc_abspath = os.path.normpath(inc_path)

            if inc_abspath in _included:
                # already processed
                continue

            if not os.path.exists(inc_abspath):
                CLI.error(f"Included file not found: {inc_abspath}")
                return False

            _included.add(inc_abspath)
            # compile included file and write its generated asm to the build dir
            child_compiler = Compiler(inc_abspath, output_file=None, verbose=self.verbose, target=self.target)
            # ensure child uses same included-set to avoid cycles
            ok = child_compiler.compile(_included)
            if not ok:
                CLI.error(f"Failed to compile included file: {inc_abspath}")
                return False

        # Re-open source to get the original content for tokenizing below
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                source = f.read()
        except Exception as e:
            CLI.error(f"Error reading file: {e}")
            return False

        with CLI.spinner(f"Compiling {os.path.basename(self.input_file)}..."):
            self.log("Tokenizing source code...")
            try:
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                self.log(f"    Generated {len(tokens)} tokens")
            except SyntaxError as e:
                CLI.error(f"Lexer error: {e}")
                return False
            except Exception as e:
                CLI.error(f"Unexpected lexer error: {e}")
                return False

            self.log("Checking syntax...")
            try:
                checker = SyntaxChecker(tokens)
                errors = checker.check()

                if errors:
                    CLI.error("Syntax errors found:")
                    for error in errors:
                        print(f"    {error}")
                    return False

                self.log("    Syntax OK")
            except Exception as e:
                CLI.error(f"Syntax checker error: {e}")
                return False

            self.log("Generating assembly code...")
            try:
                codegen = CodeGenerator(tokens, target=self.target)
                generated_code, data_section, stdlib_used = codegen.generate()
                self.log(f"    Generated {len(generated_code.split(chr(10)))} lines")
                self.log(f"    Using stdlib functions: {', '.join(stdlib_used) if stdlib_used else 'none'}")
            except Exception as e:
                CLI.error(f"Code generation error: {e}")
                import traceback
                traceback.print_exc()
                return False

            self.log("Building final assembly file...")
            try:
                output = self.build_assembly(generated_code, data_section, stdlib_used)
            except Exception as e:
                CLI.error(f"Assembly building error: {e}")
                return False

            try:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                self.log(f"Compilation successful: {self.output_file}")
            except Exception as e:
                CLI.error(f"Error writing output file: {e}")
                return False
        
        CLI.success(f"Compiled {os.path.basename(self.input_file)}")
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
            # Support nested generated blocks by using a stack. Each stack
            # frame holds the block id, start line and collected lines.
            stack = []
            for ln in code_lines.splitlines():
                s = ln.strip()
                if s.startswith('; __GEN_START__'):
                    parts = s.split()
                    bid = parts[2] if len(parts) >= 3 else None
                    try:
                        bstart = int(parts[3]) if len(parts) > 3 else None
                    except Exception:
                        bstart = None
                    # push a new frame
                    stack.append({'id': bid, 'start': bstart, 'lines': []})
                    continue

                if s.startswith('; __GEN_END__'):
                    parts = s.split()
                    end_id = parts[2] if len(parts) >= 3 else None
                    try:
                        bend = int(parts[3]) if len(parts) > 3 else None
                    except Exception:
                        bend = None
                    if stack:
                        frame = stack.pop()
                        # If this frame was nested inside another, merge its
                        # collected lines into the parent so the outer block
                        # replacement contains the inner content. Otherwise
                        # record it as a top-level generated block.
                        if stack:
                            # merge into parent's lines
                            stack[-1]['lines'].extend(frame['lines'])
                        else:
                            gen_blocks[frame['start']] = {
                                'start': frame['start'],
                                'end': bend,
                                'lines': frame['lines'].copy()
                            }
                    continue

                if stack:
                    # append into the current (top) block
                    stack[-1]['lines'].append(ln)
                else:
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

        # Rewrite any include directives in the original to point to the
        # generated file names (e.g. avatar.asm -> avatar-gen.asm).
        # This ensures we don't keep the original include and a generated
        # include side-by-side.
        try:
            include_re = re.compile(r'''^\s*(%?include)\s+(?:"([^"]+)"|'([^']+)'|([^\s;]+))''', re.IGNORECASE | re.MULTILINE)

            def _rewrite(m):
                directive = m.group(1) or 'include'
                path = m.group(2) or m.group(3) or m.group(4) or ''
                # compute the generated file path under the repo build/ directory
                try:
                    repo_root = os.getcwd()
                    build_dir = os.path.join(repo_root, 'build')
                    # basename of the original include (drop dirs)
                    base_name = os.path.splitext(os.path.basename(path))[0]
                    generated_abs = os.path.normpath(os.path.join(build_dir, f"{base_name}-gen.asm"))
                    # emit absolute path so NASM can find it regardless of cwd
                    new_path = generated_abs
                except Exception:
                    # fallback: preserve original behaviour but adjust basename
                    dirpart, fname = os.path.split(path)
                    base, ext = os.path.splitext(fname)
                    new_fname = f"{base}-gen.asm"
                    new_path = os.path.join(dirpart, new_fname) if dirpart else new_fname

                # always emit with double-quotes and use the same directive token
                return f"{directive} \"{new_path}\""

            processed_original = include_re.sub(_rewrite, processed_original)
        except Exception:
            # non-fatal: if rewriting fails, fall back to the unmodified original
            pass

        # Include any user-declared `extern <name>` from the original
        # source as requests to pull in stdlib wrappers. This lets users
        # write e.g. `extern rand` or `extern Sleep` to force the
        # corresponding stdlib helper to be defined in the generated file
        # even if the high-level call wasn't emitted by the codegen.
        user_externs = set(re.findall(r'(?m)^\s*extern\s+([A-Za-z_][A-Za-z0-9_]*)', original))
        # Only include stdlib wrappers when the user explicitly declares an
        # `extern` for them. This prevents the compiler from auto-defining
        # stdio helpers merely because a high-level `call` appeared in the
        # generated code. If callers want the wrapper, they must write
        # `extern <name>` in the source.
        if user_externs:
            combined_used = set(n.lower() for n in user_externs if isinstance(n, str))
        else:
            combined_used = set()

        # Use formatter to produce final merged content
        deps = self.stdlib.get_dependencies(combined_used)

        final = format_and_merge(processed_original, other_gen_lines, gen_blocks, deps, data_section)
        return final

    def get_output_file(self):
        return self.output_file