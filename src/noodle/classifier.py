"""
LLM Classifier for Noodle.

Routes raw thoughts into the four buckets: task, thought, person, event.
Supports both Anthropic and OpenAI APIs.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from noodle.config import load_config


class ClassifiedEntry(BaseModel):
    """Schema for LLM classification output."""

    type: str = Field(description="One of: task, thought, person, event")
    title: str = Field(max_length=100, description="Short title")
    body: str | None = Field(default=None, description="Extended content")
    confidence: float = Field(ge=0, le=1, description="Classification confidence")
    tags: list[str] = Field(default_factory=list, description="Relevant tags")
    project: str | None = Field(default=None, description="Project slug if applicable")
    people: list[str] = Field(default_factory=list, description="Referenced people slugs")
    due_date: str | None = Field(default=None, description="ISO date for tasks/events")
    priority: str | None = Field(default=None, description="low, medium, or high")


# Default models for each provider
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",  # Fast and cheap for classification
    "openai": "gpt-4o-mini",
}


CLASSIFIER_PROMPT = """You are a classifier for a personal knowledge management system called Noodle.
Your job is to route raw thoughts into exactly ONE of four buckets.

## The Four Buckets (ONLY these exist)

1. **task** - Something to DO. Action items, todos, things that require action.
   - Signals: verbs ("email", "call", "review", "buy"), "need to", "should", "must", deadlines
   - Examples: "Email Sarah", "Review the PR", "Buy milk tomorrow"

2. **thought** - Something to REMEMBER. Ideas, notes, observations, references, URLs.
   - Signals: "what if", "I think", observations, URLs, book titles, interesting facts
   - Examples: "What if we used WebSockets?", "Interesting article on distributed systems"

3. **person** - Information ABOUT someone. Contact info, relationship notes.
   - Signals: Names with context, emails, phone numbers, "works at", "met at"
   - Examples: "Met Jake at the conference - he works on distributed systems at Stripe"

4. **event** - Something at a specific TIME. Meetings, appointments, deadlines.
   - Signals: dates, times, "on Monday", "next week", calendar-like items
   - Examples: "Team standup Monday 10am", "Conference in Seattle March 15-17"

## Input
```
{input}
```

## Context
Today's date: {today}

## Rules
- Pick ONE type. When ambiguous, prefer: task > event > thought > person
- Extract @mentions as people references (slugify: "Sarah Chen" → "sarah-chen")
- Extract #hashtags as tags
- Parse natural dates relative to today
- Infer priority (low/medium/high) from urgency words - only for tasks
- Identify project context from keywords if obvious
- Be concise with titles (max 100 chars)

## Output
Return ONLY valid JSON matching this schema:
```json
{{
  "type": "task|thought|person|event",
  "title": "concise title",
  "body": "optional extended content",
  "confidence": 0.0-1.0,
  "tags": ["tag1", "tag2"],
  "project": "project-slug or null",
  "people": ["person-slug"],
  "due_date": "YYYY-MM-DD or null",
  "priority": "low|medium|high or null"
}}
```

Return ONLY the JSON object, no explanation or markdown."""


class Classifier:
    """LLM-powered classifier for routing thoughts. Supports Anthropic and OpenAI."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or load_config()
        self.llm_config = self.config.get("llm", {})

        # Determine provider (anthropic is default, check for keys)
        self.provider = self.llm_config.get("provider", "anthropic")

        # Get API key based on provider
        if self.provider == "anthropic":
            self.api_key = (
                self.llm_config.get("anthropic_api_key")
                or os.environ.get("ANTHROPIC_API_KEY")
            )
            self.model = self.llm_config.get("model", DEFAULT_MODELS["anthropic"])
            self.base_url = "https://api.anthropic.com/v1"
            if not self.api_key:
                raise ValueError(
                    "Anthropic API key not found. Set ANTHROPIC_API_KEY env var or add to config."
                )
        else:  # openai
            self.api_key = (
                self.llm_config.get("openai_api_key")
                or os.environ.get("OPENAI_API_KEY")
            )
            self.model = self.llm_config.get("model", DEFAULT_MODELS["openai"])
            self.base_url = self.llm_config.get("base_url", "https://api.openai.com/v1")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key not found. Set OPENAI_API_KEY env var or add to config."
                )

    def classify(self, raw_input: str) -> dict[str, Any]:
        """
        Classify raw input text.

        Returns dict with classification result and metadata.
        Falls back gracefully if LLM fails.
        """
        start_time = time.time()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        prompt = CLASSIFIER_PROMPT.format(input=raw_input, today=today)

        try:
            if self.provider == "anthropic":
                response = self._call_anthropic(prompt)
            else:
                response = self._call_openai(prompt)

            parsed = self._parse_response(response, raw_input)
            processing_time = int((time.time() - start_time) * 1000)

            return {
                **parsed,
                "raw_input": raw_input,
                "llm_model": self.model,
                "processing_time_ms": processing_time,
                "status": "classified" if parsed["confidence"] >= 0.75 else "low_confidence",
            }

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            # Graceful fallback - never lose the thought
            return self._fallback_classification(raw_input, str(e), processing_time)

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Lower temp for consistent classification
                },
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Lower temp for more consistent classification
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def _parse_response(self, response: str, raw_input: str) -> dict[str, Any]:
        """Parse and validate LLM response."""
        try:
            # Strip markdown code blocks if present
            text = response.strip()
            if text.startswith("```"):
                # Remove opening ``` and optional language tag
                lines = text.split("\n")
                lines = lines[1:]  # Remove first line (```json)
                # Remove closing ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)

            data = json.loads(text)

            # Validate with Pydantic
            entry = ClassifiedEntry(**data)

            # Validate type is one of the four
            if entry.type not in ("task", "thought", "person", "event"):
                raise ValueError(f"Invalid type: {entry.type}")

            # Validate priority if present
            if entry.priority and entry.priority not in ("low", "medium", "high"):
                entry.priority = None

            return entry.model_dump()

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            # If parsing fails, return low confidence to trigger manual review
            return {
                "type": "thought",
                "title": raw_input[:100],
                "body": raw_input,
                "confidence": 0.5,
                "tags": [],
                "project": None,
                "people": [],
                "due_date": None,
                "priority": None,
                "parse_error": str(e),
            }

    def _fallback_classification(
        self, raw_input: str, error: str, processing_time_ms: int
    ) -> dict[str, Any]:
        """
        Fallback when LLM is unavailable.

        Trust Guarantee: We NEVER lose a thought.
        """
        return {
            "type": "thought",
            "title": raw_input[:100],
            "body": raw_input,
            "confidence": 0.0,
            "tags": [],
            "project": None,
            "people": [],
            "due_date": None,
            "priority": None,
            "raw_input": raw_input,
            "llm_model": self.model,
            "processing_time_ms": processing_time_ms,
            "status": "fallback",
            "error": error,
            "needs_reclassification": True,
        }


def classify_text(text: str) -> dict[str, Any]:
    """Convenience function to classify a single text."""
    classifier = Classifier()
    return classifier.classify(text)
