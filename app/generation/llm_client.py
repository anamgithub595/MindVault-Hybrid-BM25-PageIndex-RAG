"""
app/generation/llm_client.py
──────────────────────────────
Provider-agnostic LLM client.
Supports Anthropic Claude, OpenAI GPT, and Google Gemini behind one interface.
Only this module knows which SDK to call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        if self.provider == "anthropic":
            return await self._anthropic(system_prompt, user_message)
        if self.provider == "openai":
            return await self._openai(system_prompt, user_message)
        if self.provider == "gemini":
            return await self._gemini(system_prompt, user_message)
        raise LLMProviderError(f"Unknown provider: {self.provider!r}")

    async def _anthropic(self, system: str, user: str) -> LLMResponse:
        try:
            import anthropic
        except ImportError as e:
            raise LLMProviderError("anthropic SDK not installed") from e
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            r = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return LLMResponse(
                content=r.content[0].text,
                input_tokens=r.usage.input_tokens,
                output_tokens=r.usage.output_tokens,
                model=r.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc

    async def _openai(self, system: str, user: str) -> LLMResponse:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise LLMProviderError("openai SDK not installed") from e
        try:
            client = AsyncOpenAI(api_key=self.api_key)
            r = await client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            usage = r.usage
            return LLMResponse(
                content=r.choices[0].message.content or "",
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                model=r.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc

    async def _gemini(self, system: str, user: str) -> LLMResponse:
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise LLMProviderError(
                "google-genai not installed. Run: pip install google-genai"
            ) from e
        try:
            client = genai.Client(api_key=self.api_key)
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=self.max_tokens,
                    temperature=self.temperature,
                ),
            )
            text = response.text or ""
            usage = response.usage_metadata
            return LLMResponse(
                content=text,
                input_tokens=getattr(usage, "prompt_token_count", 0),
                output_tokens=getattr(usage, "candidates_token_count", 0),
                model=self.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc


'''

"""
app/generation/llm_client.py
──────────────────────────────
Provider-agnostic LLM client.
Supports Anthropic Claude, OpenAI GPT, and Google Gemini behind one interface.
Only this module knows which SDK to call.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from app.core.exceptions import LLMProviderError
 
logger = logging.getLogger(__name__)
 
 
@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
 
 
class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
 
    async def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        if self.provider == "anthropic":
            return await self._anthropic(system_prompt, user_message)
        if self.provider == "openai":
            return await self._openai(system_prompt, user_message)
        if self.provider == "gemini":
            return await self._gemini(system_prompt, user_message)
        raise LLMProviderError(f"Unknown provider: {self.provider!r}")
 
    async def _anthropic(self, system: str, user: str) -> LLMResponse:
        try:
            import anthropic
        except ImportError as e:
            raise LLMProviderError("anthropic SDK not installed") from e
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            r = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return LLMResponse(
                content=r.content[0].text,
                input_tokens=r.usage.input_tokens,
                output_tokens=r.usage.output_tokens,
                model=r.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
 
    async def _openai(self, system: str, user: str) -> LLMResponse:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise LLMProviderError("openai SDK not installed") from e
        try:
            client = AsyncOpenAI(api_key=self.api_key)
            r = await client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            usage = r.usage
            return LLMResponse(
                content=r.choices[0].message.content or "",
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                model=r.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
 
    async def _gemini(self, system: str, user: str) -> LLMResponse:
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise LLMProviderError("google-generativeai not installed. Run: pip install google-generativeai") from e
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system,
            )
            response = await model.generate_content_async(
                user,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=self.temperature,
                ),
            )
            text = response.text or ""
            usage = response.usage_metadata
            return LLMResponse(
                content=text,
                input_tokens=getattr(usage, "prompt_token_count", 0),
                output_tokens=getattr(usage, "candidates_token_count", 0),
                model=self.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
 


'''


'''





"""
app/generation/llm_client.py
──────────────────────────────
Provider-agnostic LLM client.
Supports Anthropic Claude and OpenAI GPT behind one interface.
Only this module knows which SDK to call.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from app.core.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        if self.provider == "anthropic":
            return await self._anthropic(system_prompt, user_message)
        if self.provider == "openai":
            return await self._openai(system_prompt, user_message)
        raise LLMProviderError(f"Unknown provider: {self.provider!r}")

    async def _anthropic(self, system: str, user: str) -> LLMResponse:
        try:
            import anthropic
        except ImportError as e:
            raise LLMProviderError("anthropic SDK not installed") from e
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            r = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return LLMResponse(
                content=r.content[0].text,
                input_tokens=r.usage.input_tokens,
                output_tokens=r.usage.output_tokens,
                model=r.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc

    async def _openai(self, system: str, user: str) -> LLMResponse:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise LLMProviderError("openai SDK not installed") from e
        try:
            client = AsyncOpenAI(api_key=self.api_key)
            r = await client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            usage = r.usage
            return LLMResponse(
                content=r.choices[0].message.content or "",
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                model=r.model,
            )
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc



'''
