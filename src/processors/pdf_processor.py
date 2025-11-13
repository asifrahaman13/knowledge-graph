from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from .pdf_reader import PDFReader
from ..core.logger import log


def _extract_page_text(args: Tuple[str, int]) -> Tuple[int, str]:
    pdf_path, page_num = args
    try:
        from pypdf import PdfReader as PyPDFReader

        reader = PyPDFReader(pdf_path)
        if page_num < len(reader.pages):
            return page_num, reader.pages[page_num].extract_text() or ""
    except ImportError:
        try:
            import PyPDF2

            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if page_num < len(pdf_reader.pages):
                    return page_num, pdf_reader.pages[page_num].extract_text() or ""
        except ImportError:
            pass
    return page_num, ""


class PDFProcessor:
    def __init__(self, file_path: str, use_multiprocessing: bool = True) -> None:
        self.file_path = file_path
        self.pdf_reader = PDFReader()
        self._total_pages = None
        self.use_multiprocessing = use_multiprocessing
        self.max_workers = min(cpu_count(), 8)

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
        if not self.use_multiprocessing or (end_page - start_page) <= 1:
            return self.pdf_reader.read_pdf_pages(self.file_path, start_page, end_page)

        pages = list[int](range(start_page, end_page))
        page_args = [(self.file_path, page_num) for page_num in pages]

        text_parts = [""] * len(pages)

        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_page = {
                    executor.submit(_extract_page_text, args): args[1]
                    for args in page_args
                }

                for future in as_completed(future_to_page):
                    page_num, text = future.result()
                    idx = page_num - start_page
                    if 0 <= idx < len(text_parts):
                        text_parts[idx] = text
        except Exception as e:
            log.warning(f"Multiprocessing failed, falling back to sequential: {e}")
            return self.pdf_reader.read_pdf_pages(self.file_path, start_page, end_page)

        return "\n\n".join(text_parts)
