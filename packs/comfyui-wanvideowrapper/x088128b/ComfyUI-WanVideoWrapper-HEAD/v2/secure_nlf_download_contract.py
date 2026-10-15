"""Pure original URL/cache policy for the pending NLF download admission seam."""
import json
import re
from ._wan_catalogue import valid_catalogue_name

URLS=(
 'https://github.com/isarandi/nlf/releases/download/v0.3.2/nlf_l_multi_0.3.2.torchscript',
 'https://github.com/isarandi/nlf/releases/download/v0.2.2/nlf_l_multi_0.2.2.torchscript',
)
LEGACY_CACHE_NAME='nlf_l_multi_0.3.2.torchscript'
CACHE_KEY='wan-original-nlf-download-cache-v1'
CACHE_FORMAT='wan-original-nlf-first-file-v1'


def validate_nlf_download_url(url):
    if url not in URLS:
        raise ValueError(f'URL {url} is not in the list of allowed models.')


def decode_nlf_cache_record(value):
    if value is None or value=='':return None
    if not isinstance(value,str) or len(value.encode('utf-8'))>8192:
        raise ValueError('Invalid bounded NLF cache record')
    record=json.loads(value)
    if (not isinstance(record,dict) or set(record)!={'format','model_name','sha256','source_url'}
            or record['format']!=CACHE_FORMAT or not valid_catalogue_name(record['model_name'])
            or not isinstance(record['sha256'],str) or re.fullmatch('[0-9a-f]{64}',record['sha256']) is None
            or record['source_url'] not in URLS):
        raise ValueError('Invalid digest-bound NLF cache record')
    return record


def choose_nlf_cached_asset(url,legacy_exists,record,record_asset_exists):
    # The original validates the URL before inspecting its shared fixed file.
    # Its warmup choice never controls which previously downloaded file wins.
    validate_nlf_download_url(url)
    if legacy_exists:return {'model_name':LEGACY_CACHE_NAME,'sha256':None,'source':'legacy_fixed_file'}
    if record is not None and record_asset_exists:
        return {'model_name':record['model_name'],'sha256':record['sha256'],'source':'durable_first_selection'}
    return None
