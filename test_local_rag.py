import asyncio
import os
import sys

# Thêm api path
sys.path.append(os.path.join(os.getcwd(), 'api'))

from core.config import settings
from core.openai_client import get_chat_openai

async def main():
    print(f"Testing model: {settings.openai_chat_model}")
    print(f"Base URL: {settings.openai_chat_base_url}")
    
    client = get_chat_openai()
    print("Client initialized")
    
    try:
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[{"role": "user", "content": "Xin chào"}],
            stream=True
        )
        print("Connected and streaming...")
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta:
                content = delta.content or ""
                reasoning = getattr(delta, "reasoning", "")
                if reasoning:
                    print(f"[REASONING]: {reasoning}")
                if content:
                    print(f"[CONTENT]: {content}")
        print("\nDone streaming.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
