"""Restricted boolean expression evaluator for rule-card conditions.

Security boundary: expressions are parsed with ``ast`` and walked against a
strict whitelist; they are interpreted by hand and never passed to
eval/exec/compile.
"""

import ast
import operator

Value = int | float | bool | None


class UnsafeExpression(ValueError):
    """Raised when an expression uses anything outside the whitelist."""


_CMP = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub}


def _reject(node: ast.AST) -> UnsafeExpression:
    return UnsafeExpression(f"disallowed expression element: {type(node).__name__}")


def _is_number(value: object) -> bool:
    return type(value) in (int, float)


def _check(node: ast.AST) -> None:
    if isinstance(node, ast.BoolOp):
        if type(node.op) not in (ast.And, ast.Or):
            raise _reject(node.op)
        for v in node.values:
            _check(v)
    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            _check(node.operand)
        elif (
            isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and _is_number(node.operand.value)
        ):
            return
        else:
            raise _reject(node.op)
    elif isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _CMP:
                raise _reject(op)
        _check(node.left)
        for c in node.comparators:
            _check(c)
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _BIN:
            raise _reject(node.op)
        _check(node.left)
        _check(node.right)
    elif isinstance(node, ast.Name):
        if not isinstance(node.ctx, ast.Load):
            raise _reject(node)
    elif isinstance(node, ast.Constant):
        if type(node.value) not in (int, float, bool):
            raise UnsafeExpression(
                f"disallowed constant type: {type(node.value).__name__}"
            )
    else:
        raise _reject(node)


def _parse(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError) as e:
        raise UnsafeExpression(f"invalid expression: {e}") from e
    _check(tree.body)
    if isinstance(tree.body, (ast.BinOp, ast.Constant, ast.UnaryOp)) and not (
        isinstance(tree.body, ast.UnaryOp) and isinstance(tree.body.op, ast.Not)
    ):
        if not (isinstance(tree.body, ast.Constant) and type(tree.body.value) is bool):
            raise UnsafeExpression("condition must be boolean")
    return tree


def names(expr: str) -> set[str]:
    tree = _parse(expr)
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _eval(node: ast.AST, env: dict[str, Value]):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval(node.operand, env)
        return -node.operand.value  # type: ignore[attr-defined]  # validated numeric Constant
    if isinstance(node, ast.BinOp):
        return _BIN[type(node.op)](_eval(node.left, env), _eval(node.right, env))
    if isinstance(node, ast.BoolOp):
        is_and = isinstance(node.op, ast.And)
        result = is_and
        for v in node.values:
            result = bool(_eval(v, env))
            if result != is_and:
                break
        return result
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, env)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    raise _reject(node)  # unreachable after validation


def evaluate(expr: str, inputs: dict[str, Value]) -> bool | None:
    tree = _parse(expr)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for name in used:
        if name in inputs:
            v = inputs[name]
            if v is not None and type(v) not in (int, float, bool):
                raise TypeError(
                    f"input {name!r} has unsupported type {type(v).__name__}"
                )
    if any(inputs.get(n) is None for n in used):
        return None
    result = _eval(tree.body, inputs)
    if not isinstance(result, bool):
        raise UnsafeExpression("condition must be boolean")
    return result
