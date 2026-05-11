import os
from typing import Optional


class LLMClient:
    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model

        if provider == "openai":
            from openai import OpenAI
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
            self.client = OpenAI(api_key=key)
        elif provider == "anthropic":
            raise NotImplementedError("Anthropic provider is not yet implemented.")
        elif provider == "gemini":
            raise NotImplementedError("Gemini provider is not yet implemented.")
        else:
            raise ValueError(f"Unknown LLM provider: {provider!r}")

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        raise ValueError(f"Unknown provider: {self.provider!r}")
