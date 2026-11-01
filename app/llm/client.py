import asyncio
import time

from agents import (
    Agent,
    Runner,
    RunResult,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_configured = False


def setup_llm() -> None:
    global _configured
    if _configured:
        return
    client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
    )
    set_default_openai_client(client)
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)
    _configured = True


async def run_agent(agent: Agent, prompt: str | list, context=None) -> RunResult:
    setup_llm()
    started = time.monotonic()
    result = await asyncio.wait_for(
        Runner.run(agent, prompt, context=context, max_turns=settings.agent_max_turns),
        timeout=settings.agent_timeout_s,
    )
    tools = [i.raw_item.name for i in result.new_items if i.type == "tool_call_item"]
    log.info("agent_run", agent=agent.name, tools=tools, latency_ms=int((time.monotonic() - started) * 1000))
    return result
