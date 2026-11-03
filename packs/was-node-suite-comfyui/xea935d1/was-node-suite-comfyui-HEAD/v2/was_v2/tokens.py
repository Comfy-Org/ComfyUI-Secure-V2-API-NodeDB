"""TextTokens of WAS_Node_Suite.py (class TextTokens), for a guest node.

The original replaced, in this order: [time] (the current UNIX time, whole seconds), [hostname] (socket.gethostname()),
[cuda_device] and [cuda_name] (the host's torch device), [user] (os.getlogin()), then the custom tokens stored in
its settings database (was_suite_settings.json in its pack folder), then every [time(<strftime format>)]. A guest
reads its own clock, so [time] and [time(...)] are the same; the host-information tokens are refused by name when the
text contains them; there is no settings database, so there are no custom tokens (the original's default).
"""
import re
import time

from .refusals import HOST_TOKEN, SecureConversionRefusal

HOST_TOKENS = ("[hostname]", "[cuda_device]", "[cuda_name]", "[user]")


class TextTokens:
    def __init__(self):
        self.custom_tokens = {}
        self.tokens = {'[time]': str(time.time()).replace('.', '_')}
        if '.' in self.tokens['[time]']:
            self.tokens['[time]'] = self.tokens['[time]'].split('.')[0]

    def format_time(self, format_code):
        return time.strftime(format_code, time.localtime(time.time()))

    def parseTokens(self, text):
        for token in HOST_TOKENS:
            if token in text:
                raise SecureConversionRefusal(HOST_TOKEN.format(token=token))

        tokens = self.tokens.copy()
        if self.custom_tokens:
            tokens.update(self.custom_tokens)

        # Update time
        tokens['[time]'] = str(time.time())
        if '.' in tokens['[time]']:
            tokens['[time]'] = tokens['[time]'].split('.')[0]

        for token, value in tokens.items():
            if token.startswith('[time('):
                continue
            pattern = re.compile(re.escape(token))
            text = pattern.sub(value, text)

        def replace_custom_time(match):
            format_code = match.group(1)
            return self.format_time(format_code)

        text = re.sub(r'\[time\((.*?)\)\]', replace_custom_time, text)

        return text
