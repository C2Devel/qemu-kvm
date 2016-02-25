#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Pretty-printer for simple trace backend binary trace files
#
# Copyright IBM, Corp. 2010
#
# Portions copyright 2012-2014, Lluís Vilanova <vilanova@ac.upc.edu>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.
#
# For help see docs/tracing.txt

import struct
import re
import inspect


def is_string(arg):
    strtype = ('const char*', 'char*', 'const char *', 'char *')
    if arg.lstrip().startswith(strtype):
        return True
    else:
        return False


class Arguments:
    """Event arguments description."""

    def __init__(self, args):
        """
        Parameters
        ----------
        args :
            List of (type, name) tuples.
        """
        self._args = args

    def copy(self):
        """Create a new copy."""
        return Arguments(list(self._args))

    @staticmethod
    def build(arg_str):
        """Build and Arguments instance from an argument string.

        Parameters
        ----------
        arg_str : str
            String describing the event arguments.
        """
        res = []
        for arg in arg_str.split(","):
            arg = arg.strip()
            if arg == 'void':
                continue

            if '*' in arg:
                arg_type, identifier = arg.rsplit('*', 1)
                arg_type += '*'
                identifier = identifier.strip()
            else:
                arg_type, identifier = arg.rsplit(None, 1)

            res.append((arg_type, identifier))
        return Arguments(res)

    def __iter__(self):
        """Iterate over the (type, name) pairs."""
        return iter(self._args)

    def __len__(self):
        """Number of arguments."""
        return len(self._args)

    def __str__(self):
        """String suitable for declaring function arguments."""
        if len(self._args) == 0:
            return "void"
        else:
            return ", ".join([ " ".join([t, n]) for t,n in self._args ])

    def __repr__(self):
        """Evaluable string representation for this object."""
        return "Arguments(\"%s\")" % str(self)

    def names(self):
        """List of argument names."""
        return [ name for _, name in self._args ]

    def types(self):
        """List of argument types."""
        return [ type_ for type_, _ in self._args ]


class Event(object):
    """Event description.

    Attributes
    ----------
    name : str
        The event name.
    fmt : str
        The event format string.
    properties : set(str)
        Properties of the event.
    args : Arguments
        The event arguments.
    """

    _CRE = re.compile("((?P<props>.*)\s+)?(?P<name>[^(\s]+)\((?P<args>[^)]*)\)\s*(?P<fmt>\".*)?")

    _VALID_PROPS = set(["disable"])

    def __init__(self, name, props, fmt, args):
        """
        Parameters
        ----------
        name : string
            Event name.
        props : list of str
            Property names.
        fmt : str
            Event printing format.
        args : Arguments
            Event arguments.
        """
        self.name = name
        self.properties = props
        self.fmt = fmt
        self.args = args

        unknown_props = set(self.properties) - self._VALID_PROPS
        if len(unknown_props) > 0:
            raise ValueError("Unknown properties: %s"
                             % ", ".join(unknown_props))

    def copy(self):
        """Create a new copy."""
        return Event(self.name, list(self.properties), self.fmt,
                     self.args.copy(), self)

    @staticmethod
    def build(line_str):
        """Build an Event instance from a string.

        Parameters
        ----------
        line_str : str
            Line describing the event.
        """
        m = Event._CRE.match(line_str)
        assert m is not None
        groups = m.groupdict('')

        name = groups["name"]
        props = groups["props"].split()
        fmt = groups["fmt"]
        args = Arguments.build(groups["args"])

        return Event(name, props, fmt, args)

    def __repr__(self):
        """Evaluable string representation for this object."""
        return "Event('%s %s(%s) %s')" % (" ".join(self.properties),
                                          self.name,
                                          self.args,
                                          self.fmt)

    QEMU_TRACE               = "trace_%(name)s"

    def api(self, fmt=None):
        if fmt is None:
            fmt = Event.QEMU_TRACE
        return fmt % {"name": self.name}


def _read_events(fobj):
    res = []
    for line in fobj:
        if not line.strip():
            continue
        if line.lstrip().startswith('#'):
            continue
        res.append(Event.build(line))
    return res


header_event_id = 0xffffffffffffffff
header_magic    = 0xf2b177cb0aa429b4
dropped_event_id = 0xfffffffffffffffe

log_header_fmt = '=QQQ'
rec_header_fmt = '=QQII'

def read_header(fobj, hfmt):
    '''Read a trace record header'''
    hlen = struct.calcsize(hfmt)
    hdr = fobj.read(hlen)
    if len(hdr) != hlen:
        return None
    return struct.unpack(hfmt, hdr)

