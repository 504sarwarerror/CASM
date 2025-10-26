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
        self._reg_pool = ['r12', 'r13', 'r14', 'r15', 'rbx']
    
    def generate(self):
        while self.pos < len(self.tokens):
            token = self.current_token()
            
            if token.type == TokenType.EOF:
                break
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
            else:
                self.advance()
        
        return '\n'.join(self.output), self.data_section, self.stdlib_used
    
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
        return self.register_map.get(name, name)

    def allocate_reg_for(self, orig_name):
        # find a free callee-saved register from the pool
        for r in self._reg_pool:
            if r not in self.register_map.values():
                self.register_map[orig_name] = r
                return r
        # fallback: reuse rbx
        self.register_map[orig_name] = 'rbx'
        return 'rbx'
    
    def skip_newlines(self):
        while self.current_token() and self.current_token().type == TokenType.NEWLINE:
            self.advance()
    
    def generate_if(self):
        # mark the start line of this high-level block so we can replace it
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        # emit start marker
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()
        
        # Expect: IF <identifier|register> <comparison-op> <number|identifier|register>
        var_token = self.current_token()
        if not var_token or var_token.type not in [TokenType.IDENTIFIER, TokenType.REGISTER]:
            raise SyntaxError(f"Line {var_token.line if var_token else '?'}: Expected identifier or register after 'if'")
        var = var_token.value
        self.advance()
        
        op = self.current_token()
        if not op or op.type not in [TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE]:
            raise SyntaxError(f"Line {op.line if op else '?'}: Expected comparison operator after '{var}' in if-statement")
        self.advance()
        
        value_token = self.current_token()
        if not value_token or value_token.type not in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
            raise SyntaxError(f"Line {value_token.line if value_token else '?'}: Expected number, identifier or register after comparison in if-statement")
        value = value_token.value
        self.advance()
        self.skip_newlines()
        
        label_next = self.get_label()
        label_end = self.get_label()

        var_m = self.remap_reg(var)
        self.output.append(f"    cmp {var_m}, {value}")

        jump_map = {
            TokenType.EQ: 'jne', TokenType.NE: 'je',
            TokenType.LT: 'jge', TokenType.GT: 'jle',
            TokenType.LE: 'jg', TokenType.GE: 'jl'
        }
        
        try:
            jm = jump_map[op.type]
        except KeyError:
            raise SyntaxError(f"Line {op.line}: Unsupported comparison operator '{op.value}' in if-statement")
        self.output.append(f"    {jm} {label_next}")
        self.generate_block([TokenType.ELIF, TokenType.ELSE, TokenType.ENDIF])
        
        has_else = False
        while self.current_token() and self.current_token().type in [TokenType.ELIF, TokenType.ELSE]:
            if self.current_token().type == TokenType.ELIF:
                self.output.append(f"    jmp {label_end}")
                self.output.append(f"{label_next}:")
                label_next = self.get_label()
                
                self.advance()
                # ELIF expects the same pattern as IF
                var_token = self.current_token()
                if not var_token or var_token.type not in [TokenType.IDENTIFIER, TokenType.REGISTER]:
                    raise SyntaxError(f"Line {var_token.line if var_token else '?'}: Expected identifier or register after 'elif'")
                var = var_token.value
                self.advance()
                op = self.current_token()
                if not op or op.type not in [TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE]:
                    raise SyntaxError(f"Line {op.line if op else '?'}: Expected comparison operator after '{var}' in elif-statement")
                self.advance()
                value_token = self.current_token()
                if not value_token or value_token.type not in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
                    raise SyntaxError(f"Line {value_token.line if value_token else '?'}: Expected number, identifier or register after comparison in elif-statement")
                value = value_token.value
                self.advance()
                self.skip_newlines()
                var_m = self.remap_reg(var)
                self.output.append(f"    cmp {var_m}, {value}")
                try:
                    jm2 = jump_map[op.type]
                except KeyError:
                    raise SyntaxError(f"Line {op.line}: Unsupported comparison operator '{op.value}' in elif-statement")
                self.output.append(f"    {jm2} {label_next}")
                self.generate_block([TokenType.ELIF, TokenType.ELSE, TokenType.ENDIF])
                
            elif self.current_token().type == TokenType.ELSE:
                self.output.append(f"    jmp {label_end}")
                self.output.append(f"{label_next}:")
                has_else = True
                self.advance()
                self.skip_newlines()
                self.generate_block([TokenType.ENDIF])
                break
        
        if not has_else:
            self.output.append(f"{label_next}:")
        self.output.append(f"{label_end}:")

        # mark end line
        end_line = self.current_token().line if self.current_token() else start_line
        # emit end marker

        if self.current_token() and self.current_token().type == TokenType.ENDIF:
            self.advance()
    
    def generate_for(self):
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()
        
        var = self.current_token().value
        self.advance()
        self.advance()  # =
        
        start = self.current_token().value
        self.advance()
        self.advance()  # ,
        
        end = self.current_token().value
        self.advance()
        self.skip_newlines()
        
        # allocate a callee-saved register for the loop variable to survive calls
        internal_reg = self.allocate_reg_for(var)

        label_start = self.get_label()
        label_end = self.get_label()
        label_continue = self.get_label()

        self.loop_stack.append({
            'break': label_end,
            'continue': label_continue
        })

        self.output.append(f"    mov {internal_reg}, {start}")
        self.output.append(f"{label_start}:")
        self.output.append(f"    cmp {internal_reg}, {end}")
        self.output.append(f"    jg {label_end}")

        self.generate_block([TokenType.ENDFOR])

        self.output.append(f"{label_continue}:")
        self.output.append(f"    inc {internal_reg}")
        self.output.append(f"    jmp {label_start}")
        self.output.append(f"{label_end}:")
        
        self.loop_stack.pop()
        
        # free mapping
        if var in self.register_map:
            del self.register_map[var]

        # emit end marker
        end_line = self.current_token().line if self.current_token() else start_line

        if self.current_token() and self.current_token().type == TokenType.ENDFOR:
            self.advance()
    
    def generate_while(self):
        start_line = self.current_token().line if self.current_token() else -1
        block_id = self.block_counter
        self.block_counter += 1
        self.output.append(f"; __GEN_START__ {block_id} {start_line}")
        self.advance()

        # Expect: WHILE <identifier|register> <comparison-op> <number|identifier|register>
        var_token = self.current_token()
        if not var_token or var_token.type not in [TokenType.IDENTIFIER, TokenType.REGISTER]:
            raise SyntaxError(f"Line {var_token.line if var_token else '?'}: Expected identifier or register after 'while'")
        var = var_token.value
        self.advance()

        op = self.current_token()
        if not op or op.type not in [TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE]:
            raise SyntaxError(f"Line {op.line if op else '?'}: Expected comparison operator after '{var}' in while-statement")
        self.advance()

        value_token = self.current_token()
        if not value_token or value_token.type not in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
            raise SyntaxError(f"Line {value_token.line if value_token else '?'}: Expected number, identifier or register after comparison in while-statement")
        value = value_token.value
        self.advance()
        self.skip_newlines()
        
        label_start = self.get_label()
        label_end = self.get_label()
        label_continue = self.get_label()

        self.loop_stack.append({
            'break': label_end,
            'continue': label_continue
        })

        var_m = self.remap_reg(var)
        self.output.append(f"{label_start}:")
        self.output.append(f"{label_continue}:")
        self.output.append(f"    cmp {var_m}, {value}")

        jump_map = {
            TokenType.EQ: 'jne', TokenType.NE: 'je',
            TokenType.LT: 'jge', TokenType.GT: 'jle',
            TokenType.LE: 'jg', TokenType.GE: 'jl'
        }
        
        try:
            jm = jump_map[op.type]
        except KeyError:
            raise SyntaxError(f"Line {op.line}: Unsupported comparison operator '{op.value}' in while-statement")
        self.output.append(f"    {jm} {label_end}")
        self.generate_block([TokenType.ENDWHILE])
        
        self.output.append(f"    jmp {label_start}")
        self.output.append(f"{label_end}:")
        
        self.loop_stack.pop()
        
        # emit end marker
        end_line = self.current_token().line if self.current_token() else start_line

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

        self.generate_block([TokenType.ENDFUNC])

        self.output.append("    pop rbp")
        self.output.append("    ret")
        
        # emit end marker
        end_line = self.current_token().line if self.current_token() else start_line

        if self.current_token() and self.current_token().type == TokenType.ENDFUNC:
            self.advance()

        self.current_function = None
    
    def generate_return(self):
        self.advance()
        self.output.append("    pop rbp")
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
                # See note above: skip raw ASM lines from the generated snippet.
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
            self.output.append("    lea rcx, [rel _newline_str]")
            self.output.append("    call _print_string")
            self.stdlib_used.add('print')
        elif func_name == 'scan':
            self.generate_scan(args)
        elif func_name == 'scanint':
            self.generate_scanint(args)
        elif func_name in ['strlen','strcpy','strcmp','strcat','abs','min','max','pow','arraysum','arrayfill','arraycopy','memset','memcpy','rand','sleep']:
            self.generate_stdlib_call(func_name, args)
        else:
            # User-defined function call: move up to 4 args into RCX,RDX,R8,R9 then call
            if args:
                arg_str = ', '.join(arg.value for arg in args)
                self.output.append(f"    ; Call {func_name} with args: {arg_str}")

            reg_map = ['rcx', 'rdx', 'r8', 'r9']
            for i, arg in enumerate(args[:4]):
                if arg.type == TokenType.STRING:
                    str_label = f"_str_{self.string_counter}"
                    self.string_counter += 1
                    escaped_str = arg.value.replace('`', '\\`')
                    self.data_section.append(f"{str_label} db `{escaped_str}`, 0")
                    self.output.append(f"    lea {reg_map[i]}, [rel {str_label}]")
                elif arg.type in [TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.REGISTER]:
                    self.output.append(f"    mov {reg_map[i]}, {arg.value}")

            self.output.append(f"    call {func_name}")

        # emit end marker for this call
        end_line = self.current_token().line if self.current_token() else start_line
    
    def generate_print(self, args):
        if not args:
            return
        
        arg = args[0]
        
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
    
    def generate_scan(self, args):
        if not args:
            return
        buffer = args[0].value
        buffer_size = args[1].value if len(args) > 1 else "256"
        self.output.append(f"    lea rcx, [rel {buffer}]")
        self.output.append(f"    mov rdx, {buffer_size}")
        self.output.append(f"    call _scan_string")
    
    def generate_scanint(self, args):
        if not args:
            return
        var = args[0].value
        self.output.append(f"    lea rcx, [rel {var}]")
        self.output.append(f"    call _scanint")
    
    def generate_stdlib_call(self, func_name, args):
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
                    self.output.append(f"    mov {reg_map[i]}, {arg.value}")
        
        self.output.append(f"    call _{func_name}")
