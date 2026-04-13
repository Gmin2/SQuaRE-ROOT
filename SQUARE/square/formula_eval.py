"""Restricted evaluation of YAML formulas (e.g. in ``n`` or ``d``) with ``log2``."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Mapping
from typing import Any


class FormulaEvalError(ValueError):
    """Raised when a formula cannot be evaluated safely."""


_ALLOWED_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARY: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def eval_numeric_formula(expression: str, n: float) -> float:
    """
    Evaluate a numeric expression in ``n`` using ``+ - * / // % **`` and ``log2(expr)``.

    :param expression: Source string from YAML (e.g. ``\"3 * n + 0.002 * n * log2(n)\"``).
    :param n: Modulus bit length (positive number).
    :returns: Floating-point result.
    :raises FormulaEvalError: if parsing fails or the expression uses disallowed constructs.
    """
    if n <= 0:
        raise FormulaEvalError("n must be positive")
    return eval_numeric_formula_with_bindings(expression, {"n": float(n)})


def eval_numeric_formula_with_bindings(expression: str, bindings: Mapping[str, float]) -> float:
    """
    Evaluate a numeric expression using only names present in ``bindings`` plus ``log2``.

    Typical keys: ``\"n\"`` (modulus bits) for algorithm YAML, ``\"d\"`` (code distance) for QEC YAML.

    :param expression: Source string from YAML.
    :param bindings: Map of allowed variable names to positive numeric values (must be > 0 for each).
    :returns: Floating-point result.
    :raises FormulaEvalError: if parsing fails or the expression uses disallowed constructs.
    """
    if not bindings:
        raise FormulaEvalError("bindings must be non-empty")
    for name, val in bindings.items():
        if val <= 0:
            raise FormulaEvalError(f"binding {name!r} must be positive")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - covered via FormulaEvalError path
        raise FormulaEvalError(str(exc)) from exc

    allowed = frozenset(bindings)

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise FormulaEvalError("Only numeric constants are allowed")
        if isinstance(node, ast.Name):
            if node.id in allowed:
                return float(bindings[node.id])
            raise FormulaEvalError(f"Disallowed name: {node.id!r}")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _ALLOWED_BINOPS:
                raise FormulaEvalError(f"Disallowed binary operator: {op_type.__name__}")
            left = _eval(node.left)
            right = _eval(node.right)
            return float(_ALLOWED_BINOPS[op_type](left, right))
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _ALLOWED_UNARY:
                raise FormulaEvalError(f"Disallowed unary operator: {op_type.__name__}")
            return float(_ALLOWED_UNARY[op_type](_eval(node.operand)))
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "log2"
                and len(node.args) == 1
                and not node.keywords
            ):
                arg = _eval(node.args[0])
                if arg <= 0:
                    raise FormulaEvalError("log2 argument must be positive")
                return float(math.log2(arg))
            raise FormulaEvalError("Only log2(...) calls are allowed")
        raise FormulaEvalError(f"Disallowed syntax: {type(node).__name__}")

    return _eval(tree)
