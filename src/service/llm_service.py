"""
 Created by luogang on 2024/2/29
"""
import os
import time

from openai import OpenAI

import common_utils

logger = common_utils.get_logger(__name__)


def chat(prompt, retry_count=3, service='kimi'):
    client = OpenAI(
        api_key=os.environ['KIMI_API_KEY'],
        base_url="https://api.moonshot.cn/v1",
    )
    model_name = 'moonshot-v1-8k'
    messages = [
        {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。"},
        {"role": "user", "content": prompt}
    ]

    def do_request():
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.6
        )
        return resp.choices[0].message.content

    while retry_count > 0:
        try:
            return do_request()
        except Exception as e:
            sleeping_seconds = (4 - retry_count) * 2
            retry_count -= 1
            logger.warning(f"{e} sleeping {sleeping_seconds}s, prompt: {prompt}")
            time.sleep(sleeping_seconds)
    return ""
