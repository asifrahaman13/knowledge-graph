from enum import Enum


class LLMModels(Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    GPT_4_POINT_1 = "gpt-4.1"


class EmbeddingModels(Enum):
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_3_MEDIUM = "text-embedding-3-medium"
    TEXT_EMBEDDING_3_TINY = "text-embedding-3-tiny"
    TEXT_EMBEDDING_3_X_SMALL = "text-embedding-3-x-small"
    TEXT_EMBEDDING_3_X_LARGE = "text-embedding-3-x-large"
    TEXT_EMBEDDING_3_X_MEDIUM = "text-embedding-3-x-medium"
