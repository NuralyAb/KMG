"""Расчёт формулы из спецификации без доступа к Python: только арифметика, параметры и несколько функций."""

import ast
import math
import operator
from collections.abc import Mapping

OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}
FUNCTIONS = {"exp": math.exp, "log": math.log, "log10": math.log10, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos}
MAX_POWER = 50
MAX_LENGTH = 200


def evaluate(formula: str, values: Mapping[str, float]) -> float:
    if len(formula) > MAX_LENGTH:
        raise ValueError("формула слишком длинная")
    try:
        result = _walk(ast.parse(formula.replace("^", "**"), mode="eval").body, values)
    except (SyntaxError, ArithmeticError, TypeError, RecursionError) as error:
        raise ValueError(f"формула не считается: {error}") from error
    if isinstance(result, complex) or not math.isfinite(result):
        raise ValueError("значение не число")
    return float(result)


def _walk(node: ast.AST, values: Mapping[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in values:
        return float(values[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_walk(node.operand, values)
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left, right = _walk(node.left, values), _walk(node.right, values)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER:
            raise ValueError("слишком большая степень")
        return OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and len(node.args) == 1 and not node.keywords:
        return FUNCTIONS[node.func.id](_walk(node.args[0], values))
    raise ValueError(f"в формуле нельзя {type(node).__name__}")
