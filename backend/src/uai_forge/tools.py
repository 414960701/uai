"""Small, safe reference tools used by the demo and compatibility tests."""

from __future__ import annotations

import ast
import operator
from datetime import datetime, timezone
from typing import Any, Dict

from .models import PluginKind, PluginManifest, ToolBinding
from .ports import ToolPlugin


CALCULATOR_MANIFEST = PluginManifest(
    id="tool.calculator",
    kind=PluginKind.TOOL,
    display_name="Safe calculator",
    version="1.0.0",
    description="Evaluates bounded arithmetic expressions without eval().",
    capabilities=["read_only", "idempotent", "concurrency_safe"],
    config_schema={"type": "object", "additionalProperties": False},
)

ECHO_MANIFEST = PluginManifest(
    id="tool.echo",
    kind=PluginKind.TOOL,
    display_name="Echo",
    version="1.0.0",
    description="Returns structured input for tool and middleware testing.",
    capabilities=["read_only", "idempotent", "concurrency_safe"],
    config_schema={"type": "object", "additionalProperties": True},
)

UTC_NOW_MANIFEST = PluginManifest(
    id="tool.utc_now",
    kind=PluginKind.TOOL,
    display_name="UTC clock",
    version="1.0.0",
    description="Returns the current UTC time.",
    capabilities=["read_only", "concurrency_safe"],
    config_schema={"type": "object", "additionalProperties": False},
)


class CalculatorTool(ToolPlugin):
    manifest = CALCULATOR_MANIFEST
    name = "calculator"
    description = "Evaluate a basic arithmetic expression."
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string", "maxLength": 500}},
        "required": ["expression"],
        "additionalProperties": False,
    }
    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(self, binding: ToolBinding) -> None:
        self.binding = binding

    def _evaluate(self, node: ast.AST, depth: int = 0) -> float:
        if depth > 20:
            raise ValueError("expression is too deeply nested")
        if isinstance(node, ast.Expression):
            return self._evaluate(node.body, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if abs(float(node.value)) > 1e100:
                raise ValueError("number is outside the allowed range")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._operators:
            left = self._evaluate(node.left, depth + 1)
            right = self._evaluate(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(float(right)) > 12:
                raise ValueError("exponent is outside the allowed range")
            return self._operators[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._operators:
            return self._operators[type(node.op)](self._evaluate(node.operand, depth + 1))
        raise ValueError("only basic arithmetic is supported")

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        expression = str(arguments.get("expression", ""))[:500]
        tree = ast.parse(expression, mode="eval")
        return {"expression": expression, "result": self._evaluate(tree)}


class EchoTool(ToolPlugin):
    manifest = ECHO_MANIFEST
    name = "echo"
    description = "Echo a value as a structured tool result."
    parameters = {
        "type": "object",
        "properties": {"input": {}},
        "required": ["input"],
        "additionalProperties": False,
    }

    def __init__(self, binding: ToolBinding) -> None:
        self.binding = binding

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        return {"input": arguments.get("input"), "agent_id": context.get("agent_id")}


class UtcNowTool(ToolPlugin):
    manifest = UTC_NOW_MANIFEST
    name = "utc_now"
    description = "Return the current time in UTC."
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, binding: ToolBinding) -> None:
        self.binding = binding

    async def invoke(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        return {"utc": datetime.now(timezone.utc).isoformat()}


def create_calculator(binding: ToolBinding) -> ToolPlugin:
    return CalculatorTool(binding)


def create_echo(binding: ToolBinding) -> ToolPlugin:
    return EchoTool(binding)


def create_utc_now(binding: ToolBinding) -> ToolPlugin:
    return UtcNowTool(binding)
