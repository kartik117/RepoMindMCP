from langchain_google_genai import ChatGoogleGenerativeAI

from repomind.config import Settings, get_settings


def get_chat_model(settings: Settings | None = None) -> ChatGoogleGenerativeAI:
    settings = settings or get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0,
    )
