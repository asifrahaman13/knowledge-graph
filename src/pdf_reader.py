from typing import Optional
import os


class PDFReader:
    def __init__(self):
        pass

    def read_pdf(self, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            from pypdf import PdfReader as PyPDFReader

            reader = PyPDFReader(pdf_path)
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except ImportError:
            try:
                import PyPDF2

                with open(pdf_path, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text_parts = []

                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)

                    return "\n\n".join(text_parts)

            except ImportError:
                raise ImportError(
                    "No PDF library found. Please install one: "
                    "pip install pypdf OR pip install PyPDF2"
                )

    def read_pdf_pages(
        self,
        pdf_path: str,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            from pypdf import PdfReader as PyPDFReader

            reader = PyPDFReader(pdf_path)
            total_pages = len(reader.pages)

            start = start_page if start_page is not None else 0
            end = end_page if end_page is not None else total_pages

            start = max(0, min(start, total_pages - 1))
            end = max(start + 1, min(end, total_pages))

            text_parts = []
            for i in range(start, end):
                text = reader.pages[i].extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except ImportError:
            try:
                import PyPDF2

                with open(pdf_path, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)

                    start = start_page if start_page is not None else 0
                    end = end_page if end_page is not None else total_pages

                    start = max(0, min(start, total_pages - 1))
                    end = max(start + 1, min(end, total_pages))

                    text_parts = []
                    for i in range(start, end):
                        text = pdf_reader.pages[i].extract_text()
                        if text:
                            text_parts.append(text)

                    return "\n\n".join(text_parts)

            except ImportError:
                raise ImportError(
                    "No PDF library found. Please install one: "
                    "pip install pypdf OR pip install PyPDF2"
                )
