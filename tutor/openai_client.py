from openai import OpenAI


class OpenAIChatClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat(self, messages: list[dict[str, str]], timeout: int = 60) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            timeout=timeout,
        )
        return response.choices[0].message.content


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding
