import logging
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI  # type: ignore[import-not-found]
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential  # type: ignore[import-not-found]

load_dotenv()


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    openai_client = OpenAI()
    completion = None
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Let OpenAI handle the pydantic parsing directly
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=MemoryCategories,
            temperature=0
        )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        if completion is not None:
            try:
                logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
            except Exception as debug_e:
                logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
