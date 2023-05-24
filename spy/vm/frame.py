from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, W_i32
from spy.vm.codeobject import W_CodeObject

class BytecodeError(Exception):
    pass

class Frame:
    vm: SPyVM
    w_code: W_CodeObject
    pc: int  # program counter
    stack: list[W_Object]
    locals_w: dict[str, W_Object]

    def __init__(self, vm: SPyVM, w_code: W_Object) -> None:
        assert isinstance(w_code, W_CodeObject)
        self.vm = vm
        self.w_code = w_code
        self.pc = 0
        self.stack = []
        self.locals_w = {}

    def push(self, w_value: W_Object) -> None:
        assert isinstance(w_value, W_Object)
        self.stack.append(w_value)

    def pop(self) -> W_Object:
        return self.stack.pop()

    def init_locals(self) -> None:
        for varname, w_type in self.w_code.locals_w_types.items():
            # for now we know how to initialize only i32 local vars. We need
            # to think of a more generic way
            assert w_type is self.vm.builtins.w_i32
            self.locals_w[varname] = W_i32(0)

    def run(self) -> W_Object:
        self.init_locals()
        while True:
            op = self.w_code.body[self.pc]
            # 'return' is special, handle it explicitly
            if op.name == 'return':
                ## if len(self.stack) != 1:
                ##     raise BytecodeError(f'Unexpected stack length: {len(self.stack)}')
                return self.pop()
            else:
                meth_name = f'op_{op.name}'
                meth = getattr(self, meth_name, None)
                if meth is None:
                    raise NotImplementedError(meth_name)
                meth(*op.args)
                self.pc += 1

    def op_i32_const(self, w_const: W_Object) -> None:
        assert isinstance(w_const, W_i32)
        self.push(w_const)

    def op_i32_add(self) -> None:
        w_b = self.pop()
        w_a = self.pop()
        assert isinstance(w_a, W_i32)
        assert isinstance(w_b, W_i32)
        a = self.vm.unwrap(w_a)
        b = self.vm.unwrap(w_b)
        w_c = self.vm.wrap(a + b)
        self.push(w_c)

    def op_local_get(self, varname: str) -> None:
        w_value = self.locals_w[varname]
        self.push(w_value)

    def op_local_set(self, varname: str) -> None:
        w_type = self.w_code.locals_w_types[varname]
        pyclass = self.vm.unwrap(w_type)
        w_value = self.pop()
        assert isinstance(w_value, pyclass)
        self.locals_w[varname] = w_value
