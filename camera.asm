bits 64
default rel

section .data
    TILE_WIDTH equ 36
    TILE_HEIGHT equ 35
    MAP_WIDTH equ 3000
    MAP_HEIGHT equ 3000
    SCREEN_WIDTH equ 800
    SCREEN_HEIGHT equ 600

    camera_x dd 0
    camera_y dd 0
    player_x dd 0
    player_y dd 0

    grass_texture dq 0
    stone_texture dq 0
    water_texture dq 0
    wall_texture dq 0

    tilemap times MAP_WIDTH * MAP_HEIGHT db 0

    tile_rect:
    dd 0, 0, TILE_WIDTH, TILE_HEIGHT

    start_tile_x dd 0
    start_tile_y dd 0
    end_tile_x dd 0
    end_tile_y dd 0

    ; Texture file paths (adjust these to match your actual file names)
    grass_path db "/Users/sarwar/Desktop/NET/assets/avatar/AVATAR1.png", 0
    wall_path db "/Users/sarwar/Desktop/NET/assets/avatar/AVATAR1.png", 0
    stone_path db "/Users/sarwar/Desktop/NET/assets/avatar/AVATAR1.png", 0
    water_path db "/Users/sarwar/Desktop/NET/assets/avatar/AVATAR1.png", 0

section .bss

section .text
global camera_init
global render_camera
global camera_load_textures
global camera_free_textures

extern IMG_Load
extern SDL_CreateTextureFromSurface
extern SDL_FreeSurface
extern SDL_DestroyTexture
extern SDL_RenderCopy

; Load all textures
; Parameters: rcx = renderer pointer
camera_load_textures:
    push rbp
    mov rbp, rsp
    sub rsp, 48
    push rbx
    push r12
    
    mov r12, rcx  ; Save renderer
    
    ; Load grass texture
    lea rcx, [rel grass_path]
    call IMG_Load
    test rax, rax
    jz .error
    
    mov rbx, rax  ; Save surface
    mov rcx, r12  ; renderer
    mov rdx, rbx  ; surface
    call SDL_CreateTextureFromSurface
    mov [rel grass_texture], rax
    
    mov rcx, rbx
    call SDL_FreeSurface
    
    ; Load wall texture
    lea rcx, [rel wall_path]
    call IMG_Load
    test rax, rax
    jz .error
    
    mov rbx, rax
    mov rcx, r12
    mov rdx, rbx
    call SDL_CreateTextureFromSurface
    mov [rel wall_texture], rax
    
    mov rcx, rbx
    call SDL_FreeSurface
    
    ; Load stone texture (optional)
    lea rcx, [rel stone_path]
    call IMG_Load
    test rax, rax
    jz .skip_stone
    
    mov rbx, rax
    mov rcx, r12
    mov rdx, rbx
    call SDL_CreateTextureFromSurface
    mov [rel stone_texture], rax
    
    mov rcx, rbx
    call SDL_FreeSurface
    
.skip_stone:
    ; Load water texture (optional)
    lea rcx, [rel water_path]
    call IMG_Load
    test rax, rax
    jz .skip_water
    
    mov rbx, rax
    mov rcx, r12
    mov rdx, rbx
    call SDL_CreateTextureFromSurface
    mov [rel water_texture], rax
    
    mov rcx, rbx
    call SDL_FreeSurface
    
.skip_water:
    mov eax, 1  ; Success
    jmp .cleanup
    
.error:
    xor eax, eax  ; Failure
    
.cleanup:
    pop r12
    pop rbx
    add rsp, 48
    pop rbp
    ret

; Free all textures
camera_free_textures:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    
    mov rcx, [rel grass_texture]
    test rcx, rcx
    jz .check_wall
    call SDL_DestroyTexture
    mov qword [rel grass_texture], 0
    
.check_wall:
    mov rcx, [rel wall_texture]
    test rcx, rcx
    jz .check_stone
    call SDL_DestroyTexture
    mov qword [rel wall_texture], 0
    
