"""
extractors/custom_extractor.py
Uses Google Gemini to extract highly specific data based on a user's custom prompt.
"""

import json

from bs4 import BeautifulSoup
from google import genai

import config
from utils.html_parser import make_soup
from utils.logger import get_logger

logger = get_logger("custom_extractor")

# Cache to avoid configuring multiple times
_client = None


def _get_client():
    global _client
    if _client is None and config.GEMINI_API_KEY:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def extract_custom_data(html: str, prompt: str, soup: BeautifulSoup | None = None) -> list:
    """
    Sends the webpage text to Gemini and asks it to extract data matching the prompt.
    Returns a list of extracted strings/objects.
    """
    if not config.GEMINI_API_KEY or not prompt:
        return []

    client = _get_client()
    if not client:
        return []

    if soup is None:
        soup = make_soup(html)

    # Clean the HTML to just text to save tokens and avoid confusing the LLM
    text_content = soup.get_text(separator="\n", strip=True)

    # If the page is completely empty, skip
    if len(text_content) < 50:
        return []

    # Limit text to roughly 30k chars to avoid blowing up context windows on massive pages unnecessarily
    text_content = text_content[:30000]

    system_instruction = (
        "You are a strict data extraction bot. Your job is to extract exactly what the user asks for from the provided webpage text. "
        'Return the results as a JSON list of strings (e.g. ["item 1", "item 2"]). '
        "If you cannot find the requested information, return an empty list: []"
        "Do NOT include markdown formatting like ```json in your response, just the raw JSON array."
    )

    try:
        full_prompt = f"User Request: {prompt}\n\nWebpage Text:\n{text_content}"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
            config=genai.types.GenerateContentConfig(system_instruction=system_instruction),
        )
        result_text = response.text.strip()

        # Clean up any potential markdown formatting the model might still try to output
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]

        result_text = result_text.strip()

        data = json.loads(result_text)
        if isinstance(data, list):
            return data
        elif data:
            return [str(data)]

    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        logger.warning(f"Gemini custom extraction failed: {e}")

    return []
