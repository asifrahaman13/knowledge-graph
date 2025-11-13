"""
Entity and Relationship Extraction Module
Uses LLM to extract entities and relationships from text
"""

from typing import List, Dict, Any
import json
import asyncio
from openai import OpenAI, AsyncOpenAI


class EntityRelationshipExtractor:
    """Extracts entities and relationships from text using LLM"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize entity extractor

        Args:
            api_key: OpenAI API key
            model: LLM model to use
        """
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.model = model

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract entities and relationships from text

        Args:
            text: Text to extract from

        Returns:
            Dictionary with 'nodes' and 'relationships' lists
        """
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

            # Validate and clean result
            return self._validate_result(result)

        except Exception as e:
            raise Exception(f"Error extracting entities: {e}")

    async def async_extract(self, text: str) -> Dict[str, Any]:
        """
        Extract entities and relationships from text (async)

        Args:
            text: Text to extract from

        Returns:
            Dictionary with 'nodes' and 'relationships' lists
        """
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

            # Validate and clean result
            return self._validate_result(result)

        except Exception as e:
            raise Exception(f"Error extracting entities: {e}")

    async def async_extract_batch(
        self, texts: List[str], max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Extract entities and relationships from multiple texts in parallel

        Args:
            texts: List of texts to extract from
            max_concurrent: Maximum number of concurrent extractions

        Returns:
            List of dictionaries with 'nodes' and 'relationships' lists
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_with_semaphore(text: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.async_extract(text)

        tasks = [extract_with_semaphore(text) for text in texts]
        results = await asyncio.gather(*tasks)
        return results

    def _get_system_prompt(self) -> str:
        """Get system prompt for extraction"""
        return """You are an expert at extracting entities and relationships from text.
Extract entities (people, places, concepts, organizations, etc.) and their relationships.
Return a JSON object with 'nodes' and 'relationships' arrays.

IMPORTANT RULES:
1. NEVER use 'id' as a property name (use 'identifier', 'unique_id', or other names instead)
2. Each node should have a 'name' property
3. Each node should have 'labels' array (e.g., ["Person"], ["Location"], ["Concept"])
4. Relationships should have 'type', 'source', 'target', and optional 'properties'
5. Use meaningful relationship types (e.g., "LIVES_IN", "WORKS_FOR", "HAS_PROPERTY")
6. Be consistent with entity names (same entity should have same name)

Example format:
{
  "nodes": [
    {
      "labels": ["Person"],
      "properties": {
        "name": "John Doe",
        "age": 30
      }
    }
  ],
  "relationships": [
    {
      "type": "LIVES_IN",
      "source": "John Doe",
      "target": "New York",
      "properties": {}
    }
  ]
}"""

    def _create_extraction_prompt(self, text: str) -> str:
        """Create extraction prompt"""
        return f"""Extract all entities and relationships from the following text.

Text:
{text}

Return a JSON object with:
- "nodes": array of entities with labels and properties
- "relationships": array of relationships with type, source, target, and properties

Remember: NEVER use 'id' as a property name."""

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extraction result"""
        # Ensure required keys exist
        if "nodes" not in result:
            result["nodes"] = []
        if "relationships" not in result:
            result["relationships"] = []

        # Clean nodes: remove 'id' properties
        for node in result["nodes"]:
            if "properties" in node and isinstance(node["properties"], dict):
                if "id" in node["properties"]:
                    # Rename 'id' to 'identifier'
                    node["properties"]["identifier"] = node["properties"].pop("id")

        # Ensure nodes have labels
        for node in result["nodes"]:
            if "labels" not in node or not node["labels"]:
                node["labels"] = ["Entity"]

        # Ensure relationships have required fields
        valid_relationships = []
        for rel in result["relationships"]:
            if all(key in rel for key in ["type", "source", "target"]):
                valid_relationships.append(rel)
        result["relationships"] = valid_relationships

        return result
