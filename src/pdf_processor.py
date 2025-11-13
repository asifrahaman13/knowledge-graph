from typing import List, Tuple
from pdf_reader import PDFReader


class PDFProcessor:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.pdf_reader = PDFReader()
        self._total_pages = None

    def get_total_pages(self) -> int:
        if self._total_pages is None:
            try:
                from pypdf import PdfReader as PyPDFReader

                reader = PyPDFReader(self.file_path)
                self._total_pages = len(reader.pages)
            except ImportError:
                try:
                    import PyPDF2

                    with open(self.file_path, "rb") as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        self._total_pages = len(pdf_reader.pages)
                except ImportError:
                    raise ImportError(
                        "No PDF library found. Please install one: "
                        "pip install pypdf OR pip install PyPDF2"
                    )
        return self._total_pages

    def process_pdf(self) -> str:
        return self.pdf_reader.read_pdf(self.file_path)

    def get_page_batches(self, pages_per_batch: int = 10) -> List[Tuple[int, int]]:
        total_pages = self.get_total_pages()
        batches = []

        for start in range(0, total_pages, pages_per_batch):
            end = min(start + pages_per_batch, total_pages)
            batches.append((start, end))

        return batches

    def process_batch(self, start_page: int, end_page: int) -> str:
        return self.pdf_reader.read_pdf_pages(self.file_path, start_page, end_page)
