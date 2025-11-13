"""
PDF Processor Module
Processes PDF files and extracts text
"""

from typing import List, Tuple
from pdf_reader import PDFReader


class PDFProcessor:
    """Processes PDF files and extracts text"""

    def __init__(self, file_path: str) -> None:
        """Initialize PDF processor"""
        self.file_path = file_path
        self.pdf_reader = PDFReader()
        self._total_pages = None

    def get_total_pages(self) -> int:
        """Get total number of pages in PDF"""
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
        """
        Process PDF file and extract text

        Returns:
            Extracted text from PDF
        """
        return self.pdf_reader.read_pdf(self.file_path)

    def get_page_batches(self, pages_per_batch: int = 10) -> List[Tuple[int, int]]:
        """
        Get list of page ranges for batch processing

        Args:
            pages_per_batch: Number of pages per batch

        Returns:
            List of tuples (start_page, end_page) for each batch
        """
        total_pages = self.get_total_pages()
        batches = []

        for start in range(0, total_pages, pages_per_batch):
            end = min(start + pages_per_batch, total_pages)
            batches.append((start, end))

        return batches

    def process_batch(self, start_page: int, end_page: int) -> str:
        """
        Process a specific page range from PDF

        Args:
            start_page: Start page (0-indexed)
            end_page: End page (0-indexed, exclusive)

        Returns:
            Extracted text from specified pages
        """
        return self.pdf_reader.read_pdf_pages(self.file_path, start_page, end_page)


if __name__ == "__main__":
    pdf_processor = PDFProcessor("static/docs/note.pdf")
    text = pdf_processor.process_pdf()
    print(text)