def get_record(edict, rechdr, fobj):
    """Deserialize a trace record from a file into a tuple (event_num, timestamp, pid, arg1, ..., arg6)."""
    if rechdr is None:
        return None
    rec = (rechdr[0], rechdr[1], rechdr[3])
    if rechdr[0] != dropped_event_id:
        event_id = rechdr[0]
        event = edict[event_id]
        for type, name in event.args:
            if is_string(type):
                l = fobj.read(4)
                (len,) = struct.unpack('=L', l)
                s = fobj.read(len)
                rec = rec + (s,)
            else:
                (value,) = struct.unpack('=Q', fobj.read(8))
                rec = rec + (value,)
    else:
        (value,) = struct.unpack('=Q', fobj.read(8))
        rec = rec + (value,)
    return rec


def read_record(edict, fobj):
    """Deserialize a trace record from a file into a tuple (event_num, timestamp, pid, arg1, ..., arg6)."""
    rechdr = read_header(fobj, rec_header_fmt)
    return get_record(edict, rechdr, fobj) # return tuple of record elements

def read_trace_header(fobj):
    """Read and verify trace file header"""
    header = read_header(fobj, log_header_fmt)
    if header is None or \
       header[0] != header_event_id or \
       header[1] != header_magic:
        raise ValueError('Not a valid trace file!')

    log_version = header[2]
    if log_version not in [0, 2, 3]:
        raise ValueError('Unknown version of tracelog format!')
    if log_version != 3:
        raise ValueError('Log format %d not supported with this QEMU release!'
                         % log_version)

def read_trace_records(edict, fobj):
    """Deserialize trace records from a file, yielding record tuples (event_num, timestamp, pid, arg1, ..., arg6)."""
    while True:
        rec = read_record(edict, fobj)
        if rec is None:
            break

        yield rec

class Analyzer(object):
    """A trace file analyzer which processes trace records.

    An analyzer can be passed to run() or process().  The begin() method is
    invoked, then each trace record is processed, and finally the end() method
    is invoked.

    If a method matching a trace event name exists, it is invoked to process
    that trace record.  Otherwise the catchall() method is invoked."""

    def begin(self):
        """Called at the start of the trace."""
        pass

    def catchall(self, event, rec):
        """Called if no specific method for processing a trace event has been found."""
        pass

    def end(self):
        """Called at the end of the trace."""
        pass

def process(events, log, analyzer, read_header=True):
    """Invoke an analyzer on each event in a log."""
    if isinstance(events, str):
        events = _read_events(open(events, 'r'))
    if isinstance(log, str):
        log = open(log, 'rb')

    if read_header:
        read_trace_header(log)

    dropped_event = Event.build("Dropped_Event(uint64_t num_events_dropped)")
    edict = {dropped_event_id: dropped_event}

    for num, event in enumerate(events):
        edict[num] = event

    def build_fn(analyzer, event):
        if isinstance(event, str):
            return analyzer.catchall

        fn = getattr(analyzer, event.name, None)
        if fn is None:
            return analyzer.catchall

        event_argcount = len(event.args)
        fn_argcount = len(inspect.getargspec(fn)[0]) - 1
        if fn_argcount == event_argcount + 1:
            # Include timestamp as first argument
            return lambda _, rec: fn(*((rec[1:2],) + rec[3:3 + event_argcount]))
        elif fn_argcount == event_argcount + 2:
            # Include timestamp and pid
            return lambda _, rec: fn(*rec[1:3 + event_argcount])
        else:
            # Just arguments, no timestamp or pid
            return lambda _, rec: fn(*rec[3:3 + event_argcount])

    analyzer.begin()
    fn_cache = {}
    for rec in read_trace_records(edict, log):
        event_num = rec[0]
        event = edict[event_num]
        if event_num not in fn_cache:
            fn_cache[event_num] = build_fn(analyzer, event)
        fn_cache[event_num](event, rec)
    analyzer.end()

def run(analyzer):
    """Execute an analyzer on a trace file given on the command-line.

    This function is useful as a driver for simple analysis scripts.  More
    advanced scripts will want to call process() instead."""
    import sys

    read_header = True
    if len(sys.argv) == 4 and sys.argv[1] == '--no-header':
        read_header = False
        del sys.argv[1]
    elif len(sys.argv) != 3:
        sys.stderr.write('usage: %s [--no-header] <trace-events> ' \
                         '<trace-file>\n' % sys.argv[0])
        sys.exit(1)

    events = _read_events(open(sys.argv[1], 'r'))
    process(events, sys.argv[2], analyzer, read_header=read_header)

if __name__ == '__main__':
    class Formatter(Analyzer):
        def __init__(self):
            self.last_timestamp = None

        def catchall(self, event, rec):
            timestamp = rec[1]
            if self.last_timestamp is None:
                self.last_timestamp = timestamp
            delta_ns = timestamp - self.last_timestamp
            self.last_timestamp = timestamp

            fields = [event.name, '%0.3f' % (delta_ns / 1000.0),
                      'pid=%d' % rec[2]]
            i = 3
            for type, name in event.args:
                if is_string(type):
                    fields.append('%s=%s' % (name, rec[i]))
                else:
                    fields.append('%s=0x%x' % (name, rec[i]))
                i += 1
            print ' '.join(fields)

    run(Formatter())
