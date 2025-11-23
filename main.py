#!/usr/bin/env python3
import sys

sys.dont_write_bytecode = True

from utils.cli import CLI
from utils.syntax import Compiler
from src.builder import Builder


def main():
    config = CLI.parse_args(sys.argv)
    
    if config is None:
        CLI.print_usage()
        sys.exit(1)
    
    if config['help']:
        CLI.print_banner()
        CLI.print_usage()
        sys.exit(0)
    
    if config['verbose']:
        CLI.print_banner()
    
    compiler = Compiler(
        config['input_file'],
        config['output_file'],
        config['verbose'],
        target=config.get('target', 'windows'),
        arch=config.get('arch', 'x86_64')
    )
    
    if not compiler.compile():
        CLI.error("Compilation failed")
        sys.exit(1)
    
    output_file = compiler.get_output_file()
    
    if config['build']:

        builder = Builder(
            output_file,
            config['verbose'],
            target=config.get('target', 'windows'),
            linker_flags=config.get('ldflags', ''),
            debug=config.get('debug', False),
            arch=config.get('arch', 'x86_64')
        )
        
        if not builder.assemble_and_link():
            CLI.error("Build failed")
            sys.exit(1)
        
        if config['run']:
            print()
            if not builder.run_executable():
                CLI.error("Execution failed")
                sys.exit(1)
    
    sys.exit(0)

if __name__ == '__main__':
    main()