import pytest

from uai_forge.models import ToolBinding
from uai_forge.tools import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_accepts_arithmetic_without_eval():
    tool = CalculatorTool(ToolBinding(plugin_id="tool.calculator"))
    result = await tool.invoke({"expression": "(7 + 5) * 3"}, {})
    assert result["result"] == 36


@pytest.mark.asyncio
async def test_calculator_rejects_code_execution():
    tool = CalculatorTool(ToolBinding(plugin_id="tool.calculator"))
    with pytest.raises(ValueError):
        await tool.invoke({"expression": "__import__('os').getcwd()"}, {})
