import asyncio
import logging
import os
from unittest.mock import AsyncMock

import pytest
from agent_framework import SupportsChatGetResponse
from copilot import CopilotClient

from app import main
from app.config import Settings
from app.copilot_client import CopilotStructuredChatClient

pytestmark = pytest.mark.unit


@pytest.fixture
def boundaries(monkeypatch: pytest.MonkeyPatch):
    events = []
    runtime = AsyncMock()
    runtime.start.side_effect = lambda: events.append("sdk_start")
    runtime.stop.side_effect = lambda: events.append("sdk_stop")
    runtime.force_stop.side_effect = lambda: events.append("sdk_force_stop")
    tool = AsyncMock()
    tool.__aenter__.side_effect = lambda: events.append("mcp_enter")
    tool.__aexit__.side_effect = lambda *_args: events.append("mcp_exit")
    data_source = object()
    options = []
    runners = []

    def runtime_factory(**kwargs):
        options.append(kwargs)
        return runtime

    monkeypatch.setattr(main, "CopilotClient", runtime_factory)
    monkeypatch.setattr(main.McpLunchDataSource, "create", lambda _url: (tool, data_source))
    monkeypatch.setattr(main, "add_agent_framework_fastapi_endpoint", lambda _app, runner, *_a, **_k: runners.append(runner))
    return runtime, tool, data_source, options, events, runners


@pytest.mark.parametrize("mode", ["local", "pat"])
async def test_authentication_isolation_and_normal_cleanup(mode, boundaries, monkeypatch):
    runtime, tool, data_source, options, events, runners = boundaries
    for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.setenv(name, "fake-ambient-token")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    monkeypatch.setenv("HOME", "test-home")
    monkeypatch.setenv("USERPROFILE", "test-profile")
    settings = Settings(
        _env_file=None, copilot_auth_mode=mode, copilot_model="test-model",
        copilot_github_token="fake-explicit-token",
    )
    parent_env = dict(os.environ)
    app = main.create_app(settings=settings)
    runtime.start.assert_not_awaited()
    assert not options
    assert runners[0]._data_source is data_source
    assert isinstance(runners[0]._chat_client, SupportsChatGetResponse)
    with pytest.raises(RuntimeError, match="Copilot runtime is not running"):
        runners[0]._chat_client.get_response([])
    async with app.router.lifespan_context(app):
        assert options[0]["mode"] == ("copilot-cli" if mode == "local" else "empty")
        assert options[0]["base_directory"] is None if mode == "local" else options[0]["base_directory"].endswith(".copilot-runtime")
        assert options[0]["use_logged_in_user"] is (mode == "local")
        assert options[0]["github_token"] == (None if mode == "local" else "fake-explicit-token")
        assert options[0]["log_level"] == "none"
        assert not any(name.upper() in {"COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"} for name in options[0]["env"])
        for name in ("PATH", "HOME", "USERPROFILE"):
            assert options[0]["env"][name] == parent_env[name]
        assert dict(os.environ) == parent_env
        assert isinstance(runners[0]._chat_client.client, CopilotStructuredChatClient)
        assert runners[0]._chat_client.client._model == "test-model"
        assert events == ["sdk_start", "mcp_enter"]
    assert events == ["sdk_start", "mcp_enter", "mcp_exit", "sdk_stop"]
    assert runners[0]._chat_client.client is None
    runtime.force_stop.assert_not_awaited()


@pytest.mark.parametrize("injected", ["both", "data", "chat"])
async def test_injection_seams_cleanup_only_owned_resources(injected, boundaries):
    runtime, tool, source, options, events, runners = boundaries
    chat = object()
    kwargs = {}
    if injected in ("both", "data"):
        kwargs["data_source"] = source
    if injected in ("both", "chat"):
        kwargs["chat_client"] = chat
    app = main.create_app(settings=Settings(_env_file=None), **kwargs)
    async with app.router.lifespan_context(app):
        pass
    assert runtime.start.await_count == (injected != "both" and injected != "chat")
    assert runtime.stop.await_count == runtime.start.await_count
    assert tool.__aenter__.await_count == (injected == "chat")
    assert tool.__aexit__.await_count == tool.__aenter__.await_count
    if injected in ("both", "chat"):
        assert runners[0]._chat_client is chat


async def test_fully_injected_app_does_not_read_settings(boundaries, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: pytest.fail("settings should not be read"))
    app = main.create_app(data_source=object(), chat_client=object())
    async with app.router.lifespan_context(app):
        pass
    assert not boundaries[3]


