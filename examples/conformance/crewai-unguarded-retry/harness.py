"""Drives crewAI's real ToolUsage retry/re-dispatch engine (unmocked) against
a tool whose side effect is real SQLite writes.

Uses crewai.tools.tool_usage.ToolUsage directly -- the exact class whose
`use()`/`_use()` catches a tool exception, increments `_run_attempts`, and
recursively re-invokes itself with the same ToolCalling (same arguments,
including the fixed logical_action_id) up to `_max_parsing_attempts`. This
is CrewAI's actual retry/re-dispatch mechanism, read from
crewai/tools/tool_usage.py (installed package, crewai==1.15.21) -- not a
simulation of it. No LLM call is needed to exercise this code path: the
ToolCalling is constructed directly, the same object shape the agent
executor would build after parsing a real LLM tool call.
"""

from __future__ import annotations

import os

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from crewai.tools.structured_tool import CrewStructuredTool
from crewai.tools.tool_calling import ToolCalling
from crewai.tools.tool_usage import ToolUsage


class _Action:
    def __init__(self, tool: str, tool_input: dict) -> None:
        self.tool = tool
        self.tool_input = tool_input


def run_tool_under_real_crewai_retry(func, logical_action_id: str, max_attempts: int = 3) -> dict:
    """Registers `func` as a CrewStructuredTool and drives it through
    crewAI's real ToolUsage dispatcher with a fixed logical_action_id.
    Returns {"outcome": ..., "run_attempts": int, "raw_result": str}."""

    structured_tool = CrewStructuredTool.from_function(
        func=func,
        name="unguarded_effect_tool",
        description="Applies a local effect keyed by logical_action_id.",
    )

    calling = ToolCalling(
        tool_name=structured_tool.name,
        arguments={"logical_action_id": logical_action_id},
    )

    usage = ToolUsage(
        tools_handler=None,  # no repeated-usage cache gate -- isolates the
                              # retry loop itself, not the unrelated
                              # loop-prevention heuristic
        tools=[structured_tool],
        task=None,
        function_calling_llm=None,
        agent=None,
        action=_Action(tool=structured_tool.name, tool_input={"logical_action_id": logical_action_id}),
    )
    usage._max_parsing_attempts = max_attempts

    tool_string = f"unguarded_effect_tool(logical_action_id={logical_action_id})"
    result = usage.use(calling=calling, tool_string=tool_string)

    return {
        "outcome": result,
        "run_attempts": usage._run_attempts,
        "last_failure": str(usage.last_failure) if usage.last_failure else None,
    }


def run_single_tool_call(func, tool_name: str, arguments: dict) -> dict:
    """Dispatches ONE real crewAI ToolUsage.use() call with the given
    `arguments` -- no outer retry loop.

    This is deliberately NOT `run_tool_under_real_crewai_retry`: that
    function exercises crewAI's own re-dispatch, which always resends the
    identical `ToolCalling` (same arguments) it was built with -- crewAI's
    engine has no code path that changes arguments between attempts.

    A model-regenerated retry (nsolland, crewAIInc/crewAI#7449, gap #4) is a
    *different* event: the outer agent loop sees a perceived failure, the
    LLM re-proposes the tool call, and the arguments it emits the second
    time are not guaranteed to match the first -- same `logical_action_id`
    (the caller-fixed field), different payload. That re-proposal happens
    above `ToolUsage`, so it is reproduced here as two independent calls to
    this function against the real `ToolUsage.use()` dispatcher, each with
    its own `arguments` dict -- not as two iterations of the retry loop
    above."""
    structured_tool = CrewStructuredTool.from_function(
        func=func,
        name=tool_name,
        description="Applies a local effect keyed by logical_action_id, "
        "with additional argument fields that may vary between calls.",
    )

    calling = ToolCalling(tool_name=structured_tool.name, arguments=arguments)

    usage = ToolUsage(
        tools_handler=None,
        tools=[structured_tool],
        task=None,
        function_calling_llm=None,
        agent=None,
        action=_Action(tool=structured_tool.name, tool_input=arguments),
    )
    usage._max_parsing_attempts = 1

    tool_string = f"{tool_name}({arguments})"
    result = usage.use(calling=calling, tool_string=tool_string)

    return {
        "outcome": result,
        "run_attempts": usage._run_attempts,
        "last_failure": str(usage.last_failure) if usage.last_failure else None,
    }


def run_tool_call_under_real_crewai_retry(
    func, tool_name: str, arguments: dict, max_attempts: int = 3
) -> dict:
    """Same as `run_tool_under_real_crewai_retry`, for a tool whose
    arguments carry more than `logical_action_id` (the idempotency-ref v1.1
    cases send the effect-bearing payload too). crewAI's own re-dispatch
    resends this exact `ToolCalling` on every attempt."""
    structured_tool = CrewStructuredTool.from_function(
        func=func,
        name=tool_name,
        description="Applies a local effect keyed by logical_action_id.",
    )

    calling = ToolCalling(tool_name=structured_tool.name, arguments=arguments)

    usage = ToolUsage(
        tools_handler=None,
        tools=[structured_tool],
        task=None,
        function_calling_llm=None,
        agent=None,
        action=_Action(tool=structured_tool.name, tool_input=arguments),
    )
    usage._max_parsing_attempts = max_attempts

    tool_string = f"{tool_name}({arguments})"
    result = usage.use(calling=calling, tool_string=tool_string)

    return {
        "outcome": result,
        "run_attempts": usage._run_attempts,
        "last_failure": str(usage.last_failure) if usage.last_failure else None,
    }
