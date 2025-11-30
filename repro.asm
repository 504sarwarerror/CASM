bits 64

func main()
    ; Call a function with 7 arguments
    ; Args 1-4 go to rcx, rdx, r8, r9
    ; Args 5-7 should go to [rsp+32], [rsp+40], [rsp+48]
    call my_func(1, 2, 3, 4, 5, 6, 7)
    return 0
endfunc

func my_func(a, b, c, d, e, f, g)
    return 0
endfunc
