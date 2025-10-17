from google import genai
# import google.generativeai as genai
import os
from dotenv import load_dotenv
import json

load_dotenv()

class Gemini:
    def __init__(self, system_message: str | None = None):
        self.client = genai.Client()
        self.system_message = system_message or ""

    def call_gemini_JSON(self, model: str, prompt: str, scheme=None):
        # Convert Pydantic model to JSON schema if provided
        response_schema = None
        if scheme is not None:
            try:
                # Pydantic v2 models expose model_json_schema
                response_schema = scheme.model_json_schema()
            except Exception:
                # Assume already a JSON schema-like dict
                response_schema = scheme

        # Build a single string prompt; the SDK accepts a string for contents
        full_prompt = (self.system_message.strip() + "\n\n" + prompt) if self.system_message else prompt

        response = self.client.models.generate_content(
            model=model,
            contents=full_prompt,
            config={
                "response_mime_type": "application/json",
                **({"response_schema": response_schema} if response_schema else {})
            },
        )

        # Attempt to extract JSON text
        raw_text = None
        if hasattr(response, "text") and response.text:
            raw_text = response.text
        else:
            try:
                cand = response.candidates[0]
                part = cand.content.parts[0]
                raw_text = getattr(part, "text", None) or getattr(part, "inline_data", None)
            except Exception:
                raw_text = None

        if not raw_text:
            return {}

        try:
            data = json.loads(raw_text)
        except Exception:
            # If the model wrapped JSON in code fences or added comments, try to strip
            cleaned = raw_text.strip().strip("`")
            try:
                data = json.loads(cleaned)
            except Exception:
                data = {"raw": raw_text}

        # If a Pydantic model was provided, validate and return dict
        if scheme is not None:
            try:
                model_obj = scheme.model_validate(data)
                return model_obj.model_dump()
            except Exception:
                return data

        return data