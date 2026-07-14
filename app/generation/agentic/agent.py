"""The estimation agent: a hand-driven reason -> act -> observe loop (Session 12).

The loop is driven manually on purpose. We do NOT delegate the tool chaining to
the Responses API's built-in agentic behaviour, because capturing every step is
half the exercise: each iteration is recorded in an ordered trace.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from uuid import uuid4

import structlog
from openai import AsyncOpenAI

from app.generation.agentic.agent_tools import (
    TOOL_DEFINITIONS,
    calculate_estimate,
    search_budgets,
)
from app.generation.agentic.schemas import (
    AgentEstimate,
    AgentRunResult,
    EstimatedComponent,
    TraceStep,
)
from embedding_pipeline.persistence import DocumentRepository

logger = structlog.get_logger()

AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-5")
REASONING_EFFORT = "medium"

# Hard cap so a model that keeps searching cannot loop forever.
MAX_ITERATIONS = 10


SYSTEM_PROMPT = """You are a senior software estimation agent.

You receive the transcript of a client discovery meeting (it may be written in
Spanish) and must produce an effort estimate grounded in historical budgets.

Method — follow it in order:

1. Decompose the transcript into the distinct components that must be estimated.
   A component is a separable piece of work (for example: a business backend, an
   ERP integration, a mobile app, an analytics dashboard). Ignore scheduling,
   pleasantries and commercial chatter.

2. For EACH component, call search_budgets once with a focused, self-contained
   description of that component. The historical budget corpus is written in
   English, so write your search queries in English even when the transcript is
   in Spanish. If a search returns nothing useful, rephrase the query and search
   again before giving up on that component.

3. From the retrieved items, keep only the reference_amount values that genuinely
   match the component. Discard items from a clearly unrelated domain, even if the
   search returned them.

4. Once you have references for every component, call calculate_estimate a single
   time with all the components and their reference_amounts. It takes the median
   of the references, adds a contingency buffer and returns the breakdown and the
   total. It is your only source of numbers.

5. If calculate_estimate flags a component as unbudgeted (no references), search
   again for it with different wording and recalculate. If it is still unbudgeted,
   say so explicitly instead of inventing a figure.

6. Finish with a short written summary for the client: the components you
   estimated, what the numbers are based on, and any component that could not be
   grounded in a historical budget.

Rules:
- Never state hours you computed yourself. Every figure must come from
  calculate_estimate.
