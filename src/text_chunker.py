from typing import List
import re


class TextChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[dict]:
        if not text:
            return []

        text = text.strip()

        sentences = self._split_sentences(text)

        chunks = []
        current_chunk = ""
        current_length = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > self.chunk_size and current_chunk:
                start_char = sum(len(c["text"]) for c in chunks) if chunks else 0
                chunk_text = current_chunk.strip()

                chunks.append(
                    {
                        "text": chunk_text,
                        "chunk_index": chunk_index,
                        "start_char": start_char,
                        "end_char": start_char + len(chunk_text),
                    }
                )
                chunk_index += 1

                if self.chunk_overlap > 0 and chunks:
                    overlap_text = self._get_overlap_text(
                        current_chunk, self.chunk_overlap
                    )
                    current_chunk = overlap_text + " " + sentence
                    current_length = len(current_chunk)
                else:
                    current_chunk = sentence
                    current_length = sentence_length
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_length = len(current_chunk)

        if current_chunk:
            start_char = sum(len(c["text"]) for c in chunks) if chunks else 0
            chunk_text = current_chunk.strip()
            chunks.append(
                {
                    "text": chunk_text,
                    "chunk_index": chunk_index,
                    "start_char": start_char,
                    "end_char": start_char + len(chunk_text),
                }
            )

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        pattern = r"([.!?]+)\s+"
        sentences = re.split(pattern, text)

        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]
            if sentence.strip():
                result.append(sentence.strip())

        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())

        return result

    def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        if len(text) <= overlap_size:
            return text
        return text[-overlap_size:]
