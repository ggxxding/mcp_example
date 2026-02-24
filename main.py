from openai import OpenAI
API_KEY = "ollama"
BASE_URL = "http://192.168.200.23:11434/v1"
MODEL_NAME = "qwen3:30b"
def main():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你好"}
    ]
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    response = client.chat.completions.create(
    model=MODEL_NAME,
    max_tokens=10000,
    messages=messages,
    )
    print(response.choices[0].message.content)
    print("Hello from mcp-example!")


if __name__ == "__main__":
    main()