- One search_budgets call per component. Never pass the whole transcript as a query.
- Do not ask the user questions: work with what the transcript says.
"""


class EstimationAgent:
    """Drives the reason -> act -> observe loop over the two tools."""

    def __init__(self, repository: DocumentRepository, model: str = AGENT_MODEL):
        self.repository = repository
        self.client = AsyncOpenAI()
        self.model = model

    async def run(self, transcript: str, request_id: str | None = None) -> AgentRunResult:
        """Run the agent over a meeting transcript.

        Returns the structured estimate (built from the deterministic
        calculate_estimate result) plus the ordered reasoning trace.
        """
        request_id = request_id or str(uuid4())
        start_time = time.time()

        trace: list[TraceStep] = []
        last_calculation: dict[str, Any] | None = None
        iterations = 0

        logger.info(
            "agent_started",
            request_id=request_id,
            model=self.model,
            transcript_chars=len(transcript),
        )

        response = await self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=transcript,
            tools=TOOL_DEFINITIONS,
            reasoning={"effort": REASONING_EFFORT, "summary": "auto"},
        )

        for iterations in range(1, MAX_ITERATIONS + 1):
            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]

            # No tool calls left: the model produced its final answer.
            if not function_calls:
                break

            # The reasoning summary belongs to this turn as a whole; attach it to
            # the first step produced by the turn.
            turn_reasoning = self._extract_reasoning(response)

            tool_outputs: list[dict[str, Any]] = []
            for call in function_calls:
                arguments = json.loads(call.arguments)
                result = await self._execute_tool(call.name, arguments)

                if call.name == "calculate_estimate":
                    last_calculation = result

                trace.append(
                    TraceStep(
                        step=len(trace) + 1,
                        turn=iterations,
                        reasoning=turn_reasoning,
                        action=self._format_action(call.name, arguments),
                        observation=result.get("summary", ""),
                    )
                )
                turn_reasoning = None

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            logger.info(
                "agent_iteration",
                request_id=request_id,
                iteration=iterations,
                tool_calls=[call.name for call in function_calls],
            )

            # Chain the turn: previous_response_id carries the reasoning items
            # forward; we only send back the tool outputs.
            response = await self.client.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=TOOL_DEFINITIONS,
                reasoning={"effort": REASONING_EFFORT, "summary": "auto"},
            )

        final_message = response.output_text or ""
        estimate = self._build_estimate(last_calculation, final_message)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            "agent_completed",
            request_id=request_id,
            iterations=iterations,
            trace_steps=len(trace),
            total_hours=estimate.total_hours if estimate else None,
            elapsed_ms=elapsed_ms,
        )

        return AgentRunResult(
            estimate=estimate,
            trace=trace,
            iterations=iterations,
            request_id=request_id,
        )

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call to its implementation."""
        if name == "search_budgets":
            return await search_budgets(arguments, self.repository)
        if name == "calculate_estimate":
            return calculate_estimate(arguments)

        logger.error("agent_unknown_tool", tool=name)
        return {"error": f"unknown tool: {name}", "summary": f"unknown tool: {name}"}

    @staticmethod
    def _extract_reasoning(response: Any) -> str | None:
        """Collect the reasoning summaries the model emitted for this turn."""
        summaries: list[str] = []
        for item in response.output:
            if item.type != "reasoning":
                continue
            for part in getattr(item, "summary", None) or []:
                text = getattr(part, "text", None)
                if text:
                    summaries.append(text)
        return "\n".join(summaries) if summaries else None

    @staticmethod
    def _format_action(name: str, arguments: dict[str, Any]) -> str:
        """Render a tool call the way it appears in the trace."""
        rendered = ", ".join(
            f"{key}={json.dumps(value, ensure_ascii=False)}"
            for key, value in arguments.items()
        )
        return f"{name}({rendered})"

    @staticmethod
    def _build_estimate(
        last_calculation: dict[str, Any] | None,
        final_message: str,
    ) -> AgentEstimate | None:
        """Assemble the structured estimate.

        Figures come from the last calculate_estimate result, never from the
        model's prose: the LLM only supplies the narrative summary.
        """
        if last_calculation is None:
            return None

        return AgentEstimate(
            components=[
                EstimatedComponent(**component)
                for component in last_calculation["components"]
            ],
            total_hours=last_calculation["total_hours"],
            summary=final_message,
        )


def format_trace(result: AgentRunResult) -> str:
    """Render the trace in the console format required by the exercise.

    A turn can issue several tool calls in parallel. Those calls share the turn's
    reasoning, which is carried by the first of them; the rest are labelled as
    parallel calls so they are not mistaken for a turn where the model emitted no
    reasoning summary at all.
    """
    reasoning_step_of_turn: dict[int, int] = {}
    for step in result.trace:
        if step.reasoning and step.turn not in reasoning_step_of_turn:
            reasoning_step_of_turn[step.turn] = step.step

    lines: list[str] = []
    for step in result.trace:
        if step.reasoning:
            reasoning = step.reasoning
        elif step.turn in reasoning_step_of_turn:
            origin = reasoning_step_of_turn[step.turn]
            reasoning = f"(parallel call in the same turn as STEP {origin})"
        else:
            reasoning = "(model emitted no reasoning summary for this turn)"

        indented_reasoning = reasoning.replace("\n", "\n               ")

        lines.append(f"STEP {step.step} (turn {step.turn})")
        lines.append(f"  reasoning:   {indented_reasoning}")
        lines.append(f"  action:      {step.action}")
        lines.append(f"  observation: {step.observation}")
        lines.append("")
    return "\n".join(lines)
