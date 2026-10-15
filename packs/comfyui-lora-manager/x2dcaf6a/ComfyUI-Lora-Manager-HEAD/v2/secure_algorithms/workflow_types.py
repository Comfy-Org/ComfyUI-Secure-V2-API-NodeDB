"""Pure legacy wildcard declarations; no library/path/service imports."""
class AnyType(str):
    def __ne__(self, other):
        return False


class FlexibleOptionalInputType(dict):
    def __init__(self, type):
        super().__init__()
        self.type = type

    def __getitem__(self, key):
        return (self.type,)

    def __contains__(self, key):
        return True


any_type = AnyType('*')
