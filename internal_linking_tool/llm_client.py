"""LLM client for generating SEO anchor text via OpenAI-compatible API (DeepSeek V4 Pro)."""

import json
from typing import Optional


class LlmAnchorClient:
    """OpenAI-compatible client for generating natural anchor text.

    Uses the DeepSeek V4 Pro API (or any OpenAI-compatible endpoint) to
    transform GSC keywords + target page context into descriptive,
    natural anchor text suggestions.
    """

    def __init__(self, endpoint: str, api_key: str, model: str = "deepseek-chat"):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self._available = bool(api_key)

    def is_available(self) -> bool:
        return self._available

    def generate_anchors(
        self,
        target_context: dict,
        keyword: str,
        source_context: str,
        max_variations: int = 3,
    ) -> Optional[list[str]]:
        """Generate anchor text variations for a given keyword + context.

        Args:
            target_context: dict with keys "title", "h1", "slug", "description"
            keyword: GSC query keyword
            source_context: surrounding sentence from source page
            max_variations: max number of anchor texts to return (1-3)

        Returns:
            List of anchor text strings, or None on failure.
        """
        if not self._available:
            return None

        title = target_context.get("title", "")
        h1 = target_context.get("h1", "")
        slug = target_context.get("slug", "")

        prompt = self._build_prompt(title, h1, slug, keyword, source_context, max_variations)

        try:
            from openai import OpenAI
            client = OpenAI(base_url=self.endpoint, api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an internal linking specialist for SEO. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            anchors = self._parse_response(content)
            if anchors:
                return anchors[:max_variations]
            return self._retry(client, prompt)

        except Exception:
            return None

    def _retry(self, client, original_prompt) -> Optional[list[str]]:
        """Retry with stricter prompt on JSON parse failure."""
        try:
            retry_prompt = original_prompt + "\n\nIMPORTANT: Your entire response must be valid JSON with exactly this structure: {\"anchors\": [\"anchor1\", \"anchor2\"]}"
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": retry_prompt}],
                max_tokens=200,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            return self._parse_response(content)
        except Exception:
            return None

    @staticmethod
    def _build_prompt(title, h1, slug, keyword, source_context, max_variations):
        return f"""TARGET PAGE:
  Title: "{title}"
  Heading: "{h1}"
  Topic: "{slug}"

SOURCE PAGE CONTEXT:
  A page mentions "{keyword}" in this sentence: "{source_context}"

Generate {max_variations} natural, descriptive anchor text variations for a link pointing to the target page.

RULES (CRITICAL):
- Must accurately describe what the reader will find on the target page
- 2-5 words per anchor
- NOT generic: NO "click here," "read more," "learn more," "this article," "website"
- Write naturally, not keyword-stuffed
- When possible, incorporate the keyword naturally
- Each variation should be distinct from the others
- Anchor text should feel like natural prose that fits the source sentence context

Return ONLY valid JSON: {{"anchors": ["anchor1", "anchor2"]}}"""

    @staticmethod
    def _parse_response(content: str) -> Optional[list[str]]:
        """Parse JSON response from LLM."""
        try:
            data = json.loads(content)
            anchors = data.get("anchors", [])
            if isinstance(anchors, list) and len(anchors) > 0:
                return [a for a in anchors if isinstance(a, str) and len(a.strip()) > 0]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None
