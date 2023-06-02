from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, W_Type
from spy.vm.module import W_Module
from spy.vm.codeobject import W_CodeObject

class W_FunctionType(W_Type):
    argtypes_w: list[W_Type]
    restype_w: W_Type

    def __init__(self, argtypes_w: list[W_Type], w_restype: W_Type):
        argnames = [w_t.name for w_t in argtypes_w]
        resname = w_restype.name
        args = ', '.join(argnames)
        sig = f'({args}) -> {resname}'
        super().__init__(f'fn {sig}', W_Function)
        self.argtypes_w = argtypes_w
        self.w_restype = w_restype


class W_Function(W_Object):
    w_functype: W_FunctionType
    w_code: W_CodeObject

    def __init__(self, w_functype: W_FunctionType, w_code: W_CodeObject) -> None:
        self.w_functype = w_functype
        self.w_code = w_code

    def __repr__(self) -> str:
        return f"<spy function '{self.w_code.name}'>"

    def spy_get_w_type(self, vm: SPyVM) -> W_Type:
        return self.w_functype
