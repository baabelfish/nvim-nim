from collections import defaultdict
try:
    import pexpect
except ImportError:
    pexpect = None

import neovim
import tempfile


HIGHLIGHTS = {
    'skProc': "Function",
    'skTemplate': "PreProc",
    'skType': "Type",
    'skMacro': "Macro",
    'skMethod': "Function",
    'skField': "Identifier",
    'skAlias': "Type",
    'skConditional': "Conditional",
    'skConst': "Constant",
    'skConverter': "Function",
    'skDynLib': "Include",
    'skEnumField': "Identifier",
    'skForVar': "Special",
    'skGenericParam': "Typedef",
    'skGlobalVar': "Constant",
    'skGlobalLet': "Constant",
    'skIterator': "Keyword",
    'skResult': "Keyword",
    'skLabel': "Identifier",
    'skLet': "Constant",
    'skModule': "Include",
    'skPackage': "Define",
    'skParam': "Identifier",
    'skStub': "PreCondit",
    'skTemp': "Identifier",
    'skUnknown': "Error",
    'skVar': "Constant",
    }


@neovim.plugin
class Main(object):
    def __init__(self, vim):
        self.vim = vim
        self.procs = {}
        self.highlights = {}
        self.running = {}
        self.to_run = set()
        self.disabled = False

    def new_proc(self, bufpath):
        proc = pexpect.spawnu('nimsuggest --colors:off --stdin --refresh '
            + bufpath)
        self.procs[bufpath] = proc
        try:
            proc.expect('> ')
            return proc
        except Exception:
            self.vim.command('echoerr "Error trying to start nimsuggest"')

    def on_init(self, context):
        if pexpect is None:
            self.disabled = True
            self.vim.command('echoerr "pexpect must be installed for '
                'deoplete completion to work (pip install pexpect)"')
        if self.disabled:
            return
        proc = self.procs.get(context['bufpath'], None)
        if proc is None:
            self.new_proc(context['bufpath'])

    def get_lines(self, bufpath):
        proc = self.procs.get(bufpath)
        if not proc:
            proc = self.new_proc(bufpath)
        try:
            with tempfile.NamedTemporaryFile() as tmp_file:
                self.vim.command('silent write! ' + tmp_file.name)
                query = 'highlight %s;%s:1:1\r' % (bufpath, tmp_file.name)
                proc.send(query)
                proc.expect('\r\n\r\n> ')
                res = proc.before
                return [
                    self.parse(x) for x in res.split('\n')
                    if x.startswith('highlight\t')]
        except Exception:
            # Sometimes the nimsuggest process crashes
            self.procs.pop(bufpath, None)
            return self.highlight(bufpath)

    def parse(self, line):
        return line

    def do_highlight(self, bufpath, lines):
        new_highlights = {}
        # Order by line / col / size to fix some overwrite cases
        for line in sorted([x.split('\t') for x in lines] or [],
                key=lambda y: (y[2], y[3], y[4])):
            # There are sometimes duplicates
            if str(line) in new_highlights:
                continue
            _, type_, line_nbr, start, length = line
            if type_ == 'skProc' and length != '1':
                length = str(int(length) + 1)
            if type_ in HIGHLIGHTS:
                new_highlights[str(line)] = [HIGHLIGHTS[type_],
                    [line_nbr, str(int(start) + 1), length]]
        self.update_highlights(bufpath, new_highlights)

    def update_highlights(self, bufpath, new_highlights):
        if bufpath in self.highlights:
            existing = self.highlights[bufpath]
        else:
            existing = {}
            self.highlights[bufpath] = existing

        to_remove = []
        for key in [x for x in existing]:
            if key not in new_highlights:
                to_remove.append(existing[key])
                del existing[key]
            else:
                del new_highlights[key]
        if to_remove:
            self.vim.funcs.NimHighlighterUnmatch(to_remove)

        to_match = defaultdict(list)
        for line, (k, v) in new_highlights.items():
            to_match[k].append((line, v))
        for k, groups in to_match.items():
            new_matches = self.vim.funcs.NimHighlighterMatch(k,
                [x[1] for x in groups])
            for match, key in zip(new_matches, (x[0] for x in groups)):
                existing[key] = match

    @neovim.function('NimHighlight')
    def highlight(self, args):
        if pexpect is None:
            self.disabled = True
            self.vim.command('echoerr "pexpect must be installed for '
                'async highlighting to work (pip install pexpect)"')
        if self.disabled:
            return

        bufpath = self.vim.funcs.expand('%:p')
        if bufpath in self.running:
            if bufpath not in self.to_run:
                self.to_run.add(bufpath)
            return
        self.running[bufpath] = True
        try:
            lines = self.get_lines(bufpath)
            self.do_highlight(bufpath, lines)
        finally:
            del self.running[bufpath]
        if bufpath in self.to_run:
            self.to_run.remove(bufpath)
            self.highlight(args)
