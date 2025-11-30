; Simple test for lean syntax that actually compiles
; This demonstrates the * prefix for lea instructions

section .data
    message db "Testing lean syntax", 0
    buffer times 256 db 0

section .text
    global main
    extern ExitProcess

main:
    ; Without lean syntax - this would normally require:
    ; lea rcx, [message]
    ; But we can write it more explicitly with *:
    
    ; Test: Use * to explicitly request lea
    ; This is equivalent to: lea rcx, [message]
    ; (Note: print function expects a pointer, so * makes sense here)
    call println(*message)
    
    ; Test: Regular value without * uses mov
    ; This generates: mov rcx, 0
    call ExitProcess(0)
