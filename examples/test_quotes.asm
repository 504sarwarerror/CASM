; Test single quote string support
func test_quotes
    if cl == '"'
        inc rbx
        mov r12, rbx
        jmp .findCloseQuote
    endif
    
    if cl == "'"
        inc rbx
        mov r12, rbx
        jmp .findCloseSingleQuote
    endif
    
    inc rbx
    jmp .findOpenQuote
    
.findCloseQuote:
    mov cl, byte [rbx]
    if cl == '"'
        mov r13, rbx
        jmp .replaceString
    endif
    inc rbx
    jmp .findCloseQuote

.findCloseSingleQuote:
    mov cl, byte [rbx]
    if cl == "'"
        mov r13, rbx
        jmp .replaceString
    endif
    inc rbx
    jmp .findCloseSingleQuote
    
.replaceString:
    return
endfunc
