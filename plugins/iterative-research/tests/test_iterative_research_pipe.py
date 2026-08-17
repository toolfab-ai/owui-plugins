# ruff: noqa: E402
"""Unit tests for iterative-research Pipe entry point and research loop."""

from __future__ import annotations

import sys
from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ========================================================================
# MOCK OPEN_WEBUI DEPENDENCIES
# ========================================================================
mock_chat_mod = MagicMock()
mock_generate_chat_completion = AsyncMock()
mock_chat_mod.generate_chat_completion = mock_generate_chat_completion

sys.modules["open_webui"] = MagicMock()
sys.modules["open_webui.utils"] = MagicMock()
sys.modules["open_webui.utils.chat"] = mock_chat_mod
sys.modules["open_webui.models"] = MagicMock()
sys.modules["open_webui.models.models"] = MagicMock()
sys.modules["open_webui.models.users"] = MagicMock()

from tests._plugin_loader import load_plugin

mod = load_plugin("iterative-research")
Pipe = mod.Pipe


@pytest.mark.unit
class TestPipeMainEntryPoint:
    """Test the main ``pipe`` entry point and autonomous execution loop."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    @pytest.mark.asyncio
    async def test_pipe_full_loop(self) -> None:
        self.pipe.valves.MAX_STEPS = 1
        self.pipe.valves.MAX_PAGES_TO_SCRAPE = 1
        self.pipe.valves.MODEL = "mock-model"
        self.pipe.valves.TAVILY_API_KEY = "mock-key"

        # Mock search query helper
        async def mock_search(query: str, user_valves: Any = None) -> list[dict[str, str]]:
            return [
                {"title": "Result 1", "url": "https://example.com/res1", "content": "Snippet 1"}
            ]

        self.pipe._search_query = mock_search

        # Mock page scraping helper
        async def mock_scrape(url: str) -> Optional[dict[str, str]]:
            return {
                "url": url,
                "title": "Result 1 Title",
                "content": "This is the full scraped content from Result 1.",
            }

        self.pipe._scrape_url = mock_scrape

        # Mock the chat completion LLM calls
        async def mock_gen_completion(
            __request__: Any, payload: dict[str, Any], user_obj: Any
        ) -> str:
            messages = payload.get("messages", [])
            system_content = next((m["content"] for m in messages if m["role"] == "system"), "")

            if "planning agent" in system_content or "search strategy" in system_content:
                return '{"gaps": ["Need details on X"], "queries": ["query1"]}'
            elif "research synthesizer" in system_content:
                return "This is the final report synthesizing Result 1 Title [1]."
            return "Default response"

        event_emitter = AsyncMock()
        body = {
            "stream": True,
            "messages": [{"role": "user", "content": "What is the status of project X?"}],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion", side_effect=mock_gen_completion
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            chunks = []
            generator = await self.pipe.pipe(
                body=body,
                __user__=None,
                __request__=None,
                __event_emitter__=event_emitter,
            )
            async for chunk in generator:
                chunks.append(chunk)

            full_output = "".join(chunks)

            # Assert output contains critical sections and thinking blocks
            assert "<thinking>" in full_output
            assert "</thinking>" in full_output
            assert "Information Gaps Identified" in full_output
            assert "Generated Web Search Queries" in full_output
            assert "This is the final report synthesizing Result 1 Title [1]" in full_output

            # Check that citations and status updates were emitted
            emitted_types = [call[0][0]["type"] for call in event_emitter.call_args_list]
            assert "status" in emitted_types
            assert "citation" in emitted_types

            # Verify citation details
            citation_call = next(
                call[0][0]
                for call in event_emitter.call_args_list
                if call[0][0]["type"] == "citation"
            )
            assert citation_call["data"]["source"]["name"] == "Result 1 Title"
            assert citation_call["data"]["source"]["url"] == "https://example.com/res1"

    @pytest.mark.asyncio
    async def test_pipe_user_valves_as_dict(self) -> None:
        """Verify that UserValves passed as a dictionary are correctly resolved."""
        self.pipe.valves.MAX_STEPS = 5
        self.pipe.valves.SEARXNG_URL = "https://admin-searxng.local"

        # Pass UserValves as a dict, overriding MAX_STEPS
        # Note: searxng_url is now admin-only and should be ignored if passed by user
        user_valves = {
            "max_steps": "2",
            "searxng_url": "https://user-searxng.local",
        }

        # Mock dependencies to reach the research loop
        self.pipe._search_query = AsyncMock(return_value=[])
        self.pipe._get_backend_model = AsyncMock(return_value="mock-model")
        self.pipe._get_update_notification = AsyncMock(return_value=None)

        # Mock _synthesize_report as an async generator
        async def mock_synthesize(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
            yield "Final Report"

        self.pipe._synthesize_report = mock_synthesize

        body = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion",
                new_callable=AsyncMock,
                return_value='{"gaps": [], "queries": []}',
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            generator = await self.pipe.pipe(
                body=body,
                __user__={"id": "user1"},
                __request__=None,
                __event_emitter__=AsyncMock(),
                __user_valves__=user_valves,
            )
            # Consume generator to trigger logic
            async for _ in generator:
                pass

            # Verify _get_config directly for the instance
            assert self.pipe._get_config("max_steps", user_valves) == 2
            # Admin valve should be used, user override ignored or not resolved via _get_config for search
            assert self.pipe.valves.SEARXNG_URL == "https://admin-searxng.local"
            assert (
                self.pipe._get_config("co_storm_steering", user_valves) is False
            )  # default from admin

    @pytest.mark.asyncio
    async def test_pipe_non_stream_returns_str(self) -> None:
        self.pipe.valves.MAX_STEPS = 1
        self.pipe.valves.MAX_PAGES_TO_SCRAPE = 1
        self.pipe.valves.MODEL = "mock-model"
        self.pipe.valves.TAVILY_API_KEY = "mock-key"

        # Mock search query helper
        async def mock_search(query: str, user_valves: Any = None) -> list[dict[str, str]]:
            return [
                {"title": "Result 1", "url": "https://example.com/res1", "content": "Snippet 1"}
            ]

        self.pipe._search_query = mock_search

        # Mock page scraping helper
        async def mock_scrape(url: str) -> Optional[dict[str, str]]:
            return {
                "url": url,
                "title": "Result 1 Title",
                "content": "This is the full scraped content from Result 1.",
            }

        self.pipe._scrape_url = mock_scrape

        # Mock the chat completion LLM calls
        async def mock_gen_completion(
            __request__: Any, payload: dict[str, Any], user_obj: Any
        ) -> str:
            messages = payload.get("messages", [])
            system_content = next((m["content"] for m in messages if m["role"] == "system"), "")

            if "planning agent" in system_content or "search strategy" in system_content:
                return '{"gaps": ["Need details on X"], "queries": ["query1"]}'
            elif "research synthesizer" in system_content:
                return "This is the final report synthesizing Result 1 Title [1]."
            return "Default response"

        event_emitter = AsyncMock()
        # "stream" is set to False (default)
        body = {
            "stream": False,
            "messages": [{"role": "user", "content": "What is the status of project X?"}],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion", side_effect=mock_gen_completion
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            # Call pipe and assert that a plain string is returned directly
            result = await self.pipe.pipe(
                body=body,
                __user__=None,
                __request__=None,
                __event_emitter__=event_emitter,
            )

            assert isinstance(result, str) is True
            assert "<thinking>" in result
            assert "</thinking>" in result
            assert "Information Gaps Identified" in result
            assert "This is the final report synthesizing Result 1 Title [1]" in result


@pytest.mark.unit
class TestCoStormSteering:
    """Test Co-STORM human-in-the-loop pause and continuation flow."""

    def setup_method(self) -> None:
        self.pipe = Pipe()

    @pytest.mark.asyncio
    async def test_costorm_halt_after_step_1(self) -> None:
        self.pipe.valves.CO_STORM_STEERING = True
        self.pipe.valves.MAX_STEPS = 2
        self.pipe.valves.MAX_PAGES_TO_SCRAPE = 1
        self.pipe.valves.MODEL = "mock-model"
        self.pipe.valves.TAVILY_API_KEY = "mock-key"

        async def mock_search(query: str, user_valves: Any = None) -> list[dict[str, str]]:
            return [
                {"title": "Source 1", "url": "https://example.com/src1", "content": "Snippet 1"}
            ]

        self.pipe._search_query = mock_search

        async def mock_scrape(url: str) -> Optional[dict[str, str]]:
            return {"url": url, "title": "Source 1 Title", "content": "Scraped Content of Source 1"}

        self.pipe._scrape_url = mock_scrape

        async def mock_gen_completion(
            __request__: Any, payload: dict[str, Any], user_obj: Any
        ) -> str:
            return '{"gaps": ["Outstanding gap"], "queries": ["query1"]}'

        event_emitter = AsyncMock()
        body = {
            "stream": True,
            "messages": [{"role": "user", "content": "Research Topic X"}],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion", side_effect=mock_gen_completion
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            chunks = []
            generator = await self.pipe.pipe(
                body=body,
                __user__=None,
                __request__=None,
                __event_emitter__=event_emitter,
            )
            async for chunk in generator:
                chunks.append(chunk)

            full_output = "".join(chunks)

            # Verify step 1 executes and lists gaps/queries/sources
            assert "Step 1/2: Planning" in full_output
            assert "Intermediate Research Findings" in full_output
            assert "Human-in-the-Loop Steering" in full_output
            assert "Awaiting your input to continue" in full_output

            # Verify we returned early and did not synthesize the final report
            assert "Final Synthesis" not in full_output

            # Verify the status event paused correctly
            status_calls = [
                call[0][0]
                for call in event_emitter.call_args_list
                if call[0][0]["type"] == "status"
            ]
            pause_call = next(c for c in status_calls if "Pausing" in c["data"]["description"])
            assert pause_call["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_costorm_continuation_turn_2(self) -> None:
        self.pipe.valves.CO_STORM_STEERING = True
        self.pipe.valves.MAX_STEPS = 2
        self.pipe.valves.MAX_PAGES_TO_SCRAPE = 1
        self.pipe.valves.MODEL = "mock-model"
        self.pipe.valves.TAVILY_API_KEY = "mock-key"

        async def mock_search(query: str, user_valves: Any = None) -> list[dict[str, str]]:
            return [
                {"title": "Source 2", "url": "https://example.com/src2", "content": "Snippet 2"}
            ]

        self.pipe._search_query = mock_search

        async def mock_scrape(url: str) -> Optional[dict[str, str]]:
            return {"url": url, "title": "Source 2 Title", "content": "Scraped Content of Source 2"}

        self.pipe._scrape_url = mock_scrape

        async def mock_gen_completion(
            __request__: Any, payload: dict[str, Any], user_obj: Any
        ) -> str:
            messages = payload.get("messages", [])
            system_content = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_content = next((m["content"] for m in messages if m["role"] == "user"), "")

            if "planning agent" in system_content:
                # Expect intermediate feedback in user prompt
                assert "User intermediate steering feedback: focus on performance" in user_content
                # Reconstructed sources should be listed in user prompt
                assert "Source 1 Title" in user_content
                return '{"gaps": ["Step 2 gap"], "queries": ["query2"]}'
            elif "research synthesizer" in system_content:
                # Reconstructed Source 1 and scraped Source 2 should be cited
                assert "Source 1 Title" in user_content
                assert "Source 2 Title" in user_content
                return "This is the final research report synthesizing everything."
            return "Default"

        event_emitter = AsyncMock()
        # Simulated chat history containing step 1 results and user's step 2 feedback
        body = {
            "stream": True,
            "messages": [
                {"role": "user", "content": "Research Topic X"},
                {
                    "role": "assistant",
                    "content": "Intermediate findings: [Source 1 Title](https://example.com/src1)",
                },
                {"role": "user", "content": "focus on performance"},
            ],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion", side_effect=mock_gen_completion
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            chunks = []
            generator = await self.pipe.pipe(
                body=body,
                __user__=None,
                __request__=None,
                __event_emitter__=event_emitter,
            )
            async for chunk in generator:
                chunks.append(chunk)

            full_output = "".join(chunks)

            # Verify we executed step 2 planning and final synthesis
            assert "Step 2/2: Planning" in full_output
            assert "This is the final research report synthesizing everything." in full_output

            # Check that final completion event is sent
            status_calls = [
                call[0][0]
                for call in event_emitter.call_args_list
                if call[0][0]["type"] == "status"
            ]
            complete_call = next(c for c in status_calls if "complete" in c["data"]["description"])
            assert complete_call["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_pipe_validation_no_search_engine(self) -> None:
        """Verify pre-flight validation fails and halts when no search engine is configured."""
        self.pipe.valves.TAVILY_API_KEY = ""
        self.pipe.valves.SEARXNG_URL = ""
        self.pipe.valves.MODEL = "mock-model"

        event_emitter = AsyncMock()
        body = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        generator = await self.pipe.pipe(
            body=body,
            __user__=None,
            __request__=None,
            __event_emitter__=event_emitter,
        )
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)

        full_output = "".join(chunks)

        # Assert search engine configuration error is in the output and it immediately returned
        assert "Configuration Error" in full_output
        assert "No search engine is configured" in full_output
        assert "<thinking>" not in full_output  # Halts before executing any step

        # Verify status event was emitted with done: True
        emitted_types = [call[0][0]["type"] for call in event_emitter.call_args_list]
        assert "status" in emitted_types
        status_call = event_emitter.call_args_list[0][0][0]
        assert (
            status_call["data"]["description"]
            == "Configuration Error: No search engine configured."
        )
        assert status_call["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_pipe_validation_no_model(self) -> None:
        """Verify pre-flight validation fails and halts when no model is specified."""
        self.pipe.valves.TAVILY_API_KEY = "mock-key"
        self.pipe.valves.SEARXNG_URL = ""
        self.pipe.valves.MODEL = ""

        event_emitter = AsyncMock()
        body = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        generator = await self.pipe.pipe(
            body=body,
            __user__=None,
            __request__=None,
            __event_emitter__=event_emitter,
        )
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)

        full_output = "".join(chunks)

        # Assert model configuration error is in the output and it immediately returned
        assert "Configuration Error" in full_output
        assert "No backend model is specified" in full_output
        assert "<thinking>" not in full_output  # Halts before executing any step

        # Verify status event was emitted with done: True
        emitted_types = [call[0][0]["type"] for call in event_emitter.call_args_list]
        assert "status" in emitted_types
        status_call = event_emitter.call_args_list[0][0][0]
        assert (
            status_call["data"]["description"] == "Configuration Error: No backend model specified."
        )
        assert status_call["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_pipe_validation_only_tavily_configured(self) -> None:
        """Verify pre-flight validation succeeds when only Tavily is configured."""
        self.pipe.valves.TAVILY_API_KEY = "mock-key"
        self.pipe.valves.SEARXNG_URL = ""
        self.pipe.valves.MODEL = "mock-model"

        # Mock standard loop so it terminates immediately
        self.pipe._search_query = AsyncMock(return_value=[])
        self.pipe._get_update_notification = AsyncMock(return_value=None)

        async def mock_synthesize(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
            yield "Success"

        self.pipe._synthesize_report = mock_synthesize

        event_emitter = AsyncMock()
        body: dict[str, Any] = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion",
                new_callable=AsyncMock,
                return_value='{"gaps": [], "queries": []}',
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            generator = await self.pipe.pipe(
                body=body,
                __user__=None,
                __request__=None,
                __event_emitter__=event_emitter,
            )
            chunks: list[str] = []
            async for chunk in generator:
                chunks.append(chunk)

            full_output = "".join(chunks)

            # Assert that there is NO configuration error
            assert "Configuration Error" not in full_output
            assert "Success" in full_output

    @pytest.mark.asyncio
    async def test_pipe_validation_only_searxng_configured(self) -> None:
        """Verify pre-flight validation succeeds when only SearXNG is configured."""
        self.pipe.valves.TAVILY_API_KEY = ""
        self.pipe.valves.SEARXNG_URL = "https://searxng.local"
        self.pipe.valves.MODEL = "mock-model"

        # Mock standard loop so it terminates immediately
        self.pipe._search_query = AsyncMock(return_value=[])
        self.pipe._get_update_notification = AsyncMock(return_value=None)

        async def mock_synthesize(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
            yield "Success"

        self.pipe._synthesize_report = mock_synthesize

        event_emitter = AsyncMock()
        body: dict[str, Any] = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        with (
            patch(
                "open_webui.utils.chat.generate_chat_completion",
                new_callable=AsyncMock,
                return_value='{"gaps": [], "queries": []}',
            ),
            patch(
                "socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]
            ),
        ):
            generator = await self.pipe.pipe(
                body=body,
                __user__=None,
                __request__=None,
                __event_emitter__=event_emitter,
            )
            chunks: list[str] = []
            async for chunk in generator:
                chunks.append(chunk)

            full_output = "".join(chunks)

            # Assert that there is NO configuration error
            assert "Configuration Error" not in full_output
            assert "Success" in full_output

    @pytest.mark.asyncio
    async def test_pipe_validation_valves_none_and_empty_values(self) -> None:
        """Verify pre-flight validation when valves are set to None or empty types."""
        self.pipe.valves.TAVILY_API_KEY = None
        self.pipe.valves.SEARXNG_URL = None
        self.pipe.valves.MODEL = "mock-model"

        event_emitter = AsyncMock()
        body: dict[str, Any] = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        generator = await self.pipe.pipe(
            body=body,
            __user__=None,
            __request__=None,
            __event_emitter__=event_emitter,
        )
        chunks: list[str] = []
        async for chunk in generator:
            chunks.append(chunk)

        full_output = "".join(chunks)

        # Assert search engine configuration error is in the output and it immediately returned
        assert "Configuration Error" in full_output
        assert "No search engine is configured" in full_output

    @pytest.mark.asyncio
    async def test_pipe_planning_llm_failure(self) -> None:
        """Verify planning LLM call failure closes thinking, yields error banner and halts."""
        self.pipe.valves.MAX_STEPS = 1
        self.pipe.valves.MAX_PAGES_TO_SCRAPE = 1
        self.pipe.valves.MODEL = "mock-model"
        self.pipe.valves.TAVILY_API_KEY = "mock-key"

        # Mock LLM call returning empty/falsy response
        self.pipe._call_llm = AsyncMock(return_value="")

        event_emitter = AsyncMock()
        body: dict[str, Any] = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        generator = await self.pipe.pipe(
            body=body,
            __user__=None,
            __request__=None,
            __event_emitter__=event_emitter,
        )
        chunks: list[str] = []
        async for chunk in generator:
            chunks.append(chunk)

        full_output = "".join(chunks)

        # Assert that thinking block is closed cleanly
        assert "</thinking>\n\n" in full_output
        # Assert that the highly visible markdown error banner was yielded
        assert (
            "> ⚠️ **Error**: Failed to generate planning strategy using backend model 'mock-model'."
            in full_output
        )
        # Assert that we halted execution immediately (no synthesis is in output)
        assert "Final Synthesis" not in full_output

        # Verify status event was emitted with done: True
        status_calls = [
            call[0][0] for call in event_emitter.call_args_list if call[0][0]["type"] == "status"
        ]
        assert len(status_calls) > 0
        error_status = status_calls[-1]
        assert (
            "Critical Error: Failed to generate planning strategy"
            in error_status["data"]["description"]
        )
        assert error_status["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_pipe_synthesis_llm_failure(self) -> None:
        """Verify synthesis LLM call failure yields error banner and halts."""
        self.pipe.valves.MAX_STEPS = 1
        self.pipe.valves.MAX_PAGES_TO_SCRAPE = 1
        self.pipe.valves.MODEL = "mock-model"
        self.pipe.valves.TAVILY_API_KEY = "mock-key"

        # Mock LLM call. First call for planning succeeds, second call for synthesis fails (empty response)
        call_count = 0

        async def mock_call_llm(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"gaps": [], "queries": []}'  # early exit -> synthesis
            return ""  # synthesis failure

        self.pipe._call_llm = mock_call_llm

        event_emitter = AsyncMock()
        body: dict[str, Any] = {
            "stream": True,
            "messages": [{"role": "user", "content": "test query"}],
        }

        generator = await self.pipe.pipe(
            body=body,
            __user__=None,
            __request__=None,
            __event_emitter__=event_emitter,
        )
        chunks: list[str] = []
        async for chunk in generator:
            chunks.append(chunk)

        full_output = "".join(chunks)

        # Assert that the highly visible markdown error banner was yielded
        assert (
            "> ⚠️ **Error**: Final synthesis failed due to an empty response from model 'mock-model'."
            in full_output
        )

        # Verify status event was emitted with done: True
        status_calls = [
            call[0][0] for call in event_emitter.call_args_list if call[0][0]["type"] == "status"
        ]
        assert len(status_calls) > 0
        error_status = status_calls[-1]
        assert "Critical Error: Final synthesis failed" in error_status["data"]["description"]
        assert error_status["data"]["done"] is True
