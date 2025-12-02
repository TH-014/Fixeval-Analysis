import os
import random
import json
import csv
import time
from pathlib import Path
from openai import OpenAI # type: ignore
from dotenv import load_dotenv

api_key = os.getenv('OPENAI_API_KEY')

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=api_key,
)

completion = client.chat.completions.create(
  model="qwen/qwen3-30b-a3b:free",
  messages=[
    {
      "role": "user",
      "content": "What is ICMP Smurf Attack?"
    }
  ]
)

print(completion.choices[0].message.content)
