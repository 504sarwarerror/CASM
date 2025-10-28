bits 64
default rel

extern SDL_CreateTextureFromSurface
extern SDL_FreeSurface
extern SDL_RenderCopy
extern SDL_DestroyTexture
extern IMG_Load

section .data
    avatar_Bpath db "assets/avatar/AVATAR1.png", 0
    avatar_B1path db "assets/avatar/AVATAR2.png", 0
    avatar_R1path db "assets/avatar/AVATAR3.png", 0
    avatar_R2path db "assets/avatar/AVATAR4.png", 0
    avatar_L1path db "assets/avatar/AVATAR5.png", 0
    avatar_L2path db "assets/avatar/AVATAR6.png", 0
    move_speed dd 6
    avatar_r dd 0
    avatar_l dd 0
    avatar_b dd 0

section .bss
    avatar_Btexture resq 1
    avatar_B1texture resq 1
    avatar_R1texture resq 1
    avatar_R2texture resq 1
    avatar_L1texture resq 1
    avatar_L2texture resq 1
    avatar_x resd 1
    avatar_y resd 1
    avatar_rect resb 16
    avatar_frame resd 1


section .text
global avatar_load
global avatar_update
global avatar_draw
global avatar_free
global avatar_idle

macro LOAD_IMAGE 2
    lea rcx, [%1]                
    call IMG_Load               
    if rax == 0
        jmp .fail
    endif
    mov r15, rax
    mov rcx, rbx               
    mov rdx, r15                 
    call SDL_CreateTextureFromSurface
    mov [%2], rax                
    mov rcx, r15
    call SDL_FreeSurface         
endmacro

macro DRAW_IMAGE 3
    if [%1] == 1                  
        mov eax, [avatar_frame]    
        if eax == 0
            mov rcx, rdi           
            mov rdx, [%2]         
            xor r8, r8
            lea r9, [avatar_rect]
            call SDL_RenderCopy
        endif
        if eax == 1
            mov rcx, rdi
            mov rdx, [%3]         
            xor r8, r8
            lea r9, [avatar_rect]
            call SDL_RenderCopy
        endif
    endif
endmacro

avatar_load:
    push rbp
    mov rbp, rsp
    sub rsp, 32

    mov rbx, rcx

    LOAD_IMAGE avatar_Bpath, avatar_Btexture
    LOAD_IMAGE avatar_B1path, avatar_B1texture
    LOAD_IMAGE avatar_R1path, avatar_R1texture
    LOAD_IMAGE avatar_R2path, avatar_R2texture
    LOAD_IMAGE avatar_L1path, avatar_L1texture
    LOAD_IMAGE avatar_L2path, avatar_L2texture

    mov dword [avatar_x], 350
    mov dword [avatar_y], 250
    jmp .done

.fail:
    xor eax, eax
.done:
    leave
    ret

avatar_update:
    push rbp
    mov rbp, rsp

    mov eax, edi          

    if eax == 0
        mov dword [avatar_r], 0
        mov dword [avatar_b], 1
        mov dword [avatar_l], 0
        mov dword [avatar_frame], 0
        jmp .done
    endif

    if eax == 80
        mov dword [avatar_b], 0
        mov dword [avatar_r], 0
        mov dword [avatar_l], 1

        mov eax, [avatar_x]
        sub eax, [move_speed]
        if eax < 0
            xor eax, eax
        endif
        mov [avatar_x], eax

        mov eax, [avatar_frame]
        inc eax
        cmp eax, 2
        jne .store_frame_l
        xor eax, eax
    .store_frame_l:
        mov [avatar_frame], eax
    endif

    if eax == 79
        mov dword [avatar_b], 0
        mov dword [avatar_r], 1
        mov dword [avatar_l], 0

        mov eax, [avatar_x]
        add eax, [move_speed]
        if eax > 700
            mov eax, 700
        endif
        mov [avatar_x], eax

        mov eax, [avatar_frame]
        inc eax
        cmp eax, 2
        jne .store_frame_r
        xor eax, eax
    .store_frame_r:
        mov [avatar_frame], eax
    endif

.done:
    leave
    ret


avatar_draw:
    push rbp
    mov rbp, rsp

    mov eax, [avatar_x]
    mov [avatar_rect + 0], eax
    mov eax, [avatar_y]
    mov [avatar_rect + 4], eax
    mov dword [avatar_rect + 8], 50
    mov dword [avatar_rect + 12], 50

    DRAW_IMAGE avatar_r, avatar_R1texture, avatar_R2texture
    DRAW_IMAGE avatar_l, avatar_L1texture, avatar_L2texture
    
    if [avatar_b] == 1
        mov rcx, rdi
        mov rdx, [avatar_Btexture]
        xor r8, r8
        lea r9, [avatar_rect]
        call SDL_RenderCopy
    endif

    leave
    ret

avatar_free:
    push rbp
    mov rbp, rsp
    mov rcx, [avatar_Btexture]
    if rcx != 0
        call SDL_DestroyTexture
    endif
    leave
    ret
