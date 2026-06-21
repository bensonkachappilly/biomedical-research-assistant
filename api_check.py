import os
from dotenv import load_dotenv
import anthropic

load_dotenv()                    # reads ANTHROPIC_API_KEY from your .env file
client = anthropic.Anthropic()   # the SDK picks up the key from the environment

if __name__ == "__main__":
    msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=200,
    messages=[{"role": "user", "content": "In one sentence, confirm you are working."}],)
    print(msg.content[0].text)