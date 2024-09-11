from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type, W_Dynamic
from spy.vm.opimpl import W_OpImpl, W_AbsVal

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin(color='blue')
def GETITEM(vm: 'SPyVM', wav_obj: W_AbsVal, wav_i: W_AbsVal) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    pyclass = wav_obj.w_static_type.pyclass
    if pyclass.has_meth_overriden('op_GETITEM'):
        w_opimpl = pyclass.op_GETITEM(vm, wav_obj, wav_i)

    typecheck_opimpl(
        vm,
        w_opimpl,
        [wav_obj, wav_i],
        dispatch = 'single',
        errmsg = 'cannot do `{0}`[...]'
    )
    return w_opimpl


@OP.builtin(color='blue')
def SETITEM(vm: 'SPyVM', w_type: W_Type, w_itype: W_Type,
            w_vtype: W_Type) -> W_Dynamic:
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_SETITEM'):
        return pyclass.op_SETITEM(vm, w_type, w_itype, w_vtype)

    return W_OpImpl.NULL
