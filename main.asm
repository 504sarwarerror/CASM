bits 64
default rel

%include "avatar.asm"  
%include "camera.asm"

SDL_INIT_VIDEO equ 0x00000020
SDL_WINDOW_SHOWN equ 0x00000004
SDL_WINDOWPOS_CENTERED equ 0x2FFF0000
SDL_RENDERER_SOFTWARE equ 0x00000001
SDL_QUIT equ 0x100
SDL_KEYDOWN equ 0x300
SDL_KEYUP equ 0x301
IMG_INIT_PNG equ 0x00000002

extern SDL_Init
extern SDL_CreateWindow
extern SDL_CreateRenderer
extern SDL_SetRenderDrawColor
extern SDL_RenderClear
extern SDL_RenderCopy
extern SDL_RenderPresent
extern SDL_PollEvent
extern SDL_Delay
extern SDL_DestroyRenderer
extern SDL_DestroyWindow
extern SDL_Quit
extern IMG_Init
extern IMG_Quit

section .data
    window_title db "NET 2027", 0

section .bss
    window resq 1
    renderer resq 1
    event resb 56
    running resb 1

section .text
global main

main:
    push rbp
    mov rbp, rsp
    and rsp, -16
    sub rsp, 48

    mov ecx, SDL_INIT_VIDEO
    call SDL_Init
    if eax != 0
        jmp .error
    endif

    mov ecx, IMG_INIT_PNG
    call IMG_Init
    if eax == 0
        jmp .error
    endif

    lea rcx, [window_title]
    mov edx, SDL_WINDOWPOS_CENTERED
    mov r8d, SDL_WINDOWPOS_CENTERED
    mov r9d, 800
    mov dword [rsp+32], 600
    mov dword [rsp+40], SDL_WINDOW_SHOWN
    call SDL_CreateWindow
    if rax == 0
        jmp .error
    endif
    mov [window], rax

    mov rcx, [window]
    mov rdx, -1
    mov r8d, SDL_RENDERER_SOFTWARE
    call SDL_CreateRenderer
    if rax == 0
        jmp .error
    endif
    mov [renderer], rax


    mov rcx, [renderer]
    call avatar_load
    call camera_init

    mov byte [running], 1

    while byte [running] == 1
        lea rcx, [event]
        call SDL_PollEvent

        if eax != 0
            mov eax, [event]

            if eax == SDL_QUIT
                mov byte [running], 0
                continue
            endif

            if eax == SDL_KEYDOWN
                mov edi, [event + 16]
                call avatar_update
            endif

            if eax == SDL_KEYUP
                mov edi, 0
                call avatar_update
            endif
        endif 

        mov rcx, [renderer]
        xor edx, edx
        xor r8d, r8d
        xor r9d, r9d
        mov dword [rsp+32], 255
        call SDL_SetRenderDrawColor

        mov rcx, [renderer]
        call SDL_RenderClear

        call avatar_idle

        mov rdi, [renderer]
        call avatar_draw
        call render_camera


        mov rcx, [renderer]
        call SDL_RenderPresent
    endwhile
.cleanup:
    call avatar_free

    mov rcx, [renderer]
    if rcx != 0
        call SDL_DestroyRenderer
    endif

    mov rcx, [window]
    if rcx != 0
        call SDL_DestroyWindow
    endif

    call IMG_Quit
    call SDL_Quit

    xor eax, eax
    mov rsp, rbp
    pop rbp
    ret
.error:
    call IMG_Quit
    call SDL_Quit
    mov eax, 1
    mov rsp, rbp
    pop rbp
    ret
