from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.module import W_Module
from spy.vm.str import W_Str
from spy.vm.modules.types import W_TypeDef

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.primitive('def(v: type, i: type) -> dynamic')
def GETITEM(vm: 'SPyVM', w_vtype: W_Type, w_itype: W_Type) -> W_Object:
    return MM.lookup('[]', w_vtype, w_itype)


@OP.primitive('def(t: type, attr: str) -> dynamic')
def GETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str) -> W_Object:
    if w_type is W_Module._w:
        return OP.w_module_getattr
    return B.w_NotImplemented


@OP.primitive('def(t: type, attr: str, v: type) -> dynamic')
def SETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str,
            w_vtype: W_Type) -> W_Object:
    if w_type is W_Module._w:
        return OP.w_module_setattr
    elif w_type is B.w_dynamic:
        return OP.w_dynamic_setattr
    elif w_type is W_TypeDef._w:
        return OP.w_generic_setattr
    return B.w_NotImplemented
