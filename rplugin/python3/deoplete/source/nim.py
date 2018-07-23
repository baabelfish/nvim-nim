# ============================================================================
# File: rplugin/python3/deoplete/sources/nim.py
# Author: Jean Cavallo <jean.cavallo@hotmail.fr>
# License: MIT license  {{{
#     Permission is hereby granted, free of charge, to any person obtaining
#     a copy of this software and associated documentation files (the
#     "Software"), to deal in the Software without restriction, including
#     without limitation the rights to use, copy, modify, merge, publish,
#     distribute, sublicense, and/or sell copies of the Software, and to
#     permit persons to whom the Software is furnished to do so, subject to
#     the following conditions:
#
#     The above copyright notice and this permission notice shall be included
#     in all copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#     OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#     MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#     IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#     CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#     TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#     SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# ============================================================================

import tempfile
try:
    import pexpect
except ImportError:
    pexpect = None

from .base import Base

TYPES = {
    'skProc': ['p', 'Function'],
    'skTemplate': ['t', 'Template'],
    'skType': ['T', 'Type'],
    'skMacro': ['M', 'Macro'],
    'skMethod': ['m', 'Method'],
    'skField': ['field', 'Field'],
    'skAlias': ['a', 'Alias'],
    'skConditional': ['c', 'Conditional'],
    'skConst': ['C', 'Constant'],
    'skConverter': ['c', 'Converter'],
    'skDynLib': ['d', 'Dynamic library'],
    'skEnumField': ['e', 'Enum field'],
    'skForVar': ['l', 'Loop variable'],
    'skGenericParam': ['g', 'Generic parameter'],
    'skGlobalVar': ['g', 'Global variable'],
    'skGlobalLet': ['g', 'Global constant'],
    'skIterator': ['i', 'Iterator'],
    'skLabel': ['l', 'Label'],
    'skLet': ['r', 'Runtime constant'],
    'skModule': ['m', 'Module'],
    'skPackage': ['p', 'Package'],
    'skParam': ['p', 'Parameter'],
    'skResult': ['r', 'Result'],
    'skStub': ['s', 'Stub'],
    'skTemp': ['t', 'Temporary'],
    'skUnknown': ['u', 'Unknown'],
    'skVar': ['v', 'Variable'],
    }

SORT_KEYS = {
    'Field': 0,
    'Function': 1,
    'Method': 2,
    'Variable': 3,
    'Parameter': 4,
    'LoopVariable': 5,
    'Runtime constant': 6,
    'Global variable': 7,
    'Constant': 8,
    'Global constant': 9,
    'Module': 10,
    'Package': 11,
    }


class Source(Base):
    def __init__(self, vim):
        Base.__init__(self, vim)

        self.name = 'nim'
        self.mark = '[Nim]'
        self.min_pattern_length = 0
        self.rank = 1000
        self.procs = {}
        self.disabled = False
        self.filetypes = ['nim', 'nims', 'nimble']

    def on_event(self, context):
        pass

    def on_init(self, context):
        if pexpect is None:
            self.disabled = True
            self.vim.command('echoerr "pexpect must be installed for '
                'deoplete completion to work (pip install pexpect)"')
        if self.disabled:
            return
        proc = self.procs.get(context['bufpath'], None)
        if proc is None:
            self.new_proc(context)

    def new_proc(self, context):
        max_val = str(self.vim.eval('g:nvim_nim_deoplete_limit'))
        proc = pexpect.spawnu('nimsuggest --colors:off --stdin --refresh '
            + '--maxresults:' + max_val + ' ' + context['bufpath'])
        self.procs[context['bufpath']] = proc
        try:
            proc.expect('> ')
            return proc
        except Exception:
            self.vim.command('echoerr "Error trying to start nimsuggest"')

    def get_complete_position(self, context):
        if len(context['input']) < 2:
            return 0
        for idx, val in enumerate(reversed(context['input'])):
            val = ord(val)
            if not(48 <= val <= 57 or
                    65 <= val <= 90 or
                    97 <= val <= 122 or
                    val == 95):
                return len(context['input']) - idx
        return len(context['input']) - len(context['input'].lstrip())

    def gather_candidates(self, context):
        #  bufpath  => filepath
        #  position  => [X, line, col, Y]
        if context['input'].startswith('import '):
            return self.get_module_completions(context)
        else:
            return self.get_nim_completions(context)

    def get_module_completions(self, context):
        _, line, col, _ = context['position']
        modules = self.vim.eval('modules#FindGlobalImports()')
        return [
            {'word': x, 'kind': modules[x], 'info': 'G', 'menu': 'module'}
            for x in sorted(modules.keys())]

    def get_nim_completions(self, context):
        _, line, col, _ = context['position']
        proc = self.procs.get(context['bufpath'])
        if not proc:
            proc = self.new_proc(context)
        try:
            with tempfile.NamedTemporaryFile() as tmp_file:
                self.vim.command('silent write! ' + tmp_file.name)
                query = 'sug %s;%s:%i:%i\r' % (
                    context['bufpath'], tmp_file.name, line, col - 1)
                proc.send(query)
                proc.expect('\r\n\r\n> ')
                res = proc.before
                lines = [
                    self.parse(x) for x in res.split('\n')
                    if x.startswith('sug\t')]
                lines.sort(
                    key=lambda x: SORT_KEYS.get(x['kind'].split(' ')[0], 100))
        except Exception:
            # Sometimes the nimsuggest process crashes
            self.procs.pop(context['bufpath'], None)
            return self.get_nim_completions(context)
        return lines

    def parse(self, line):
        data = [x for x in line.split('\t')]
        path = data[2].split('.')
        details = self.get_signature(data[3])
        return {
            'word': path[-1],
            'kind': TYPES[data[1]][1] + (' : ' + details if details else ''),
            'info': data[7],
            'menu': path[0],
            }

    def get_signature(self, data):
        res = self.vim.eval('util#ParseSignature("%s")' % data)
        return ', '.join(res['params']) + (
            ' => ' + res['reval'] if res['reval'] else '')
