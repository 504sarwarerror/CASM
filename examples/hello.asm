section .data
    msg1 db "Advanced Compiler Test", 0

section .bss
    user_input resb 256
    number resq 1
    array resq 10

section .text

call println "=========================================="
call println "ADVANCED ASSEMBLY COMPILER TEST"
call println "=========================================="
call println ""

; === TEST 1: Basic I/O ===
call println "TEST 1: Basic I/O"
call println "Hello from the compiler!"
call print "Your age: "
mov rax, 25
call println rax
call println ""

; === TEST 2: FOR loop ===
call println "TEST 2: FOR Loop (1 to 5)"
for rcx = 1, 5
    call print "  Count: "
    call println rcx
endfor
call println ""

; === TEST 3: IF/ELIF/ELSE ===
call println "TEST 3: IF/ELIF/ELSE"
mov rax, 10
if rax == 5
    call println "  Value is 5"
elif rax == 10
    call println "  Value is 10"
else
    call println "  Value is something else"
endif
call println ""

; === TEST 4: WHILE loop ===
call println "TEST 4: WHILE Loop"
mov rbx, 3
while rbx > 0
    call print "  Countdown: "
    call println rbx
    dec rbx
endwhile
call println ""

; === TEST 5: Nested loops with BREAK ===
call println "TEST 5: Nested loops with BREAK"
for rax = 1, 3
    call print "Outer: "
    call println rax
    for rbx = 1, 5
        if rbx == 3
            break
        endif
        call print "  Inner: "
        call println rbx
    endfor
endfor
call println ""

; === TEST 6: User function ===
call println "TEST 6: Custom Function"
func my_function
    call println "  Inside custom function!"
    return
endfunc

call my_function
call println ""

; === TEST 7: Standard library functions ===
call println "TEST 7: Math Functions"
call print "  abs(-42) = "
mov rcx, -42
call abs
call println rax

call print "  min(10, 20) = "
mov rcx, 10
mov rdx, 20
call min
call println rax

call print "  max(10, 20) = "
mov rcx, 10
mov rdx, 20
call max
call println rax
call println ""

call println "=========================================="
call println "ALL TESTS COMPLETED!"
call println "=========================================="