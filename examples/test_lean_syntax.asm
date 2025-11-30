; Test file for lean syntax with * prefix for lea instructions

section .data
    findData times 320 db 0
    bufferSize dd 256

section .text
    global main

main:
    ; Test 1: Basic lean syntax with memory operands
    ; This should generate: lea rcx, [rsp + 512]
    ;                       lea rdx, [findData]
    call FindFirstFileA(*[rsp + 512], *[findData])
    
    ; Test 2: Mixed usage - some with *, some without
    ; First arg uses lea, second uses mov
    call SomeFunction(*[bufferSize], 256)
    
    ; Test 3: Simple identifier with *
    ; This should generate: lea rcx, [findData]
    call ProcessData(*findData)
    
    ; Test 4: Without * (traditional syntax)
    ; This should generate: mov rcx, 0
    call ExitProcess(0)
    
    ; Test 5: Multiple * prefixed args
    call ThreeArgs(*[rsp + 100], *[rsp + 200], *[rsp + 300])
    
    ret
