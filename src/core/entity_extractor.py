from typing import List, Dict, Any, Optional
import json
import asyncio
import hashlib
from openai import OpenAI, AsyncOpenAI

from ..config.models import LLMModels
from ..storage.redis_cache import RedisCache


LEGAL_SYSTEM_PROMPT = """
You are an expert legal analyst specializing in extracting entities and relationships from legal documents.
Extract legal entities (parties, laws, regulations, cases, courts, legal concepts, contracts, clauses, etc.) and their legal relationships.
Return a JSON object with 'nodes' and 'relationships' arrays.

IMPORTANT RULES:
1. NEVER use 'id' as a property name (use 'identifier', 'unique_id', 'case_number', 'article_number', or other names instead)
2. Each node should have a 'name' property
3. Each node should have 'labels' array with legal-specific labels such as:
   - ["Party"], ["Plaintiff"], ["Defendant"], ["Lawyer"], ["LawFirm"]
   - ["Law"], ["Regulation"], ["Statute"], ["Article"], ["Section"]
   - ["Case"], ["Court"], ["Judge"], ["Jurisdiction"]
   - ["Contract"], ["Clause"], ["Provision"], ["Term"]
   - ["LegalConcept"], ["Doctrine"], ["Principle"], ["Precedent"]
   - ["Organization"], ["Agency"], ["Institution"]
4. Relationships should have 'type', 'source', 'target', and optional 'properties'
5. Use legal-specific relationship types such as:
   - "SUES", "REPRESENTS", "DEFENDS", "PROSECUTES"
   - "VIOLATES", "ENFORCES", "INTERPRETS", "APPLIES"
   - "REFERENCES", "CITES", "OVERRULES", "AFFIRMS"
   - "AMENDS", "REPEALS", "SUPERSEDES", "CONFLICTS_WITH"
   - "CONTAINS", "DEFINES", "ESTABLISHES", "PROHIBITS"
   - "REQUIRES", "PERMITS", "AUTHORIZES", "MANDATES"
6. Be consistent with entity names (same entity should have same name across the document)
7. Extract legal dates, case numbers, article numbers, and other legal identifiers as properties

Example format:
{
  "nodes": [
    {
      "labels": ["Party", "Plaintiff"],
      "properties": {
        "name": "John Doe",
        "role": "plaintiff"
      }
    },
    {
      "labels": ["Law", "Statute"],
      "properties": {
        "name": "Civil Rights Act of 1964",
        "year": 1964
      }
    },
    {
      "labels": ["Case"],
      "properties": {
        "name": "Doe v. Smith",
        "case_number": "2024-CV-1234"
      }
    }
  ],
  "relationships": [
    {
      "type": "SUES",
      "source": "John Doe",
      "target": "Smith Corporation",
      "properties": {
        "date": "2024-01-15"
      }
    },
    {
      "type": "VIOLATES",
      "source": "Smith Corporation",
      "target": "Civil Rights Act of 1964",
      "properties": {
        "section": "Title VII"
      }
    },
    {
      "type": "CITES",
      "source": "Doe v. Smith",
      "target": "Civil Rights Act of 1964",
      "properties": {}
    }
  ]
}"""


LEGAL_EXTRACTION_PROMPT = """
Extract all legal entities and relationships from the following legal document text.

Focus on:
- Legal parties (plaintiffs, defendants, lawyers, law firms, organizations)
- Laws, regulations, statutes, articles, and sections
- Legal cases, court decisions, and precedents
- Courts, judges, and jurisdictions
- Contracts, clauses, provisions, and terms
- Legal concepts, doctrines, principles, and precedents
- Legal relationships (sues, represents, violates, enforces, cites, etc.)

Text:
{text}

Return a JSON object with:
- "nodes": array of legal entities with appropriate labels (Party, Law, Case, Court, Contract, LegalConcept, etc.) and properties
- "relationships": array of legal relationships with type (SUES, REPRESENTS, VIOLATES, ENFORCES, CITES, etc.), source, target, and properties

Important:
- NEVER use 'id' as a property name (use 'identifier', 'case_number', 'article_number', etc.)
- Include legal identifiers like case numbers, article numbers, dates, and section references as properties
- Use legal-specific labels and relationship types
- Be precise with legal terminology and maintain consistency"""


class EntityRelationshipExtractor:
    def __init__(
        self,
        api_key: str,
        model: str = LLMModels.GPT_4_POINT_1.value,
        redis_cache: Optional[RedisCache] = None,
        cache_ttl: int = 86400 * 3,
    ):
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.cache = redis_cache
        self.cache_ttl = cache_ttl

    def _get_cache_key(self, text: str) -> str:
        text_hash = hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()
        return f"extraction:{self.model}:{text_hash}"

    def extract(self, text: str) -> Dict[str, Any]:
        if self.cache:
            cache_key = self._get_cache_key(text)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        prompt = self._create_extraction_prompt(text)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )

            content = response.choices[0].message.content
            if not content:
                raise Exception("LLM returned empty response")

            result = json.loads(content)
            validated_result = self._validate_result(result)

            if self.cache:
                cache_key = self._get_cache_key(text)
                self.cache.set(
                    cache_key, validated_result, ttl=self.cache_ttl, serialize=True
                )

            return validated_result

        except Exception as e:
            raise Exception(f"Error extracting entities: {e}")

    async def async_extract(self, text: str) -> Dict[str, Any]:
        if self.cache:
            cache_key = self._get_cache_key(text)
            cached = await self.cache.async_get(cache_key)
            if cached is not None:
                return cached

        prompt = self._create_extraction_prompt(text)

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )

            content = response.choices[0].message.content
            if not content:
                raise Exception("LLM returned empty response")

            result = json.loads(content)
            validated_result = self._validate_result(result)

            if self.cache:
                cache_key = self._get_cache_key(text)
                await self.cache.async_set(
                    cache_key, validated_result, ttl=self.cache_ttl, serialize=True
                )

            return validated_result

        except Exception as e:
            raise Exception(f"Error extracting entities: {e}")

    async def async_extract_batch(
        self, texts: List[str], max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_with_semaphore(text: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.async_extract(text)

        tasks = [extract_with_semaphore(text) for text in texts]
        results = await asyncio.gather(*tasks)
        return results

    def _get_system_prompt(self) -> str:
        return LEGAL_SYSTEM_PROMPT

    def _create_extraction_prompt(self, text: str) -> str:
        return LEGAL_EXTRACTION_PROMPT.format(text=text)

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if "nodes" not in result:
            result["nodes"] = []
        if "relationships" not in result:
            result["relationships"] = []

        for node in result["nodes"]:
            if "properties" in node and isinstance(node["properties"], dict):
                if "id" in node["properties"]:
                    node["properties"]["identifier"] = node["properties"].pop("id")

        for node in result["nodes"]:
            if "labels" not in node or not node["labels"]:
                node["labels"] = ["Entity"]

        valid_relationships = []
        for rel in result["relationships"]:
            if all(key in rel for key in ["type", "source", "target"]):
                valid_relationships.append(rel)
        result["relationships"] = valid_relationships

        return result
