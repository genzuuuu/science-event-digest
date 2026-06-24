import os
from openai import OpenAI

LINK_RULES = """
Citation rules (mandatory):
- Every event must include a clickable markdown link using the URL from the input.
- Format: [Event Title](https://...)
- Do NOT use bare numbers or placeholders without URLs.
""".strip()


def summarize(api_key: str, base_url: str, model: str, system_prompt: str, content: str) -> str:
    if not api_key:
        return "### No API key configured.\n\n" + content

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": f"{system_prompt.strip()}\n\n{LINK_RULES}"},
            {"role": "user", "content": content},
        ],
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},
    )
    text = response.choices[0].message.content or ""
    if not text.strip():
        raise ValueError("Empty summary from model")
    return text


def summarize_bilingual(api_key, base_url, model, prompt_en, prompt_zh, content):
    en = summarize(api_key, base_url, model, prompt_en, content)
    zh = summarize(api_key, base_url, model, prompt_zh, content)
    return en, zh
