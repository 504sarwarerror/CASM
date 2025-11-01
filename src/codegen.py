from src.token import TokenType


class CodeGenerator:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.output = []
        self.label_counter = 0
        self.block_counter = 0
        self.stdlib_used = set()
        self.data_section = []
        self.string_counter = 0
        self.loop_stack = []
        self.functions = {}
        self.current_function = None
        self.register_map = {}
        # default to 64-bit generation; can be switched to 32-bit by
        # passing bits=32 when constructing CodeGenerator.
        self.bits = 64
        # prefer using the extended registers for temporary/callee-saved
        # allocations so generated code can use r8..r15 (and their d subregs)
        self._reg_pool = ['r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15', 'rbx']
    
    def generate(self):
        while self.pos < len(self.tokens):
            token = self.current_token()
            
            if token.type == TokenType.EOF:
                break
            # Allow a top-level 'bits 32' or 'bits 64' directive in the source
            # to switch code generation mode.
            elif token.type == TokenType.IDENTIFIER and str(token.value).lower() == 'bits':
                # consume 'bits'
                self.advance()
                num = self.current_token()
                if num and num.type == TokenType.NUMBER:
                    try:
                        self.set_bits(int(num.value))
                    except ValueError:
                        raise SyntaxError(f"Line {num.line}: invalid bits value '{num.value}'")
                    self.advance()
                else:
                    raise SyntaxError(f"Line {token.line}: expected number after 'bits'")
                # skip any newline after directive
                self.skip_newlines()
            elif token.type == TokenType.IF:
                self.generate_if()
            elif token.type == TokenType.FOR:
                self.generate_for()
            elif token.type == TokenType.WHILE:
                self.generate_while()
            elif token.type == TokenType.FUNC:
                self.generate_function()
            elif token.type == TokenType.CALL:
                self.generate_call()
            elif token.type == TokenType.RETURN:
                self.generate_return()
            elif token.type == TokenType.BREAK:
                self.generate_break()
            elif token.type == TokenType.CONTINUE:
                self.generate_continue()
            elif token.type == TokenType.ASM_LINE:
                # Do not inline raw ASM lines into the generated snippet.
                # The compiler will preserve the original source file and
                # append generated code afterwards. Skip these tokens so
                # we don't duplicate the user's assembly.
                self.advance()
            elif token.type == TokenType.NEWLINE:
                self.advance()
            elif token.type == TokenType.INCLUDE:
                # Include directives are rewritten at the assembly-build stage
                # to point to the generated files. Skip emitting an include here
                # to avoid duplicate includes in the final output.
                self.advance()
            else:
                self.advance()
        
        # Ensure there's a text section in the final assembly output. If the
        # user's source (or inline assembly) didn't include a `section .text`
        # declaration, prepend one so assemblers (NASM/YASM) have a code
        # section to put generated instructions into.
        assembly_text = '\n'.join(self.output)
        if 'section .text' not in assembly_text.lower():
            # Prefer to insert the text section before any `global` directive
            # (e.g. `global main`) so globals remain after the section line.
            # If no `global` is present, insert after any leading `bits` or
            # `default rel` directives. Fallback to the top if nothing
            # recognizable is found.
            insert_index = 0
            found_global = False
            for i, line in enumerate(self.output):
                if line.lstrip().lower().startswith('global '):
                    insert_index = i
                    found_global = True
                    break

            if not found_global:
                # look for trailing bits/default rel directives and place after
                last_dir = -1
                for i, line in enumerate(self.output):
                    s = line.strip().lower()
                    if s.startswith('bits ') or s.startswith('default rel'):
                        last_dir = i
                if last_dir != -1:
                    insert_index = last_dir + 1
                else:
                    insert_index = 0

            self.output.insert(insert_index, 'section .text')

        return '\n'.join(self.output), self.data_section, self.stdlib_used

    def set_bits(self, bits: int):
        """Set generation mode to 32 or 64 bit. Call before generate()."""
        if bits not in (32, 64):
            raise ValueError("bits must be 32 or 64")
        self.bits = bits
    
    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    
    def advance(self):
        self.pos += 1
        return self.current_token()
    
    def get_label(self):
        label = f".L{self.label_counter}"
        self.label_counter += 1
        return label

    def remap_reg(self, name):
        # Support case-insensitive lookup for register mappings. The lexer
        # may emit registers in different cases; prefer an exact match but
        # fall back to a lowercase key if present.
        if name in self.register_map:
            return self.register_map[name]
        lower = name.lower()
        return self.register_map.get(lower, name)

    def allocate_reg_for(self, orig_name):
        # lazy-init appropriate register pool for 32/64-bit modes
        if self.bits == 32 and self._reg_pool[0].startswith('r'):
            # 32-bit callee-saved candidates
            self._reg_pool = ['ebx', 'esi', 'edi']

        # find a free callee-saved register from the pool
        for r in self._reg_pool:
            if r not in self.register_map.values():
                # store both the original and lowercase keys so later
                # lookups (which may use different cases) succeed.
                self.register_map[orig_name] = r
                self.register_map[orig_name.lower()] = r
                return r
        # fallback: reuse the first pool entry
        self.register_map[orig_name] = self._reg_pool[0]
        self.register_map[orig_name.lower()] = self._reg_pool[0]
        return self._reg_pool[0]
    
    def skip_newlines(self):
        while self.current_token() and self.current_token().type == TokenType.NEWLINE:
            self.advance()

    def remap_asm_line(self, line: str) -> str:
        """Remap register identifiers inside a raw ASM line using current
        register_map. This replaces whole-word occurrences of known register
        names (case-insensitive) with their mapped names so loop counters
        allocated to callee-saved regs (r12/r13 -> r12d/r13d) are used
        inside emitted assembly lines.
        """
        import re

        def repl(m):
            tok = m.group(0)
            mapped = self.remap_reg(tok)
            return mapped

        # Replace identifiers (words) only. This is conservative but works for
        # typical assembly tokens like 'eax', 'ebx', 'r12', 'ecx', etc.
        return re.sub(r"\b[A-Za-z][A-Za-z0-9]*\b", repl, line)

    def parse_operand(self):
        """Parse an operand which may be:
        - a register (TokenType.REGISTER)
        - an identifier (TokenType.IDENTIFIER)
        - a memory operand like `[ident]` or `byte [ident]` (size prefix + bracket)

        Returns a tuple (operand_string, start_token) where operand_string is the
        textual assembly operand to use in generated code and start_token is the
        token where parsing began (useful for error line numbers).
        """
        tok = self.current_token()
        if not tok:
            return None, None

        # size-prefixed memory: e.g. "byte [running]" or "byte [i + 1]"
        if tok.type == TokenType.IDENTIFIER and (self.pos + 1) < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.LBRACKET:
            size = tok.value
            start = tok
            # consume size identifier
            self.advance()

            # expect '['
            if not self.current_token() or self.current_token().type != TokenType.LBRACKET:
                raise SyntaxError(f"Line {start.line}: Expected '[' after size specifier '{size}'")
            # consume '['
            self.advance()

            # collect tokens until closing ']'
            parts = []
            while self.current_token() and self.current_token().type != TokenType.RBRACKET:
                inner_tok = self.current_token()
                # remap registers inside the expression
                # Handle `%` macro-parameter token sequences like `%1` or `%ident`
                # The lexer emits '%' as a separate MODULO token followed by a
                # NUMBER/IDENTIFIER token; join them without a space so the
                # assembler sees "%1" instead of "% 1" which is invalid.
                if inner_tok.type == TokenType.MODULO:
                    # peek next token
                    next_pos = self.pos + 1
                    next_tok = self.tokens[next_pos] if next_pos < len(self.tokens) else None
                    if next_tok and next_tok.type in (TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER):
                        parts.append('%' + str(next_tok.value))
                        # consume both '%' and the following token
                        self.advance()
                        self.advance()
                        continue
                    else:
                        parts.append(str(inner_tok.value))
                        self.advance()
                        continue

                if inner_tok.type == TokenType.REGISTER:
                    parts.append(self.remap_reg(inner_tok.value))
                else:
                    parts.append(str(inner_tok.value))
                self.advance()

            if not self.current_token() or self.current_token().type != TokenType.RBRACKET:
                raise SyntaxError(f"Line {start.line}: Expected closing ']' for memory operand")
            # consume ']'
            self.advance()

            inner_val = ' '.join(parts).strip()
            if not inner_val:
                raise SyntaxError(f"Line {start.line}: Empty memory operand '[]'")
            return f"{size} [{inner_val}]", start

        # direct memory: [ident]
        if tok.type == TokenType.LBRACKET:
            start = tok
            # consume '['
            self.advance()
            parts = []
            while self.current_token() and self.current_token().type != TokenType.RBRACKET:
                inner_tok = self.current_token()
                # handle macro-param %n sequences as a single token
                if inner_tok.type == TokenType.MODULO:
                    next_pos = self.pos + 1
                    next_tok = self.tokens[next_pos] if next_pos < len(self.tokens) else None
                    if next_tok and next_tok.type in (TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER):
                        parts.append('%' + str(next_tok.value))
                        self.advance()
                        self.advance()
                        continue
                    else:
                        parts.append(str(inner_tok.value))
                        self.advance()
                        continue

                if inner_tok.type == TokenType.REGISTER:
                    parts.append(self.remap_reg(inner_tok.value))
                else:
                    parts.append(str(inner_tok.value))
                self.advance()

            if not self.current_token() or self.current_token().type != TokenType.RBRACKET:
                raise SyntaxError(f"Line {start.line}: Expected closing ']' for memory operand")
            # consume ']'
            self.advance()

            inner_val = ' '.join(parts).strip()
            if not inner_val:
                raise SyntaxError(f"Line {start.line}: Empty memory operand '[]'")
            return f"[{inner_val}]", start

        # simple identifier, register or number
        if tok.type in [TokenType.IDENTIFIER, TokenType.REGISTER, TokenType.NUMBER]:
            val = tok.value
            start = tok
            # remap registers to internal callee-saved names
            if tok.type == TokenType.REGISTER:
                val = self.remap_reg(val)
            self.advance()
            return val, start

        # anything else is invalid here
        raise SyntaxError(f"Line {tok.line if tok else '?'}: Unexpected token '{tok.value if tok else None}' when parsing operand")
    
    def generate_if(self):
        # mark the start line of this high-level block so we can replace it
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        # emit start marker
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()
        
        # Expect: IF <operand> <comparison-op> <number|operand>
        var, var_token = self.parse_operand()
        if not var or not var_token:
            raise SyntaxError(f"Line {var_token.line if var_token else '?'}: Expected identifier, register or memory operand after 'if'")

        op = self.current_token()
        if not op or op.type not in [TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE]:
            raise SyntaxError(f"Line {op.line if op else '?'}: Expected comparison operator after '{var}' in if-statement")
        self.advance()

        # Right-hand side can be a number or another operand (identifier/register/memory)
        rhs_token = self.current_token()
        if not rhs_token:
            raise SyntaxError(f"Line {op.line if op else '?'}: Expected value after comparison in if-statement")

        if rhs_token.type == TokenType.NUMBER:
            rhs_val = rhs_token.value
            self.advance()
            rhs_tok_info = rhs_token = rhs_token
        else:
            rhs_val, rhs_tok_info = self.parse_operand()

        self.skip_newlines()

        label_next = self.get_label()
        label_end = self.get_label()

        # Decide proper cmp ordering so NASM never sees immediate, immediate or
        # immediate as the destination. If both sides are numeric, evaluate at
        # compile-time and emit an unconditional jump when the condition is false.
        if var_token.type == TokenType.NUMBER and (rhs_tok_info and rhs_tok_info.type == TokenType.NUMBER):
            # both immediates: evaluate condition now
            a = int(var)
            b = int(rhs_val)
            cond_map = {
                TokenType.EQ: (a == b), TokenType.NE: (a != b),
                TokenType.LT: (a < b), TokenType.GT: (a > b),
                TokenType.LE: (a <= b), TokenType.GE: (a >= b)
            }
            if not cond_map.get(op.type, False):
                # condition is false at compile time: skip true-block
                self.output.append(f"    jmp {label_next}")
        else:
            # choose left and right so left is register/memory (valid cmp dest)
            if var_token.type == TokenType.NUMBER:
                # swap: rhs becomes left operand
                left = rhs_val
                # remap register if needed
                if rhs_tok_info and rhs_tok_info.type == TokenType.REGISTER:
                    left = self.remap_reg(left)
                right = var
            else:
                left = var
                if var_token.type == TokenType.REGISTER:
                    left = self.remap_reg(left)
                right = rhs_val

            self.output.append(f"    cmp {left}, {right}")

        jump_map = {
            TokenType.EQ: 'jne', TokenType.NE: 'je',
            TokenType.LT: 'jge', TokenType.GT: 'jle',
            TokenType.LE: 'jg', TokenType.GE: 'jl'
        }
        
        try:
            jm = jump_map[op.type]
        except KeyError:
            raise SyntaxError(f"Line {op.line}: Unsupported comparison operator '{op.value}' in if-statement")
        
        # FIXED: Jump to label_next when condition is FALSE
        self.output.append(f"    {jm} {label_next}")
        
        # Generate the TRUE block (this will include the "jmp error" from your code)
        self.generate_block([TokenType.ELIF, TokenType.ELSE, TokenType.ENDIF])
        
        # FIXED: Only jump to end if there are elif/else blocks coming
        has_elif_or_else = self.current_token() and self.current_token().type in [TokenType.ELIF, TokenType.ELSE]
        if has_elif_or_else:
            self.output.append(f"    jmp {label_end}")
        
        # Place label_next (where we jump when condition is FALSE)
        self.output.append(f"{label_next}:")
        
        has_else = False
        while self.current_token() and self.current_token().type in [TokenType.ELIF, TokenType.ELSE]:
            if self.current_token().type == TokenType.ELIF:
                label_next = self.get_label()
                
                self.advance()
                var, var_token = self.parse_operand()
                if not var or not var_token:
                    raise SyntaxError(f"Line {var_token.line if var_token else '?'}: Expected identifier, register or memory operand after 'elif'")
                op = self.current_token()
                if not op or op.type not in [TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE]:
                    raise SyntaxError(f"Line {op.line if op else '?'}: Expected comparison operator after '{var}' in elif-statement")
                self.advance()

                rhs_token = self.current_token()
                if not rhs_token:
                    raise SyntaxError(f"Line {op.line if op else '?'}: Expected value after comparison in elif-statement")
                if rhs_token.type == TokenType.NUMBER:
                    rhs_val = rhs_token.value
                    self.advance()
                    rhs_info = rhs_token
                else:
                    rhs_val, rhs_info = self.parse_operand()
                self.skip_newlines()

                # Handle numeric left-side or both-numeric like in `if 1 == 1`
                if var_token.type == TokenType.NUMBER and (rhs_info and rhs_info.type == TokenType.NUMBER):
                    a = int(var)
                    b = int(rhs_val)
                    cond_map = {
                        TokenType.EQ: (a == b), TokenType.NE: (a != b),
                        TokenType.LT: (a < b), TokenType.GT: (a > b),
                        TokenType.LE: (a <= b), TokenType.GE: (a >= b)
                    }
                    if not cond_map.get(op.type, False):
                        self.output.append(f"    jmp {label_next}")
                else:
                    # choose left so it's register/memory
                    if var_token.type == TokenType.NUMBER:
                        left = rhs_val
                        if rhs_info and rhs_info.type == TokenType.REGISTER:
                            left = self.remap_reg(left)
                        right = var
                    else:
                        left = var
                        if var_token.type == TokenType.REGISTER:
                            left = self.remap_reg(left)
                        right = rhs_val

                    self.output.append(f"    cmp {left}, {right}")
                    try:
                        jm2 = jump_map[op.type]
                    except KeyError:
                        raise SyntaxError(f"Line {op.line}: Unsupported comparison operator '{op.value}' in elif-statement")
                    self.output.append(f"    {jm2} {label_next}")
                
                self.generate_block([TokenType.ELIF, TokenType.ELSE, TokenType.ENDIF])
                self.output.append(f"    jmp {label_end}")
                self.output.append(f"{label_next}:")
                
            elif self.current_token().type == TokenType.ELSE:
                has_else = True
                self.advance()
                self.skip_newlines()
                self.generate_block([TokenType.ENDIF])
                break
        
        # Only place end label if we had elif/else
        if has_elif_or_else:
            self.output.append(f"{label_end}:")

        # mark end line and emit end marker
        end_line = self.current_token().line if self.current_token() else start_line
        self.output.append(f"; __GEN_END__ {block_id} {end_line}")

        if self.current_token() and self.current_token().type == TokenType.ENDIF:
            self.advance()

    def generate_for(self):
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()
        
        # Support two syntaxes:
        # 1) for <var> = <start>, <end>
        # 2) for <var> <comparison-op> <operand>    (treated as start=0, end=<operand>)
        var_token = self.current_token()
        if not var_token:
            raise SyntaxError(f"Line {self.current_token().line if self.current_token() else '?'}: Expected loop variable after 'for'")
        # Capture the raw token so we can detect register-specified loops
        is_register_var = (var_token.type == TokenType.REGISTER)
        var = var_token.value
        self.advance()

        # If next token is an assignment '=', parse start and end (old syntax)
        next_tok = self.current_token()
        if next_tok and next_tok.type == TokenType.ASSIGN:
            # consume '='
            self.advance()
            # parse start operand (support numbers, identifiers, registers, or memory)
            if self.current_token() and self.current_token().type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER, TokenType.LBRACKET]:
                start, _ = self.parse_operand()
            else:
                start = self.current_token().value if self.current_token() else '0'
                self.advance()

            # consume optional comma
            if self.current_token() and self.current_token().type == TokenType.COMMA:
                self.advance()

            # parse end operand similarly
            if self.current_token() and self.current_token().type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER, TokenType.LBRACKET]:
                end, _ = self.parse_operand()
            else:
                end = self.current_token().value if self.current_token() else '0'
                self.advance()
        else:
            # Comparison-style: e.g. 'for r12d < dword [num_frames]'
            if next_tok and next_tok.type in [TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE]:
                # consume comparison operator
                self.advance()
                # parse the right-hand operand (could be memory/identifier/number/register)
                end, _ = self.parse_operand()
                # treat start as 0
                start = '0'
            else:
                raise SyntaxError(f"Line {var_token.line}: Unsupported 'for' syntax; expected '=' or comparison operator after variable")
        self.skip_newlines()
        
        # allocate a callee-saved register for the loop variable to survive calls
        # If the user specified a register (e.g. `for r12 = ...`), try to
        # reserve that specific register; otherwise choose from preferred
        # pools depending on nesting depth so nested loops get different
        # registers.
        internal_reg = None
        loop_depth = len(self.loop_stack)  # 0 for outermost
        if self.bits == 64:
            # preferred order by depth: prefer r8..r15 to keep registers
            # available for manual use by the programmer
            base_prefs = ('r8','r9','r10','r11','r12','r13','r14','r15','rbx')

            # If the loop variable is a register name, try to use it
            if is_register_var:
                desired = var.lower()
                # normalize names like 'r12d' -> 'r12'
                if desired.endswith('d') and desired.startswith('r'):
                    desired = desired[:-1]
                # if desired is available in the register pool and not used,
                # reserve it
                if desired in base_prefs and desired not in self.register_map.values():
                    internal_reg = desired
                    self.register_map[var] = internal_reg
                    self.register_map[var.lower()] = internal_reg

            # If not reserved yet, pick a preferred one by loop depth to avoid
            # nested conflicts
            if internal_reg is None:
                # rotate preferences by depth so nested loops choose different
                prefs = tuple(base_prefs[loop_depth % len(base_prefs):] + base_prefs[:loop_depth % len(base_prefs)])
                for pref in prefs:
                    if pref not in self.register_map.values():
                        self.register_map[var] = pref
                        self.register_map[var.lower()] = pref
                        internal_reg = pref
                        break

        if internal_reg is None:
            # fallback: allocate from pool which also records mapping
            internal_reg = self.allocate_reg_for(var)

        label_start = self.get_label()
        label_end = self.get_label()
        label_continue = self.get_label()

        self.loop_stack.append({
            'break': label_end,
            'continue': label_continue
        })

        # If start/end use 32-bit sized memory (e.g. 'dword [...]'), prefer the
        # 32-bit subregister (r12 -> r12d) to avoid operand-size mismatches.
        def subreg32(r):
            # r like 'r12' or 'rbx' -> 'r12d' or 'ebx'
            if r.startswith('r') and r[1].isdigit():
                return r + 'd'
            if r.startswith('r'):
                return 'e' + r[1:]
            return r

        # Prefer the 32-bit subregister for loop counters when targeting
        # x64. Loop counters are typically used with 32-bit arithmetic
        # (mul/div with eax/edx, index calculations), so use r12d/r13d to
        # avoid operand-size mismatches with instructions that operate on
        # 32-bit registers (eax, edx, etc.). For 32-bit target keep the
        # allocated register as-is.
        if self.bits == 64:
            loop_reg = subreg32(internal_reg)
        else:
            loop_reg = internal_reg

        # If we're using a 32-bit subregister for the loop counter (e.g. r12d)
        # update the register map for the loop variable so subsequent uses of
        # the variable inside the generated block will reference the same
        # sized register (avoids falling back to ebx/ecx or mismatched names).
        if loop_reg != internal_reg:
            # Overwrite mapping to point to the subregister (r12d, r13d, etc.)
            self.register_map[var] = loop_reg
            self.register_map[var.lower()] = loop_reg

        self.output.append(f"    mov {loop_reg}, {start}")
        self.output.append(f"{label_start}:")
        self.output.append(f"    cmp {loop_reg}, {end}")
        # Use jge (jump if greater or equal) so the loop does not skip the
        # final iteration when the loop variable equals the end value.
        self.output.append(f"    jge {label_end}")

        self.generate_block([TokenType.ENDFOR])

        self.output.append(f"{label_continue}:")
        self.output.append(f"    inc {loop_reg}")
        self.output.append(f"    jmp {label_start}")
        self.output.append(f"{label_end}:")
        
        self.loop_stack.pop()
        
        # free mapping (remove both original and lowercase keys)
        if var in self.register_map:
            del self.register_map[var]
        if var.lower() in self.register_map:
            del self.register_map[var.lower()]


        # emit end marker
        end_line = self.current_token().line if self.current_token() else start_line
        self.output.append(f"; __GEN_END__ {block_id} {end_line}")

        if self.current_token() and self.current_token().type == TokenType.ENDFOR:
            self.advance()
    
    def generate_while(self):
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()

        # Expect: WHILE <operand> <comparison-op> <number|operand>
        var, var_token = self.parse_operand()
        if not var or not var_token:
            raise SyntaxError(f"Line {var_token.line if var_token else '?'}: Expected identifier, register or memory operand after 'while'")

        op = self.current_token()
        if not op or op.type not in [TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE]:
            raise SyntaxError(f"Line {op.line if op else '?'}: Expected comparison operator after '{var}' in while-statement")
        self.advance()

        rhs_token = self.current_token()
        if not rhs_token:
            raise SyntaxError(f"Line {op.line if op else '?'}: Expected value after comparison in while-statement")
        if rhs_token.type == TokenType.NUMBER:
            rhs_val = rhs_token.value
            self.advance()
            rhs_info = rhs_token
        else:
            rhs_val, rhs_info = self.parse_operand()
        self.skip_newlines()
        
        label_start = self.get_label()
        label_end = self.get_label()
        label_continue = self.get_label()

        self.loop_stack.append({
            'break': label_end,
            'continue': label_continue
        })

        self.output.append(f"{label_start}:")
        self.output.append(f"{label_continue}:")

        # If both sides are numeric, evaluate condition at compile-time.
        cmp_emitted = False
        if var_token.type == TokenType.NUMBER and (rhs_info and rhs_info.type == TokenType.NUMBER):
            a = int(var)
            b = int(rhs_val)
            cond_map = {
                TokenType.EQ: (a == b), TokenType.NE: (a != b),
                TokenType.LT: (a < b), TokenType.GT: (a > b),
                TokenType.LE: (a <= b), TokenType.GE: (a >= b)
            }
            if not cond_map.get(op.type, False):
                # condition false => jump to end immediately
                self.output.append(f"    jmp {label_end}")
        else:
            # ensure left operand is a register/memory for valid cmp
            if var_token.type == TokenType.NUMBER:
                left = rhs_val
                if rhs_info and rhs_info.type == TokenType.REGISTER:
                    left = self.remap_reg(left)
                right = var
            else:
                left = var
                if var_token.type == TokenType.REGISTER:
                    left = self.remap_reg(left)
                right = rhs_val

            self.output.append(f"    cmp {left}, {right}")
            cmp_emitted = True

        jump_map = {
            TokenType.EQ: 'jne', TokenType.NE: 'je',
            TokenType.LT: 'jge', TokenType.GT: 'jle',
            TokenType.LE: 'jg', TokenType.GE: 'jl'
        }
        
        try:
            jm = jump_map[op.type]
        except KeyError:
            raise SyntaxError(f"Line {op.line}: Unsupported comparison operator '{op.value}' in while-statement")
        # Only emit the conditional jump if we actually emitted a cmp; for
        # constant-true loops we don't want a premature conditional branch.
        if cmp_emitted:
            self.output.append(f"    {jm} {label_end}")
        self.generate_block([TokenType.ENDWHILE])
        
        self.output.append(f"    jmp {label_start}")
        self.output.append(f"{label_end}:")
        
        self.loop_stack.pop()
        

        # emit end marker
        end_line = self.current_token().line if self.current_token() else start_line
        self.output.append(f"; __GEN_END__ {block_id} {end_line}")

        if self.current_token() and self.current_token().type == TokenType.ENDWHILE:
            self.advance()
    
    def generate_function(self):
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()
        func_name = self.current_token().value
        self.advance()

        # Parse optional parameter list: func name (a, b, c)
        params = []
        if self.current_token() and self.current_token().type == TokenType.LPAREN:
            # consume '('
            self.advance()
            while self.current_token() and self.current_token().type != TokenType.RPAREN:
                if self.current_token().type == TokenType.IDENTIFIER:
                    params.append(self.current_token().value)
                    self.advance()
                elif self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    # skip unexpected tokens
                    self.advance()
            # consume ')'
            if self.current_token() and self.current_token().type == TokenType.RPAREN:
                self.advance()

        self.skip_newlines()
        
        self.current_function = func_name
        self.functions[func_name] = {
            'start': len(self.output),
            'code': [],
            'params': params
        }

        # Emit function label and prologue according to target bitness
        if self.bits == 64:
            self.output.append(f"\n{func_name}:")
            self.output.append("    push rbp")
            self.output.append("    mov rbp, rsp")

            # Map incoming parameters (RCX, RDX, R8, R9) to internal callee-saved regs
            reg_map = ['rcx', 'rdx', 'r8', 'r9']
            for i, p in enumerate(params):
                internal = self.allocate_reg_for(p)
                if i < len(reg_map):
                    self.output.append(f"    mov {internal}, {reg_map[i]}")
                else:
                    # For simplicity, parameters beyond 4 are not supported yet.
                    self.output.append(f"    ; WARNING: parameter '{p}' passed on stack not supported")
        else:
            # 32-bit: prefix user function names with '_' to match C/Win decorations
            self.output.append(f"\n_{func_name}:")
            self.output.append("    push ebp")
            self.output.append("    mov ebp, esp")

            # Load parameters from the stack [ebp+8], [ebp+12], ... into internal regs
            for i, p in enumerate(params):
                internal = self.allocate_reg_for(p)
                offset = 8 + 4 * i
                self.output.append(f"    mov {internal}, dword [ebp+{offset}]")

        self.generate_block([TokenType.ENDFUNC])

        # function epilogue depends on bitness
        if self.bits == 64:
            self.output.append("    pop rbp")
        else:
            self.output.append("    pop ebp")
        self.output.append("    ret")
        

        # emit end marker
        end_line = self.current_token().line if self.current_token() else start_line
        self.output.append(f"; __GEN_END__ {block_id} {end_line}")

        if self.current_token() and self.current_token().type == TokenType.ENDFUNC:
            self.advance()

        self.current_function = None
    
    def generate_return(self):
        self.advance()
        if self.bits == 64:
            self.output.append("    pop rbp")
        else:
            self.output.append("    pop ebp")
        self.output.append("    ret")
    
    def generate_break(self):
        if not self.loop_stack:
            raise SyntaxError(f"Line {self.current_token().line}: 'break' outside loop")
        self.output.append(f"    jmp {self.loop_stack[-1]['break']}")
        self.advance()
    
    def generate_continue(self):
        if not self.loop_stack:
            raise SyntaxError(f"Line {self.current_token().line}: 'continue' outside loop")
        self.output.append(f"    jmp {self.loop_stack[-1]['continue']}")
        self.advance()
    
    def generate_block(self, end_tokens):
        while self.current_token() and self.current_token().type not in end_tokens:
            token = self.current_token()
            
            if token.type == TokenType.IF:
                self.generate_if()
            elif token.type == TokenType.FOR:
                self.generate_for()
            elif token.type == TokenType.WHILE:
                self.generate_while()
            elif token.type == TokenType.FUNC:
                self.generate_function()
            elif token.type == TokenType.CALL:
                self.generate_call()
            elif token.type == TokenType.RETURN:
                self.generate_return()
            elif token.type == TokenType.BREAK:
                self.generate_break()
            elif token.type == TokenType.CONTINUE:
                self.generate_continue()
            elif token.type == TokenType.ASM_LINE:
                # Remap register names inside raw ASM lines so that loop
                # variables previously bound to callee-saved registers are
                # used consistently in the emitted assembly.
                self.output.append(self.remap_asm_line(token.value))
                self.advance()
            elif token.type == TokenType.INCLUDE:
                # Skip here as well; original source will be rewritten to
                # reference the generated file path by the compiler build step.
                self.advance()
            elif token.type == TokenType.NEWLINE:
                self.advance()
            elif token.type == TokenType.EOF:
                break
            else:
                self.advance()
    
    def generate_call(self):
        # capture start line (the CALL token)
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()

        func_name = self.current_token().value
        self.advance()

        args = []

        # Support two call syntaxes: call foo a, b  OR call foo(a, b)
        if self.current_token() and self.current_token().type == TokenType.LPAREN:
            # consume '('
            self.advance()
            while self.current_token() and self.current_token().type != TokenType.RPAREN:
                if self.current_token().type in [TokenType.STRING, TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.REGISTER]:
                    args.append(self.current_token())
                    self.advance()
                elif self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    self.advance()
            # consume ')'
            if self.current_token() and self.current_token().type == TokenType.RPAREN:
                self.advance()
        else:
            while self.current_token() and self.current_token().type in [TokenType.STRING, TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.REGISTER]:
                args.append(self.current_token())
                self.advance()
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()

        self.stdlib_used.add(func_name)

        if func_name == 'print':
            self.generate_print(args)
        elif func_name == 'println':
            self.generate_print(args)
            if self.bits == 64:
                self.output.append("    lea rcx, [rel _newline_str]")
                self.output.append("    call _print_string")
            else:
                # push string pointer and call (cdecl-like)
                self.output.append("    push dword _newline_str")
                self.output.append("    call _print_string")
                self.output.append("    add esp, 4")
            self.stdlib_used.add('print')
        elif func_name == 'scan':
            self.generate_scan(args)
        elif func_name == 'scanint':
            self.generate_scanint(args)
        elif func_name in ['strlen','strcpy','strcmp','strcat','abs','min','max','pow','arraysum','arrayfill','arraycopy','memset','memcpy','rand','sleep']:
            self.generate_stdlib_call(func_name, args)
        else:
            # User-defined function call: on x64 move up to 4 args into RCX,RDX,R8,R9
            # on x86 push args (right-to-left) and call _func
            if args:
                arg_str = ', '.join(arg.value for arg in args)
                self.output.append(f"    ; Call {func_name} with args: {arg_str}")
            if self.bits == 64:
                reg_map = ['rcx', 'rdx', 'r8', 'r9']
                for i, arg in enumerate(args[:4]):
                    if arg.type == TokenType.STRING:
                        str_label = f"_str_{self.string_counter}"
                        self.string_counter += 1
                        escaped_str = arg.value.replace('`', '\\`')
                        self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                        self.output.append(f"    lea {reg_map[i]}, [rel {str_label}]")
                    elif arg.type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
                        val = arg.value
                        if arg.type in [TokenType.REGISTER, TokenType.IDENTIFIER]:
                            val = self.remap_reg(arg.value)
                        self.output.append(f"    mov {reg_map[i]}, {val}")

                self.output.append(f"    call {func_name}")
            else:
                # 32-bit: push args right-to-left
                for arg in reversed(args):
                    if arg.type == TokenType.STRING:
                        str_label = f"_str_{self.string_counter}"
                        self.string_counter += 1
                        escaped_str = arg.value.replace('`', '\\`')
                        self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                        self.output.append(f"    push dword {str_label}")
                    elif arg.type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
                        val = arg.value
                        if arg.type in [TokenType.REGISTER, TokenType.IDENTIFIER]:
                            val = self.remap_reg(arg.value)
                        self.output.append(f"    push {val}")

                # call with underscore prefix for user functions on x86
                self.output.append(f"    call _{func_name}")
                if args:
                    self.output.append(f"    add esp, {4 * len(args)}")

        # emit end marker for this call
        end_line = self.current_token().line if self.current_token() else start_line
        self.output.append(f"; __GEN_END__ {block_id} {end_line}")
    
    def generate_print(self, args):
        if not args:
            return
        
        arg = args[0]
        
        if self.bits == 64:
            if arg.type == TokenType.STRING:
                str_label = f"_str_{self.string_counter}"
                self.string_counter += 1
                escaped_str = arg.value.replace('`', '\\`')
                self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                self.output.append(f"    lea rcx, [rel {str_label}]")
                self.output.append(f"    call _print_string")
            elif arg.type in [TokenType.REGISTER, TokenType.IDENTIFIER]:
                val = self.remap_reg(arg.value)
                self.output.append(f"    mov rcx, {val}")
                self.output.append(f"    call _print_number")
            elif arg.type == TokenType.NUMBER:
                self.output.append(f"    mov rcx, {arg.value}")
                self.output.append(f"    call _print_number")
        else:
            # 32-bit: push arguments and call cdecl-style
            if arg.type == TokenType.STRING:
                str_label = f"_str_{self.string_counter}"
                self.string_counter += 1
                escaped_str = arg.value.replace('`', '\\`')
                self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                self.output.append(f"    push dword {str_label}")
                self.output.append(f"    call _print_string")
                self.output.append(f"    add esp, 4")
            elif arg.type in [TokenType.REGISTER, TokenType.IDENTIFIER]:
                val = self.remap_reg(arg.value)
                self.output.append(f"    push {val}")
                self.output.append(f"    call _print_number")
                self.output.append(f"    add esp, 4")
            elif arg.type == TokenType.NUMBER:
                self.output.append(f"    push {arg.value}")
                self.output.append(f"    call _print_number")
                self.output.append(f"    add esp, 4")
    
    def generate_scan(self, args):
        if not args:
            return
        buffer = args[0].value
        buffer_size = args[1].value if len(args) > 1 else "256"
        if self.bits == 64:
            self.output.append(f"    lea rcx, [rel {buffer}]")
            self.output.append(f"    mov rdx, {buffer_size}")
            self.output.append(f"    call _scan_string")
        else:
            # push size then buffer pointer
            self.output.append(f"    push {buffer_size}")
            self.output.append(f"    push dword {buffer}")
            self.output.append(f"    call _scan_string")
            self.output.append(f"    add esp, 8")
    
    def generate_scanint(self, args):
        if not args:
            return
        var = args[0].value
        if self.bits == 64:
            self.output.append(f"    lea rcx, [rel {var}]")
            self.output.append(f"    call _scanint")
        else:
            self.output.append(f"    push dword {var}")
            self.output.append(f"    call _scanint")
            self.output.append(f"    add esp, 4")
    
    def generate_stdlib_call(self, func_name, args):
        # Support both x64 (register) and x86 (stack push) argument passing
        if self.bits == 64:
            # Map arguments to registers (Windows x64 calling convention)
            reg_map = ['rcx', 'rdx', 'r8', 'r9']
            for i, arg in enumerate(args[:4]):
                if i < len(reg_map):
                    if arg.type == TokenType.STRING:
                        str_label = f"_str_{self.string_counter}"
                        self.string_counter += 1
                        escaped_str = arg.value.replace('`', '\\`')
                        self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                        self.output.append(f"    lea {reg_map[i]}, [rel {str_label}]")
                    elif arg.type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
                        val = arg.value
                        if arg.type in [TokenType.REGISTER, TokenType.IDENTIFIER]:
                            val = self.remap_reg(arg.value)
                        self.output.append(f"    mov {reg_map[i]}, {val}")
            self.output.append(f"    call _{func_name}")
        else:
            # 32-bit: push args right-to-left and call underscore-prefixed name
            for arg in reversed(args):
                if arg.type == TokenType.STRING:
                    str_label = f"_str_{self.string_counter}"
                    self.string_counter += 1
                    escaped_str = arg.value.replace('`', '\\`')
                    self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                    self.output.append(f"    push dword {str_label}")
                elif arg.type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
                    val = arg.value
                    if arg.type in [TokenType.REGISTER, TokenType.IDENTIFIER]:
                        val = self.remap_reg(arg.value)
                    self.output.append(f"    push {val}")
            self.output.append(f"    call _{func_name}")
            if args:
                self.output.append(f"    add esp, {4 * len(args)}")