@pytest.mark.parametrize("failed", ["sdk", "mcp"])
async def test_partial_startup_cleans_resources(failed, boundaries, caplog):
    runtime, tool, _, options, events, _ = boundaries
    failure = RuntimeError("fake-token and private-prompt")
    if failed == "sdk":
        runtime.start.side_effect = failure
    else:
        tool.__aenter__.side_effect = failure
    app = main.create_app(settings=Settings(_env_file=None))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as exc:
            async with app.router.lifespan_context(app):
                pytest.fail("startup should fail")
    runtime.stop.assert_awaited_once()
    assert "fake-token" not in str(exc.value)
    assert "private-prompt" not in str(exc.value)
    if failed == "sdk":
        assert exc.value.__suppress_context__
        tool.__aexit__.assert_not_awaited()
    else:
        tool.__aexit__.assert_awaited_once()
    assert "fake-token" not in caplog.text
    assert len(options) == 1


@pytest.mark.parametrize("stage", ["sdk_start", "mcp_enter", "body"])
async def test_cancellation_cleans_resources(stage, boundaries):
    runtime, tool, _, _, _, _ = boundaries
    if stage == "sdk_start":
        runtime.start.side_effect = asyncio.CancelledError
    elif stage == "mcp_enter":
        tool.__aenter__.side_effect = asyncio.CancelledError
    app = main.create_app(settings=Settings(_env_file=None))
    with pytest.raises(asyncio.CancelledError):
        async with app.router.lifespan_context(app):
            raise asyncio.CancelledError
    runtime.stop.assert_awaited_once()
    assert tool.__aexit__.await_count == (stage != "sdk_start")


async def test_shutdown_failure_force_stops_and_hides_exception(boundaries):
    runtime, _, _, _, _, _ = boundaries
    runtime.stop.side_effect = RuntimeError("fake-token private-prompt")
    app = main.create_app(settings=Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="Agent runtime shutdown failed") as exc:
        async with app.router.lifespan_context(app):
            pass
    runtime.force_stop.assert_awaited_once()
    assert "fake-token" not in str(exc.value)
    assert "private-prompt" not in str(exc.value)
    assert exc.value.__suppress_context__


async def test_failed_cleanup_does_not_replace_cancellation(boundaries):
    runtime, _, _, _, _, _ = boundaries
    runtime.stop.side_effect = RuntimeError("fake-token")
    app = main.create_app(settings=Settings(_env_file=None))
    with pytest.raises(asyncio.CancelledError):
        async with app.router.lifespan_context(app):
            raise asyncio.CancelledError
    runtime.force_stop.assert_awaited_once()


async def test_mcp_cleanup_failure_still_stops_sdk(boundaries):
    runtime, tool, _, _, _, _ = boundaries
    tool.__aexit__.side_effect = RuntimeError("MCP shutdown failed")
    app = main.create_app(settings=Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="Agent runtime shutdown failed"):
        async with app.router.lifespan_context(app):
            pass
    runtime.stop.assert_awaited_once()


async def test_every_lifespan_constructs_its_own_sdk_runtime(boundaries):
    runtime, _, _, options, _, _ = boundaries
    app = main.create_app(settings=Settings(_env_file=None), data_source=object())
    for _ in range(2):
        async with app.router.lifespan_context(app):
            pass
    assert len(options) == 2
    assert runtime.start.await_count == 2
    assert runtime.stop.await_count == 2


@pytest.mark.parametrize("mode", ["local", "pat"])
def test_real_sdk_accepts_transport_and_storage_without_starting(mode, monkeypatch):
    monkeypatch.setenv("COPILOT_SDK_DEFAULT_CONNECTION", "inprocess")
    monkeypatch.setattr(
        CopilotClient, "_resolve_runtime_entrypoint",
        lambda _self, _path, **_kwargs: "fake-runtime-not-started",
    )
    runtime = main._create_copilot_runtime(
        Settings(
            _env_file=None, copilot_auth_mode=mode,
            copilot_github_token="fake-explicit-token",
        )
    )
    assert runtime._state == "disconnected"
    assert runtime._options.mode == ("copilot-cli" if mode == "local" else "empty")
    assert runtime._options.use_logged_in_user is (mode == "local")
    assert runtime._process is None


async def test_repeated_cancellation_waits_for_cleanup(boundaries):
    runtime, _, _, _, _, _ = boundaries
    stopping = asyncio.Event()
    finish = asyncio.Event()

    async def stop():
        stopping.set()
        await finish.wait()

    runtime.stop.side_effect = stop
    app = main.create_app(settings=Settings(_env_file=None))

    async def worker():
        async with app.router.lifespan_context(app):
            raise asyncio.CancelledError

    task = asyncio.create_task(worker())
    await stopping.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    runtime.stop.assert_awaited_once()


async def test_constructor_failure_hides_sensitive_error(boundaries, monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("fake-token private-prompt")

    monkeypatch.setattr(main, "CopilotClient", fail)
    app = main.create_app(settings=Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="Copilot runtime configuration failed") as exc:
        async with app.router.lifespan_context(app):
            pytest.fail("startup should fail")
    assert "fake-token" not in str(exc.value)
    assert "private-prompt" not in str(exc.value)
