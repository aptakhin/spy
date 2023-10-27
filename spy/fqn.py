from typing import Optional

class FQN:
    """
    Fully qualified name.

    A FQN uniquely identify a named object inside the current VM. It is
    formated as 'modname::attr', where 'modname' can be composed of multiple
    parts separated by dots (e.g. 'a.b.c').

    NOTE: this is not part of the Node hierarchy
    """
    modname: str
    attr: str

    def __init__(self,
                 fullname: Optional[str] = None,
                 *,
                 modname: Optional[str] = None,
                 attr: Optional[str] = None
                 ) -> None:
        if fullname is None:
            assert modname is not None
            assert attr is not None
        else:
            assert modname is None
            assert attr is None
            assert fullname.count('::') == 1
            modname, attr = fullname.split('::')
        #
        self.modname = modname
        self.attr = attr

    def __repr__(self):
        return f"FQN({self.fullname!r})"

    def __str__(self):
        return self.fullname

    def __eq__(self, other):
        if not isinstance(other, FQN):
            return NotImplemented
        return self.fullname == other.fullname

    def __hash__(self):
        return hash(self.fullname)

    @property
    def fullname(self):
        return f'{self.modname}::{self.attr}'

    def as_c_name(self):
        return self.fullname.replace('.', '_').replace('::', '_')
