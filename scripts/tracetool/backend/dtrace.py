#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DTrace/SystemTAP backend.
"""

__author__     = "Lluís Vilanova <vilanova@ac.upc.edu>"
__copyright__  = "Copyright 2012, Lluís Vilanova <vilanova@ac.upc.edu>"
__license__    = "GPL version 2 or (at your option) any later version"

__maintainer__ = "Stefan Hajnoczi"
__email__      = "stefanha@linux.vnet.ibm.com"


from tracetool import out
from tracetool.backend.simple import is_string


PUBLIC = True


PROBEPREFIX = None

def _probeprefix():
    if PROBEPREFIX is None:
        raise ValueError("you must set PROBEPREFIX")
    return PROBEPREFIX


BINARY = None

def _binary():
    if BINARY is None:
        raise ValueError("you must set BINARY")
    return BINARY


def stap_escape(identifier):
    # Append underscore to reserved keywords
    if identifier in RESERVED_WORDS:
        return identifier + '_'
    return identifier


def c(events):
    pass


def h(events):
    out('#include "trace/generated-tracers-dtrace.h"',
        '')

    for e in events:
        out('static inline void trace_%(name)s(%(args)s) {',
            '    QEMU_%(uppername)s(%(argnames)s);',
            '}',
            name = e.name,
            args = e.args,
            uppername = e.name.upper(),
            argnames = ", ".join(e.args.names()),
            )


def d(events):
    out('provider qemu {')

    for e in events:
        args = str(e.args)

        # DTrace provider syntax expects foo() for empty
        # params, not foo(void)
        if args == 'void':
            args = ''

        # Define prototype for probe arguments
        out('',
            'probe %(name)s(%(args)s);',
            name = e.name,
            args = args,
            )

    out('',
        '};')


# Technically 'self' is not used by systemtap yet, but
# they recommended we keep it in the reserved list anyway
RESERVED_WORDS = (
    'break', 'catch', 'continue', 'delete', 'else', 'for',
    'foreach', 'function', 'global', 'if', 'in', 'limit',
    'long', 'next', 'probe', 'return', 'self', 'string',
    'try', 'while'
    )

def stap(events):
    for e in events:
        # Define prototype for probe arguments
        out('probe %(probeprefix)s.%(name)s = process("%(binary)s").mark("%(name)s")',
            '{',
            probeprefix = _probeprefix(),
            name = e.name,
            binary = _binary(),
            )

        i = 1
        if len(e.args) > 0:
            for name in e.args.names():
                name = stap_escape(name)
                out('  %s = $arg%d;' % (name, i))
                i += 1

        out('}')

    out()


def simpletrace_stap(events):
    for event_id, e in enumerate(events):
        out('probe %(probeprefix)s.simpletrace.%(name)s = %(probeprefix)s.%(name)s ?',
            '{',
            probeprefix=_probeprefix(),
            name=e.name)

        # Calculate record size
        sizes = ['24'] # sizeof(TraceRecord)
        for type_, name in e.args:
            name = stap_escape(name)
            if is_string(type_):
                out('    try {',
                    '        arg%(name)s_str = %(name)s ? user_string_n(%(name)s, 512) : "<null>"',
                    '    } catch {}',
                    '    arg%(name)s_len = strlen(arg%(name)s_str)',
                    name=name)
                sizes.append('4 + arg%s_len' % name)
            else:
                sizes.append('8')
        sizestr = ' + '.join(sizes)

        # Generate format string and value pairs for record header and arguments
        fields = [('8b', str(event_id)),
                  ('8b', 'gettimeofday_ns()'),
                  ('4b', sizestr),
                  ('4b', 'pid()')]
        for type_, name in e.args:
            name = stap_escape(name)
            if is_string(type_):
                fields.extend([('4b', 'arg%s_len' % name),
                               ('.*s', 'arg%s_len, arg%s_str' % (name, name))])
            else:
                fields.append(('8b', name))

        # Emit the entire record in a single SystemTap printf()
        fmt_str = '%'.join(fmt for fmt, _ in fields)
        arg_str = ', '.join(arg for _, arg in fields)
        out('    printf("%%%(fmt_str)s", %(arg_str)s)',
            fmt_str=fmt_str, arg_str=arg_str)

        out('}')

    out()