.check_stone:
    mov rcx, [rel stone_texture]
    test rcx, rcx
    jz .check_water
    call SDL_DestroyTexture
    mov qword [rel stone_texture], 0
    
.check_water:
    mov rcx, [rel water_texture]
    test rcx, rcx
    jz .done
    call SDL_DestroyTexture
    mov qword [rel water_texture], 0
    
.done:
    add rsp, 32
    pop rbp
    ret

camera_init:
    push rbp
    mov rbp, rsp
    sub rsp, 32

    mov eax, [rel player_x]
    sub eax, SCREEN_WIDTH / 2
    if eax < 0
        xor eax, eax
    endif 

    mov ebx, MAP_WIDTH
    imul ebx, TILE_WIDTH
    sub ebx, SCREEN_WIDTH

    if eax > ebx
        mov eax, ebx
    endif

    mov [rel camera_x], eax

    mov eax, [rel player_y]
    sub eax, SCREEN_HEIGHT / 2
    if eax < 0
        xor eax, eax
    endif

    mov ebx, MAP_HEIGHT
    imul ebx, TILE_HEIGHT
    sub ebx, SCREEN_HEIGHT

    if eax > ebx
        mov eax, ebx
    endif

    mov [rel camera_y], eax
    
    add rsp, 32
    pop rbp
    ret

render_camera:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    push rbx
    push r12
    push r13
    push r14
    push r15
    
    ; Save renderer pointer (passed in rdi)
    mov r15, rdi

    mov eax, [rel camera_x]
    xor edx, edx
    mov ecx, TILE_WIDTH
    div ecx
    mov [rel start_tile_x], eax

    mov eax, [rel camera_y]
    xor edx, edx
    mov ecx, TILE_HEIGHT
    div ecx
    mov [rel start_tile_y], eax

    mov eax, SCREEN_WIDTH
    add eax, [rel camera_x]
    xor edx, edx
    mov ecx, TILE_WIDTH
    div ecx
    mov [rel end_tile_x], eax

    mov eax, SCREEN_HEIGHT
    add eax, [rel camera_y]
    xor edx, edx
    mov ecx, TILE_HEIGHT
    div ecx
    mov [rel end_tile_y], eax

    if [rel end_tile_x] > MAP_WIDTH
        mov dword [rel end_tile_x], MAP_WIDTH
    endif
    if [rel end_tile_y] > MAP_HEIGHT
        mov dword [rel end_tile_y], MAP_HEIGHT
    endif

    for ebx = [rel start_tile_y], [rel end_tile_y]
        for ecx = [rel start_tile_x], [rel end_tile_x]
            mov eax, ebx
            imul eax, MAP_WIDTH
            add eax, ecx
            lea r10, [rel tilemap]
            movzx r14d, byte [r10 + rax]

            mov eax, ecx
            imul eax, TILE_WIDTH
            sub eax, [rel camera_x]
            mov [rel tile_rect], eax

            mov eax, ebx
            imul eax, TILE_HEIGHT
            sub eax, [rel camera_y]
            mov [rel tile_rect + 4], eax

            mov dword [rel tile_rect + 8], TILE_WIDTH
            mov dword [rel tile_rect + 12], TILE_HEIGHT

            if r14d == 0
                mov rcx, r15
                mov rdx, [rel grass_texture]
                test rdx, rdx
                jz .skip_render_0
                xor r8, r8
                lea r9, [rel tile_rect]
                call SDL_RenderCopy
.skip_render_0:
            endif
            if r14d == 1
                mov rcx, r15
                mov rdx, [rel wall_texture]
                test rdx, rdx
                jz .skip_render_1
                xor r8, r8
                lea r9, [rel tile_rect]
                call SDL_RenderCopy
.skip_render_1:
            endif
        endfor
    endfor

    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    add rsp, 64
    pop rbp
    ret