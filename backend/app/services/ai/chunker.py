import io
import pandas as pd
from typing import List, Optional
import pypdf

def decrypt_and_extract_pdf_pages(
    file_bytes: bytes,
    password: Optional[str] = None
) -> List[str]:
    """
    Reads a PDF file from bytes, decrypts with password if required,
    and returns a list of extracted text strings per page.
    """
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    if reader.is_encrypted:
        if not password:
            raise ValueError("PDF is password protected. Please provide a password.")
        decrypt_success = reader.decrypt(password)
        if not decrypt_success:
            raise ValueError("Failed to decrypt PDF. Incorrect password.")

    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(f"--- PAGE {idx + 1} ---\n{text}")
    return pages_text

def chunk_pdf_pages(pages_text: List[str], pages_per_chunk: int = 4) -> List[str]:
    """Combines extracted PDF pages into chunk windows."""
    chunks = []
    for i in range(0, len(pages_text), pages_per_chunk):
        chunk_slice = pages_text[i:i + pages_per_chunk]
        chunks.append("\n\n".join(chunk_slice))
    return chunks

def chunk_tabular_data(
    file_bytes: bytes,
    mime_type: str = "text/csv",
    chunk_size: int = 150
) -> List[str]:
    """
    Reads CSV, TSV, or XLSX tabular data and chunks it into markdown/CSV slices
    with headers preserved in each chunk.
    """
    buf = io.BytesIO(file_bytes)
    if "excel" in mime_type or "spreadsheet" in mime_type:
        df = pd.read_excel(buf)
    elif "tsv" in mime_type:
        df = pd.read_csv(buf, sep="\t")
    else:
        # Default CSV
        df = pd.read_csv(buf)

    total_rows = len(df)
    if total_rows == 0:
        return []

    chunks = []
    for start_idx in range(0, total_rows, chunk_size):
        end_idx = min(start_idx + chunk_size, total_rows)
        slice_df = df.iloc[start_idx:end_idx]
        csv_chunk = slice_df.to_csv(index=False)
        chunks.append(csv_chunk)

    return chunks
