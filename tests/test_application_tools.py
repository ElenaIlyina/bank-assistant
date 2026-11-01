import json
from types import SimpleNamespace

import pytest
from agents.tool_context import ToolContext

from app.agents import tools


async def invoke(tool, context, **args):
    data = json.dumps(args)
    wrapped = ToolContext(
        context=context,
        tool_name=tool.name,
        tool_call_id="call_1",
        tool_arguments=data,
    )
    return await tool.on_invoke_tool(wrapped, data)


async def test_check_uses_context_loan(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tools, "_loan",
        lambda ctx: SimpleNamespace(id=ctx.context.loan_id),
    )

    def check(loan_id, new_day):
        calls.append((loan_id, new_day))
        return {"allowed": True}

    monkeypatch.setattr(tools.applications, "check_payment_day", check)
    result = await invoke(
        tools.check_payment_date_change,
        tools.ClientContext(42),
        new_day=20,
    )
    assert result["allowed"] is True
    assert calls == [(42, 20)]


@pytest.mark.parametrize(
    "request_ids,expected_jobs",
    [
        (("request-1", "request-1"), 1),
        (("request-1", "request-2"), 2),
    ],
)
async def test_submission_keys(monkeypatch, request_ids, expected_jobs):
    saved = {}
    calls = []
    monkeypatch.setattr(
        tools, "_loan",
        lambda ctx: SimpleNamespace(id=ctx.context.loan_id),
    )

    async def create(loan_id, new_day, key):
        calls.append((loan_id, new_day, key))
        if key not in saved:
            saved[key] = {"id": f"job-{len(saved) + 1}", "status": "pending"}
        return saved[key]

    monkeypatch.setattr(
        tools.application_process, "create_payment_day", create
    )
    results = []
    for request_id in request_ids:
        context = tools.ClientContext(42, request_id=request_id)
        results.append(
            await invoke(
                tools.create_payment_date_application,
                context,
                new_day=20,
            )
        )
    assert len(saved) == expected_jobs
    assert len({result["job_id"] for result in results}) == expected_jobs
    assert len(calls) == 2
    assert all(call[:2] == (42, 20) for call in calls)


def test_application_tools_hide_context():
    for tool in (
        tools.check_payment_date_change,
        tools.create_payment_date_application,
    ):
        assert set(tool.params_json_schema["properties"]) == {"new_day"}

