"""Formatter utility

Provides helpers to normalize and merge assembly files:
- strip comments
- merge externs
- merge .data and .bss entries without duplication
- inline only required stdlib functions (avoid duplicates)

This utility is intentionally conservative: it does not remove or
rewrite user code except for comment stripping and replacing generated
blocks when instructed by the code generator via markers.
"""
from typing import List, Set
import re
import os


def strip_comments(lines: List[str]) -> List[str]:
    out = []
    for ln in lines:
        # Remove anything after a semicolon (NASM comment) unless the
        # semicolon is inside a backtick-delimited string. Backticks are
        # rare in user files, but our generated data uses them. A simple
        # heuristic: if the line contains a backtick before a semicolon,
        # keep everything. Otherwise split.
        if '`' in ln and ';' in ln and ln.find('`') < ln.find(';'):
            out.append(ln.rstrip())
            continue

        if ';' in ln:
            ln = ln.split(';', 1)[0]
        ln = ln.rstrip()
        if ln:
            out.append(ln)
    return out


def collect_sections(original: str):
    """Parse the original file into preamble, data_lines, bss_lines, externs and text_lines.
    Returns a dict with those keys (lists/sets).
    """
    preamble = []
    data_lines = []
    bss_lines = []
    externs = []
    text_lines = []

    cur = None
    seen_section = False
    for ln in original.splitlines():
        s = ln.strip()
        ls = s.lower()
        if ls.startswith('section .data'):
            cur = 'data'
            seen_section = True
            continue
        if ls.startswith('section .bss'):
            cur = 'bss'
            seen_section = True
            continue
        if ls.startswith('section .text'):
            cur = 'text'
            seen_section = True
            continue

        if ls.startswith('extern '):
            # record extern (keep original spacing)
            externs.append(s[len('extern '):].strip())
            continue

        if not seen_section:
            preamble.append(ln)
            continue

        # After seeing any section, route lines based on cur
        if cur == 'data':
            if s:
                data_lines.append(ln)
        elif cur == 'bss':
            if s:
                bss_lines.append(ln)
        else:
            text_lines.append(ln)

    return {
        'preamble': preamble,
        'data': data_lines,
        'bss': bss_lines,
        'externs': externs,
        'text': text_lines
    }


def merge_unique(existing: List[str], additions: List[str]) -> List[str]:
    seen = set(l.strip() for l in existing)
    out = existing.copy()
    for a in additions:
        if not a:
            continue
        if a.strip() not in seen:
            out.append(a)
            seen.add(a.strip())
    return out


def split_functions(code: str):
    """Split stdlib code blob into function chunks using label lines ending with ':' as separators."""
    funcs = []
    cur = []
    for ln in code.splitlines():
        if ln.strip().endswith(':') and cur:
            funcs.append('\n'.join(cur).rstrip())
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        funcs.append('\n'.join(cur).rstrip())
    return funcs


