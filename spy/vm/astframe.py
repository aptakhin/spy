from typing import TYPE_CHECKING, Any, Optional, NoReturn
from types import NoneType
from dataclasses import dataclass
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError, maybe_plural)
from spy.vm.builtins import B
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_Func, W_FuncType, W_ASTFunc, Namespace
from spy.vm import helpers
from spy.vm.typechecker import TypeChecker
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class Return(Exception):
    w_value: W_Object

    def __init__(self, w_value: W_Object) -> None:
        self.w_value = w_value



@dataclass
class FrameVal:
    """
    Small wrapper around W_Object which also keeps track of its static type.
    The naming convention is to call them fv_*.
    """
    w_static_type: W_Type
    w_value: W_Object


class ASTFrame:
    vm: 'SPyVM'
    w_func: W_ASTFunc
    funcdef: ast.FuncDef
    locals: Namespace
    t: TypeChecker

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        assert isinstance(w_func, W_ASTFunc)
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.locals = {}
        self.t = TypeChecker(vm, self.w_func.funcdef)

    def __repr__(self) -> str:
        return f'<ASTFrame for {self.w_func.fqn}>'

    def declare_local(self, name: str, w_type: W_Type) -> None:
        assert name not in self.locals, f'variable already declared: {name}'
        self.t.declare_local(name, w_type)
        self.locals[name] = None

    def store_local(self, got_loc: Loc, name: str, w_value: W_Object) -> None:
        self.t.typecheck_local(got_loc, name, w_value)
        self.locals[name] = w_value

    def load_local(self, name: str) -> W_Object:
        assert name in self.locals
        w_obj = self.locals[name]
        if w_obj is None:
            raise SPyRuntimeError('read from uninitialized local')
        return w_obj

    def run(self, args_w: list[W_Object]) -> W_Object:
        self.init_arguments(args_w)
        try:
            for stmt in self.funcdef.body:
                self.exec_stmt(stmt)
            #
            # we reached the end of the function. If it's void, we can return
            # None, else it's an error.
            if self.w_func.w_functype.w_restype is B.w_void:
                return B.w_None
            else:
                loc = self.w_func.funcdef.loc.make_end_loc()
                msg = 'reached the end of the function without a `return`'
                raise SPyTypeError.simple(msg, 'no return', loc)

        except Return as e:
            return e.w_value

    def init_arguments(self, args_w: list[W_Object]) -> None:
        """
        - declare the local vars for the arguments and @return
        - store the arguments in args_w in the appropriate local var
        """
        w_functype = self.w_func.w_functype
        self.declare_local('@return', w_functype.w_restype)
        #
        params = self.w_func.w_functype.params
        arglocs = [arg.loc for arg in self.funcdef.args]
        for loc, param, w_arg in zip(arglocs, params, args_w, strict=True):
            self.declare_local(param.name, param.w_type)
            self.store_local(loc, param.name, w_arg)

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        return magic_dispatch(self, 'exec_stmt', stmt)

    def eval_expr(self, expr: ast.Expr) -> FrameVal:
        """
        Typecheck and eval the given expr.

        Every concrete implementation of this MUST call the corresponding
        self.t.check_*
        """
        return magic_dispatch(self, 'eval_expr', expr)

    def eval_expr_object(self, expr: ast.Expr) -> W_Object:
        fv = self.eval_expr(expr)
        return fv.w_value

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        fv = self.eval_expr(expr)
        if isinstance(fv.w_value, W_Type):
            assert fv.w_static_type is B.w_type
            return fv.w_value
        w_valtype = self.vm.dynamic_type(fv.w_value)
        msg = f'expected `type`, got `{w_valtype.name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Return(self, stmt: ast.Return) -> None:
        fv = self.eval_expr(stmt.value)
        self.t.typecheck_local(stmt.loc, '@return', fv.w_value)
        raise Return(fv.w_value)

    def exec_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # evaluate the functype
        d = {}
        for arg in funcdef.args:
            d[arg.name] = self.eval_expr_type(arg.type)
        w_restype = self.eval_expr_type(funcdef.return_type)
        w_functype = W_FuncType.make(
            color = funcdef.color,
            w_restype = w_restype,
            **d)
        #
        # create the w_func
        fqn = FQN(modname='???', attr=funcdef.name)
        # XXX we should capture only the names actually used in the inner func
        closure = self.w_func.closure + (self.locals,)
        w_func = W_ASTFunc(fqn, closure, w_functype, funcdef)
        #
        # store it in the locals
        self.declare_local(funcdef.name, w_func.w_functype)
        self.store_local(funcdef.loc, funcdef.name, w_func)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        sym = self.funcdef.symtable.lookup(vardef.name)
        assert sym.is_local
        assert vardef.value is not None, 'WIP?'
        w_type = self.eval_expr_type(vardef.type)
        self.declare_local(vardef.name, w_type)
        w_value = self.eval_expr_object(vardef.value)
        self.store_local(vardef.value.loc, vardef.name, w_value)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        # XXX this looks wrong. We need to add an AST field to keep track of
        # which scope we want to assign to. For now we just assume that if
        # it's not local, it's module.
        name = assign.target
        sym = self.funcdef.symtable.lookup(name)
        fv = self.eval_expr(assign.value)
        if sym.is_local:
            if name not in self.locals:
                # first assignment, implicit declaration
                self.declare_local(name, fv.w_static_type)
            self.store_local(assign.value.loc, name, fv.w_value)
        elif sym.fqn is not None:
            self.vm.store_global(sym.fqn, fv.w_value)
        else:
            assert False, 'closures not implemented yet'

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> FrameVal:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        w_type = self.t.check_expr_Constant(const)
        w_value = self.vm.wrap(const.value)
        return FrameVal(w_type, w_value)

    def eval_expr_Name(self, name: ast.Name) -> FrameVal:
        w_type = self.t.check_expr_Name(name)
        sym = self.w_func.funcdef.symtable.lookup(name.id)
        if sym.is_local:
            w_value = self.load_local(name.id)
            return FrameVal(w_type, w_value)
        elif sym.fqn is not None:
            w_value2 = self.vm.lookup_global(sym.fqn)
            assert w_value2 is not None, \
                f'{sym.fqn} not found. Bug in the ScopeAnalyzer?'
            return FrameVal(w_type, w_value2)
        else:
            assert False, 'closures not implemented yet'

    def eval_expr_BinOp(self, binop: ast.BinOp) -> FrameVal:
        self.t.check_expr_BinOp(binop)
        fv_l = self.eval_expr(binop.left)
        fv_r = self.eval_expr(binop.right)
        w_ltype = fv_l.w_static_type
        w_rtype = fv_r.w_static_type
        if w_ltype is B.w_i32 and w_rtype is B.w_i32:
            l = self.vm.unwrap(fv_l.w_value)
            r = self.vm.unwrap(fv_r.w_value)
            if binop.op == '+':
                return FrameVal(B.w_i32, self.vm.wrap(l + r))
            elif binop.op == '*':
                return FrameVal(B.w_i32, self.vm.wrap(l * r))
        #
        assert False, 'Unsupported binop, bug in the typechecker'

    eval_expr_Add = eval_expr_BinOp
    eval_expr_Mul = eval_expr_BinOp

    def eval_expr_Call(self, call: ast.Call) -> FrameVal:
        w_restype = self.t.check_expr_Call(call)
        fv_func = self.eval_expr(call.func)
        w_func = fv_func.w_value
        assert isinstance(w_func, W_Func)
        args_w = [self.eval_expr_object(arg) for arg in call.args]
        w_res = self.vm.call_function(w_func, args_w)
        return FrameVal(w_restype, w_res)
