class CLI:
    @staticmethod
    def print_banner():
        print("=" * 60)
        print("  Advanced Assembly Compiler v2.0")
        print("  High-level constructs for NASM (Windows x64)")
        print("  With dynamic standard library injection")
        print("=" * 60)
        print()
    
    @staticmethod
    def print_usage():
        print("Usage: python compiler.py <input.asm> [options]")
        print()
        print("Options:")
        print("  -o <file>      Specify output file")
        print("  -e, --exe      Compile directly to .exe")
        print("  --build        Assemble and link to executable")
        print("  --target <t>   Target OS: windows (only 'windows' is supported)")
        print("  --run          Run after building")
        print("  -v, --verbose  Verbose output")
        print("  -h, --help     Show help")
        print()
        print("Examples:")
        print("  python compiler.py program.asm")
        print("  python compiler.py program.asm --build")
        print("  python compiler.py program.asm --exe --run")
        print("  python compiler.py program.asm -o output.asm -v")
        print()
        print("Supported high-level features:")
        print("  • if/elif/else/endif")
        print("  • for/endfor loops")
        print("  • while/endwhile loops")
        print("  • break/continue")
        print("  • func/endfunc")
        print("  • call with standard library functions")
        print()
        print("Standard library functions:")
        print("  I/O:     print, println, scan, scan_int")
        print("  String:  strlen, strcpy, strcmp, strcat")
        print("  Math:    abs, min, max, pow")
        print("  Array:   array_sum, array_fill, array_copy")
        print("  Memory:  memset, memcpy")
        print("  Other:   rand, sleep")
        print()
    
    @staticmethod
    def parse_args(args):
        if len(args) < 2:
            return None
        
        config = {
            'input_file': None,
            'output_file': None,
            'build': False,
            'exe': False,
            'run': False,
            'verbose': False,
            'target': 'windows',
            'help': False
        }
        
        i = 1
        while i < len(args):
            arg = args[i]
            
            if arg in ['-h', '--help']:
                config['help'] = True
                return config
            
            elif arg == '-o':
                if i + 1 < len(args):
                    config['output_file'] = args[i + 1]
                    i += 2
                else:
                    print("[!] Error: -o requires filename")
                    return None
            
            elif arg in ['-e', '--exe']:
                config['exe'] = True
                config['build'] = True
                i += 1

            elif arg == '--target':
                if i + 1 < len(args):
                    requested = args[i + 1].lower()
                    if requested != 'windows':
                        print(f"[!] Warning: only 'windows' target is supported. Forcing target to 'windows'.")
                    config['target'] = 'windows'
                    i += 2
                else:
                    print("[!] Error: --target requires a value (windows)")
                    return None
            
            elif arg == '--build':
                config['build'] = True
                i += 1
            
            elif arg == '--run':
                config['run'] = True
                config['build'] = True
                i += 1
            
            elif arg in ['-v', '--verbose']:
                config['verbose'] = True
                i += 1
            
            elif not arg.startswith('-'):
                if config['input_file'] is None:
                    config['input_file'] = arg
                i += 1
            
            else:
                print(f"[!] Unknown option: {arg}")
                return None
        
        if not config['input_file']:
            print("[!] Error: No input file specified")
            return None
        
        return config