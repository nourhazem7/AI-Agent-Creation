"""Deep Agent — wraps LangChain's Deep Agents harness for agentic tool-calling loops.

Uses the deepagents package (langchain-ai/deepagents) with a minimal middleware
stack: only summarization (context compaction) and Anthropic prompt caching.
Filesystem, todo, and sub-agent middleware are disabled — this agent only needs
the text2sql tools passed in by the caller.
"""

from __future__ import annotations

from deepagents import create_deep_agent as _deepagents_create
from langchain_core.messages import HumanMessage


def _get_chat_model(
    model_str: str,
    base_url: str | None = None,
    verify_ssl: bool = True,
    extra_body: dict | None = None,
    llm_api_key: str | None = None,
):
    """Parse 'provider:model_name' and return a LangChain chat model.

    Args:
        model_str:   'provider:model_name', e.g. 'openai:Qwen/Qwen3.6-35B-A3B'
        base_url:    Override the API base URL (for custom / on-prem endpoints).
        verify_ssl:  Set False to skip TLS verification (self-signed certs).
        extra_body:  Extra JSON fields merged into every request body,
                     e.g. {'chat_template_kwargs': {'enable_thinking': False}}.
        llm_api_key: API key for the LLM endpoint (defaults to env var).
    """
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
    else:
        provider, model_name = "anthropic", model_str

    provider = provider.lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = {"model": model_name, "max_tokens": 4096}
        if llm_api_key:
            kwargs["api_key"] = llm_api_key
        return ChatAnthropic(**kwargs)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        import httpx

        kwargs = {"model": model_name}
        if base_url:
            kwargs["base_url"] = base_url
        # Use a dummy key when the endpoint doesn't require auth
        kwargs["api_key"] = llm_api_key or "not-required"
        if not verify_ssl:
            kwargs["http_client"] = httpx.Client(verify=False)
        if extra_body:
            kwargs["extra_body"] = extra_body
        return ChatOpenAI(**kwargs)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


class DeepAgent:
    """LangChain Deep Agents harness with text2sql tools and system prompt."""

    def __init__(
        self,
        model_str: str,
        tools: list,
        system_prompt: str,
        base_url: str | None = None,
        verify_ssl: bool = True,
        extra_body: dict | None = None,
        llm_api_key: str | None = None,
    ):
        self.llm = _get_chat_model(
            model_str,
            base_url=base_url,
            verify_ssl=verify_ssl,
            extra_body=extra_body,
            llm_api_key=llm_api_key,
        )
        self.system_prompt = system_prompt

        self.agent = _deepagents_create(
            model=self.llm,
            tools=tools,
            system_prompt=system_prompt,
            subagents=[],
        )

    def invoke(self, input_dict: dict) -> dict:
        """Run the agent. Input: {"messages": [{"role": "user", "content": "..."}]}"""
        messages = []
        for msg in input_dict.get("messages", []):
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))

        result = self.agent.invoke(
            {"messages": messages},
            config={"recursion_limit": 50},
        )

        return {"messages": result["messages"]}

    def stream(self, input_dict: dict, stream_mode="updates"):
        """Stream the agent. Input: {"messages": [{"role": "user", "content": "..."}]}"""
        messages = []
        for msg in input_dict.get("messages", []):
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))

        if hasattr(self.agent, "stream"):
            return self.agent.stream(
                {"messages": messages},
                config={"recursion_limit": 50},
                stream_mode=stream_mode,
            )
        else:
            raise NotImplementedError("Inner agent does not support streaming")


def create_deep_agent(
    model: str,
    tools: list,
    system_prompt: str,
    token_limit: int = 75_000,  # kept for backward compatibility
    base_url: str | None = None,
    verify_ssl: bool = True,
    extra_body: dict | None = None,
    llm_api_key: str | None = None,
) -> DeepAgent:
    """Create a Deep Agent with tools and a system prompt."""
    return DeepAgent(
        model_str=model,
        tools=tools,
        system_prompt=system_prompt,
        base_url=base_url,
        verify_ssl=verify_ssl,
        extra_body=extra_body,
        llm_api_key=llm_api_key,
    )
