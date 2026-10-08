"""Meter actual replacement inputs and projected output before materialization."""
import contextvars
from contextlib import contextmanager
MAX_TEXT_BYTES=65536
MAX_WORK=16777216
MAX_TICKETS=65536
_work=contextvars.ContextVar('ebu_work',default=0)
def check_text(value):
    if type(value) is not str:
        raise TypeError('text must be a string')
    if len(value.encode('utf-8'))>MAX_TEXT_BYTES:
        raise ValueError('text byte budget exceeded')
def charge(n):
    total=_work.get()+n
    if total>MAX_WORK:
        raise ValueError('cumulative replacement work budget exceeded')
    _work.set(total)
@contextmanager
def scope():
    token=_work.set(0)
    try:
        yield
    finally:
        _work.reset(token)
def replace(text,old,new):
    check_text(text);check_text(old);check_text(new)
    charge(len(text))
    size=len(text.encode('utf-8'))+text.count(old)*(len(new.encode('utf-8'))-len(old.encode('utf-8')))
    if size>MAX_TEXT_BYTES:
        raise ValueError('projected replacement output byte budget exceeded')
    return text.replace(old,new)
def sub(pattern,replacement,text):
    check_text(text);check_text(replacement);charge(len(text))
    # Public regex templates are still interpreted by Python. Before expanding
    # a template, bound its conservative zero-group match multiplier.
    size=len(text.encode('utf-8'))
    for match in pattern.finditer(text):
        matched=match.group().encode('utf-8')
        if '\\' in replacement and len(replacement.encode('utf-8'))*max(1,len(matched))>MAX_TEXT_BYTES:
            raise ValueError('replacement template expansion budget exceeded')
        expanded=match.expand(replacement)
        size+=len(expanded.encode('utf-8'))-len(matched)
        if size>MAX_TEXT_BYTES:
            raise ValueError('projected replacement output byte budget exceeded')
    return pattern.sub(replacement,text)
