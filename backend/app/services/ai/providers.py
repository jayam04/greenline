import re
import os
import json
import datetime
from typing import List, Optional
import httpx

from app.services.ai.base import BaseAIProvider, ExtractedRecord, DocumentContext

SYSTEM_PARSE_PROMPT = """
You are an expert financial document parser. Extract all financial transactions from the provided document chunk into a JSON array of objects.
Each object must have the following schema:
{
  "record_type": "investment" or "cashflow",
  "transaction_date": "YYYY-MM-DD",
  "action_type": "buy" | "sell" | "dividend" | "bonus" | "split" | "income" | "expense" | "transfer",
  "account_name_raw": "name of account if mentioned",
  "asset_symbol_raw": "stock/crypto/mutual fund ticker or symbol (e.g. AAPL, INFY)",
  "asset_name_raw": "company or fund name",
  "category_name_raw": "expense or income category (e.g. Food, Groceries, Salary)",
  "quantity": numeric or null,
  "price_per_unit": numeric or null,
  "total_amount": numeric (positive number),
  "fees": numeric or 0.0,
  "taxes": numeric or 0.0,
  "currency": "USD" or "EUR" or "INR" etc.,
  "notes": "brief summary or description",
  "confidence_score": 0.0 to 1.0,
  "source_raw_text": "verbatim text snippet"
}

User context:
- Target Account: {target_account}
- Default Currency: {default_currency}
- User custom instructions: {custom_instructions}
- Known Accounts: {known_accounts}
- Known Categories: {known_categories}
- Known Assets: {known_assets}

Return ONLY valid JSON with no conversational text or markdown code blocks outside of JSON array.
"""

class RuleBasedMockProvider(BaseAIProvider):
    """
    Robust regex and tabular parser used for offline testing, local CSVs,
    and fallback when no AI API keys are configured.
    """
    async def parse_document_chunk(
        self,
        chunk_text: str,
        context: DocumentContext
    ) -> List[ExtractedRecord]:
        records: List[ExtractedRecord] = []
        lines = chunk_text.strip().split("\n")

        date_regex = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})")
        amount_regex = re.compile(r"[$€£₹]?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)")

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("Date") or line_str.startswith("---"):
                continue

            date_match = date_regex.search(line_str)
            if not date_match:
                continue

            raw_date = date_match.group(1).replace("/", "-")
            parsed_date = datetime.date.today()
            try:
                parts = raw_date.split("-")
                if len(parts[0]) == 4:
                    parsed_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                else:
                    parsed_date = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                pass

            # Detect action type
            line_upper = line_str.upper()
            action_type = "expense"
            rec_type = "cashflow"
            if "BUY" in line_upper:
                action_type = "buy"
                rec_type = "investment"
            elif "SELL" in line_upper:
                action_type = "sell"
                rec_type = "investment"
            elif "DIVIDEND" in line_upper:
                action_type = "dividend"
                rec_type = "investment"
            elif "SALARY" in line_upper or "CREDIT" in line_upper or "DEPOSIT" in line_upper or "INCOME" in line_upper:
                action_type = "income"
                rec_type = "cashflow"

            # Detect amount
            amounts = [float(m.replace(",", "")) for m in amount_regex.findall(line_str) if m and m != "."]
            if not amounts:
                continue
            total_amt = amounts[-1] if amounts else 100.0

            # Detect symbol
            sym_match = re.search(r"\b([A-Z]{2,6})\b", line_str)
            symbol = sym_match.group(1) if (sym_match and rec_type == "investment") else None

            records.append(ExtractedRecord(
                record_type=rec_type,
                transaction_date=parsed_date,
                action_type=action_type,
                asset_symbol_raw=symbol,
                asset_name_raw=symbol,
                total_amount=total_amt,
                currency=context.default_currency,
                notes=line_str[:120],
                source_raw_text=line_str,
                confidence_score=0.9
            ))

        return records

class GeminiAIProvider(BaseAIProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model_name

    async def parse_document_chunk(
        self,
        chunk_text: str,
        context: DocumentContext
    ) -> List[ExtractedRecord]:
        prompt = SYSTEM_PARSE_PROMPT.format(
            target_account=context.target_account_name or "None",
            default_currency=context.default_currency,
            custom_instructions=context.custom_instructions or "None",
            known_accounts=str([a.get("account_name") for a in context.existing_accounts]),
            known_categories=str([c.get("name") for c in context.existing_categories]),
            known_assets=str([ast.get("symbol") for ast in context.existing_assets])
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"text": f"Document content to parse:\n\n{chunk_text}"}
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            raw_json_str = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_list = json.loads(raw_json_str)

        return [ExtractedRecord.model_validate(item) for item in parsed_list]

class OllamaAIProvider(BaseAIProvider):
    def __init__(self, host: str = "http://localhost:11434", model_name: str = "llama3.2-vision"):
        self.host = host.rstrip("/")
        self.model_name = model_name

    async def parse_document_chunk(
        self,
        chunk_text: str,
        context: DocumentContext
    ) -> List[ExtractedRecord]:
        prompt = SYSTEM_PARSE_PROMPT.format(
            target_account=context.target_account_name or "None",
            default_currency=context.default_currency,
            custom_instructions=context.custom_instructions or "None",
            known_accounts=str([a.get("account_name") for a in context.existing_accounts]),
            known_categories=str([c.get("name") for c in context.existing_categories]),
            known_assets=str([ast.get("symbol") for ast in context.existing_assets])
        )
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": f"{prompt}\n\nDocument Chunk:\n{chunk_text}",
            "stream": False,
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            parsed_list = json.loads(data.get("response", "[]"))

        return [ExtractedRecord.model_validate(item) for item in parsed_list]

def get_ai_provider(provider_name: Optional[str] = None) -> BaseAIProvider:
    """Factory returning the active AI provider based on environment or settings."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if provider_name == "gemini" and gemini_key:
        return GeminiAIProvider(api_key=gemini_key)

    ollama_host = os.getenv("OLLAMA_HOST")
    if provider_name == "ollama" and ollama_host:
        return OllamaAIProvider(host=ollama_host)

    if gemini_key:
        return GeminiAIProvider(api_key=gemini_key)

    # Default robust rule/regex provider
    return RuleBasedMockProvider()
