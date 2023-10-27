from typing import Any, Optional
from dataclasses import dataclass
import fixedint
from spy.fqn import FQN
from spy.errors import SPyLookupError
from spy import libspy
from spy.vm.object import W_Object, W_Type, W_void, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.function import (W_FunctionType, W_Function, W_UserFunction,
                             W_BuiltinFunction)
from spy.vm.module import W_Module
from spy.vm.codeobject import W_CodeObject
from spy.vm.frame import Frame
from spy.vm import testmod


class Builtins:
    w_object = W_Object._w
    w_type = W_Type._w
    w_i32 = W_i32._w
    w_bool = W_bool._w
    w_void = W_void._w
    w_str = W_str._w
    w_None = W_void._w_singleton
    w_True = W_bool._w_singleton_True
    w_False = W_bool._w_singleton_False

    w_abs = W_BuiltinFunction(
        name = 'abs',
        llname = 'spy_abs',
        w_functype = W_FunctionType.make(x=w_i32, w_restype=w_i32),
    )

    @classmethod
    def lookup(cls, name: str) -> Optional[W_Object]:
        attr = 'w_' + name
        return getattr(cls, attr, None)


class SPyVM:
    """
    A Virtual Machine to execute SPy code.

    Each instance of the VM contains an instance of libspy.wasm: all the
    non-scalar objects (e.g. strings) are stored in the WASM linear memory.
    """
    ll: libspy.LLSPyInstance
    globals_types: dict[FQN, W_Type]
    globals_w: dict[FQN, W_Object]
    modules_w: dict[str, W_Module]

    def __init__(self) -> None:
        self.ll = libspy.LLSPyInstance(libspy.LLMOD)
        self.globals_types = {}
        self.globals_w = {}
        self.modules_w = {}
        #self.modules_w['testmod'] = testmod.make(self)

    def register_module(self, w_mod: W_Module) -> None:
        assert w_mod.name not in self.modules_w
        self.modules_w[w_mod.name] = w_mod

    def add_global(self, name: FQN, w_type: W_Type, w_value: W_Object) -> None:
        assert name.modname in self.modules_w
        assert name not in self.globals_w
        assert name not in self.globals_types
        if w_type is None:
            w_type = self.dynamic_type(w_value)
        else:
            assert self.is_compatible_type(w_value, w_type)
        self.globals_types[name] = w_type
        self.globals_w[name] = w_value

    def lookup_global_type(self, fqn: FQN) -> Optional[W_Type]:
        return self.globals_types.get(fqn)

    def lookup_global(self, fqn: FQN) -> Optional[W_Object]:
        return self.globals_w.get(fqn)

    def dynamic_type(self, w_obj: W_Object) -> W_Type:
        assert isinstance(w_obj, W_Object)
        return w_obj.spy_get_w_type(self)

    def issubclass(self, w_sub: W_Type, w_super: W_Type) -> bool:
        assert isinstance(w_super, W_Type)
        assert isinstance(w_sub, W_Type)
        w_class = w_sub
        while w_class is not Builtins.w_None:
            if w_class is w_super:
                return True
            w_class = w_class.w_base  # type:ignore
        return False

    def is_True(self, w_obj: W_bool) -> bool:
        return w_obj is Builtins.w_True

    def is_False(self, w_obj: W_bool) -> bool:
        return w_obj is Builtins.w_False

    def wrap(self, value: Any) -> W_Object:
        """
        Useful for tests: magic funtion which wraps the given inter-level object
        into the most appropriate app-level W_* object.
        """
        T = type(value)
        if value is None:
            return Builtins.w_None
        elif T in (int, fixedint.Int32):
            return W_i32(value)
        elif T is bool:
            if value:
                return Builtins.w_True
            else:
                return Builtins.w_False
        elif T is str:
            return W_str(self, value)
        elif isinstance(value, type) and issubclass(value, W_Object):
            return value._w
        raise Exception(f"Cannot wrap interp-level objects of type {value.__class__.__name__}")

    def unwrap(self, w_value: W_Object) -> Any:
        """
        Useful for tests: magic funtion which wraps the given app-level w_ object
        into the most appropriate inter-level object. Opposite of wrap().
        """
        assert isinstance(w_value, W_Object)
        return w_value.spy_unwrap(self)

    def unwrap_i32(self, w_value: W_Object) -> Any:
        if not isinstance(w_value, W_i32):
            raise Exception('Type mismatch')
        return w_value.value

    def make_function(self, w_code: W_CodeObject, w_mod: W_Module) -> W_UserFunction:
        """
        Create a function inside a module
        """
        w_func = W_UserFunction(w_code, w_mod.content)
        w_mod.add(w_code.name, w_func, w_type=None)
        return w_func

    def is_compatible_type(self, w_arg: W_Object, w_type: W_Type) -> bool:
        # XXX: this check is wrong: we should define better what it means to
        # be "compatible", but we don't have this notion yet
        return self.dynamic_type(w_arg) is w_type

    def call_function(self, w_func: W_Function, args_w: list[W_Object]) -> W_Object:
        w_functype = w_func.w_functype
        assert len(w_functype.params) == len(args_w)
        for param, w_arg in zip(w_functype.params, args_w):
            assert self.is_compatible_type(w_arg, param.w_type)
        #
        if isinstance(w_func, W_UserFunction):
            frame = Frame(self, w_func.w_code)
            return frame.run(args_w)
        elif isinstance(w_func, W_BuiltinFunction):
            return w_func.spy_call(self, args_w)
        else:
            assert False