def format_and_merge(original: str, generated_helpers: List[str], gen_blocks: dict, deps: dict, data_section: List[str]) -> str:
    """Return merged assembly text.

    - original: original source text
    - generated_helpers: list of helper lines from code generator (not per-block)
    - gen_blocks: dict of generated blocks keyed by start line (value has 'lines' list)
    - deps: result of StandardLibrary.get_dependencies (dict with 'code','data','bss','externs')
    - data_section: list of data lines produced by the codegen (strings)
    """
    parts = collect_sections(original)

    # Strip comments from preamble and text (but keep generated blocks content intact)
    preamble = strip_comments(parts['preamble'])
    text = parts['text']
    # We will later replace text ranges with generated blocks using gen_blocks

    # Merge externs
    existing_externs = set(parts['externs'])
    for e in deps.get('externs', set()):
        existing_externs.add(e)

    # Merge data and bss (unique)
    merged_data = merge_unique(parts['data'], deps.get('data', []))
    merged_data = merge_unique(merged_data, data_section or [])

    merged_bss = merge_unique(parts['bss'], deps.get('bss', []))

    # Determine existing function labels in original to avoid duplicates
    existing_labels = set()
    for ln in original.splitlines():
        s = ln.strip()
        if s.endswith(':'):
            existing_labels.add(s[:-1])

    # Split deps['code'] into function chunks and include only those not present
    stdlib_code = deps.get('code', '') or ''
    stdlib_funcs = []
    if stdlib_code:
        for fn_chunk in split_functions(stdlib_code):
            # get first label
            first_line = fn_chunk.splitlines()[0].strip()
            label = first_line[:-1] if first_line.endswith(':') else None
            if label and label in existing_labels:
                continue
            stdlib_funcs.append(fn_chunk)

    # Build final output
    out_lines = []
    out_lines.extend(preamble)
    out_lines.append('')

    def inline_includes(lines: List[str], seen: Set[str] = None) -> List[str]:
        """Expand %include "path" directives by inlining the referenced file.

        - Resolves paths relative to the current working directory.
        - Prevents recursive includes using `seen` set.
        - If the file can't be read, leaves the original include line as a comment
          so the assembler still sees something informative.
        """
        if seen is None:
            seen = set()
        out = []
        include_re = re.compile(r'^%\s*include\s+["\'](.+?)["\']', re.IGNORECASE)

        for ln in lines:
            m = include_re.match(ln.strip())
            if not m:
                out.append(ln)
                continue

            inc_path = m.group(1)
            # resolve relative to cwd first
            cand = os.path.abspath(os.path.join(os.getcwd(), inc_path))
            if not os.path.exists(cand):
                # try relative to project root (same as cwd here) or as given
                cand = os.path.abspath(inc_path)

            if not os.path.exists(cand):
                # include not found — comment the directive for visibility
                out.append(f'; WARNING: include not found: {inc_path}')
                out.append(f'; {ln}')
                continue

            if cand in seen:
                out.append(f'; WARNING: skipping recursive include: {inc_path}')
                continue

            try:
                seen.add(cand)
                with open(cand, 'r', encoding='utf-8') as f:
                    inc_text = f.read()
                # preserve included file lines as-is (they may contain sections/labels)
                out.extend(inc_text.splitlines())
            except Exception as e:
                out.append(f'; WARNING: failed to read include {inc_path}: {e}')
                out.append(f'; {ln}')

        return out

    # externs
    if existing_externs:
        for e in sorted(existing_externs):
            out_lines.append(f'extern {e}')
        out_lines.append('')

    # data
    if merged_data:
        out_lines.append('section .data')
        out_lines.extend(strip_comments(merged_data))
        out_lines.append('')

    # bss
    if merged_bss:
        out_lines.append('section .bss')
        out_lines.extend(strip_comments(merged_bss))
        out_lines.append('')

    # inline generated blocks into text
    # Ensure we include an explicit `section .text` header before any text lines.
    # The collector intentionally skipped original section header lines; add it
    # back unless one of the generated helper lines already contains it.
    has_text_header = False
    # check generated helpers and deps for an existing text header
    # If found in generated_helpers, remove those lines so we don't append
    # the header at the end later; we'll add a single header in the
    # correct place below.
    if generated_helpers:
        filtered_helpers = []
        for ln in generated_helpers:
            # Remove any 'section .text' lines emitted by the generator so
            # they don't get appended at the end. Do NOT treat these as the
            # authoritative header — we'll add the section header right
            # before the text block below (unless a dependency provides one).
            if ln and ln.strip().lower().startswith('section .text'):
                continue
            filtered_helpers.append(ln)
        generated_helpers = filtered_helpers
    else:
        generated_helpers = []

    if not has_text_header:
        for ln in deps.get('code', '').splitlines():
            if ln.strip().lower().startswith('section .text'):
                has_text_header = True
                break

    def remove_highlevel_directives(lines: List[str]) -> List[str]:
        """Remove source-level DSL directive lines (if/while/for/etc.) from text.

        This prevents high-level statements from being left in the merged
        assembly (which would be invalid NASM). We only remove lines that
        start with a recognized keyword (ignoring leading whitespace).
        """
        directives = {'if', 'elif', 'else', 'endif', 'for', 'endfor', 'while', 'endwhile', 'func', 'endfunc'}
        out = []
        for ln in lines:
            s = ln.strip()
            if not s:
                out.append(ln)
                continue
            first = s.split()[0].lower()
            if first in directives:
                # skip DSL directive lines
                continue
            out.append(ln)
        return out

    if gen_blocks:
        orig_lines = remove_highlevel_directives(parts['text'])
        # Always ensure a text section header appears immediately before the
        # text block (unless a dependency already declared one). We removed
        # any stray header from generated_helpers above so we won't duplicate.
        if not has_text_header and orig_lines:
            out_lines.append('section .text')
        out_lines.extend(strip_comments(orig_lines))
        out_lines.append('')
    else:
        if not has_text_header and text:
            out_lines.append('section .text')
        out_lines.extend(strip_comments(text))
        out_lines.append('')

    # append any other generated helpers (code_lines not part of blocks)
    if generated_helpers:
        for ln in generated_helpers:
            if ln.strip():
                out_lines.append(ln)
        out_lines.append('')

    # append stdlib functions selected
    if stdlib_funcs:
        for fn in stdlib_funcs:
            out_lines.append(fn)
            out_lines.append('')

    return '\n'.join(out_lines).rstrip() + '\n'
