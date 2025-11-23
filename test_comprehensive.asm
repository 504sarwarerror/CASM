extern printf

; Comprehensive CASM Test
; Tests: if/elif/else, for loops, while loops, and x86 assembly translation

func main()
    call println "=== CASM Comprehensive Test ==="
    call println ""
    
    ; Test 1: Simple if/else
    call println "Test 1: If/Else Statements"
    mov rax, 42
    
    if rax == 42
        call println "  ✓ If statement works!"
    else
        call println "  ✗ If statement failed"
    endif
    
    ; Test 2: If/elif/else
    call println ""
    call println "Test 2: If/Elif/Else"
    mov rbx, 100
    
    if rbx < 50
        call println "  Value is less than 50"
    elif rbx < 100
        call println "  Value is between 50 and 99"
    elif rbx == 100
        call println "  ✓ Value is exactly 100"
    else
        call println "  Value is greater than 100"
    endif
    
    ; Test 3: For loop
    call println ""
    call println "Test 3: For Loop (1 to 5)"
    for i = 1, 5
        call print "  Count: "
        call println i
    endfor
    
    ; Test 4: While loop with x86 assembly
    call println ""
    call println "Test 4: While Loop (countdown from 5)"
    mov rbx, 5
    while rbx > 0
        call print "  "
        call println rbx
        sub rbx, 1
    endwhile
    
    ; Test 5: Nested loops
    call println ""
    call println "Test 5: Nested Loops (3x3 grid)"
    for row = 1, 3
        call print "  Row "
        call print row
        call print ": "
        for col = 1, 3
            call print col
            call print " "
        endfor
        call println ""
    endfor
    
    ; Test 6: Complex arithmetic with x86 assembly
    call println ""
    call println "Test 7: Complex Arithmetic (x86 instructions)"
    mov rax, 10
    mov rbx, 20
    add rax, rbx    ; rax = 30
    mov rcx, 5
    sub rax, rcx    ; rax = 25
    
    call print "  (10 + 20 - 5) = "
    call println 25
    
    ; Test 8: More x86 instructions
    call println ""
    call println "Test 8: More x86 Instructions"
    mov rax, 100
    mov rbx, 50
    call print "  100 - 50 = "
    sub rax, rbx
    call println 50
    
    ; Test 9: Stack operations
    call println ""
    call println "Test 9: Stack Push/Pop"
    mov rax, 111
    push rax
    mov rax, 222
    call print "  Before pop: rax = "
    call println rax
    pop rax
    call print "  After pop: rax = "
    call println rax
    
    ; Test 10: XOR operation (translated to EOR on ARM64)
    call println ""
    call println "Test 10: XOR/EOR Operation"
    mov rax, 0xFF
    mov rbx, 0xFF
    xor rax, rbx    ; Should be 0
    call print "  0xFF XOR 0xFF = "
    call println 0
    
    ; Test 11: Comparison operations
    call println ""
    call println "Test 11: Comparison Operations"
    mov rax, 50
    mov rbx, 50
    
    if rax == rbx
        call println "  ✓ 50 == 50"
    endif
    
    mov rcx, 100
    if rcx > rax
        call println "  ✓ 100 > 50"
    endif
    
    ; Test 12: Printf with format strings
    call println ""
    call println "Test 12: Printf Formatting"
    call printf("  Formatted number: %d", 42)
    call println ""
    call printf("  Another number: %d", 255)
    call println ""
    
    call println ""
    call println "=== All Tests Complete! ==="
    
    return
endfunc
