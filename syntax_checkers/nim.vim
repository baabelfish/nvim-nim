" Mainly copied from https://github.com/zah/nim.vim syntax check

if exists("g:loaded_syntastic_nim_nim_checker")
    finish
endif
let g:loaded_syntastic_nim_nim_checker = 1

let s:save_cpo = &cpo
set cpo&vim

function! s:CurrentNimFile()
    let save_cur = getpos('.')
    call cursor(0, 0, 0)

    let PATTERN = "\\v^\\#\\s*included from \\zs.*\\ze"
    let l = search(PATTERN, "n")

    if l != 0
        let f = matchstr(getline(l), PATTERN)
        let l:to_check = expand('%:h') . "/" . f
    else
        let l:to_check = expand("%")
    endif

    call setpos('.', save_cur)
    return l:to_check
endfunction

function! SyntaxCheckers_nim_nim_GetLocList()
    let makeprg = 'nim check --listfullpaths ' . s:CurrentNimFile()
    let errorformat = '%I%f(%l\, %c) Hint: %m,' .
        \   '%W%f(%l\, %c) Warning: %m,' .
        \   '%E%f(%l\, %c) Error: %m'

    return SyntasticMake({'makeprg': makeprg, 'errorformat': errorformat})
endfunction

function! SyntaxCheckers_nim_nim_IsAvailable()
    return executable("nim")
endfunction

call g:SyntasticRegistry.CreateAndRegisterChecker({
    \ 'filetype': 'nim',
    \ 'name': 'nim'
    \ })

let &cpo = s:save_cpo
unlet s:save_cpo
