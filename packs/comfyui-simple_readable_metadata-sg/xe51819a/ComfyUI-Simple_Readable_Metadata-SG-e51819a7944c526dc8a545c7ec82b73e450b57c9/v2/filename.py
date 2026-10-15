"""Pinned date/token replacements, evaluated only on the admitted guest clock."""
from datetime import datetime
import re


def parse_filename(filename_prefix):
    def replace_date(match):
        format_str = match.group(1)
        conversions = {'yyyy': '%Y', 'yy': '%y', 'MM': '%m', 'dd': '%d',
                       'HH': '%H', 'hh': '%H', 'mm': '%M', 'ss': '%S'}
        for old, new in conversions.items():
            format_str = format_str.replace(old, new)
        return datetime.now().strftime(format_str)
    filename_prefix = re.sub(r'%date:([^%]+)%', replace_date, filename_prefix)

    def replace_time(match):
        format_str = match.group(1)
        conversions = {'HH': '%H', 'hh': '%H', 'mm': '%M', 'ss': '%S'}
        for old, new in conversions.items():
            format_str = format_str.replace(old, new)
        return datetime.now().strftime(format_str)
    filename_prefix = re.sub(r'%time:([^%]+)%', replace_time, filename_prefix)
    if '%date%' in filename_prefix:
        filename_prefix = filename_prefix.replace('%date%', datetime.now().strftime('%Y-%m-%d'))
    if '%time%' in filename_prefix:
        filename_prefix = filename_prefix.replace('%time%', datetime.now().strftime('%H-%M-%S'))
    if '%timestamp%' in filename_prefix:
        filename_prefix = filename_prefix.replace('%timestamp%', str(int(datetime.now().timestamp())))
    return filename_prefix
