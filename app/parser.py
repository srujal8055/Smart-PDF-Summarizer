import os
import fitz  # PyMuPDF
from typing import Dict, Any, Union, BinaryIO

def extract_pdf_text_and_metadata(file_source: Union[str, BinaryIO, bytes], filename: str = "Unknown") -> Dict[str, Any]:
    """
    Extracts text page-by-page from a PDF file source (either file path, file-like object, or bytes).
    
    Args:
        file_source: The PDF source (path, bytes, or file-like stream).
        filename: Fallback filename if a stream or bytes is passed.
        
    Returns:
        A dictionary containing:
            - "success": (bool) True if parsing succeeded, False otherwise.
            - "filename": (str) The filename of the PDF.
            - "page_count": (int) Total number of pages.
            - "pages": (dict) Mapping of page numbers (1-indexed) to cleaned text strings.
            - "error": (str) Error message, if any.
    """
    result = {
        "success": False,
        "filename": filename,
        "page_count": 0,
        "pages": {},
        "error": None
    }
    
    try:
        doc = None
        # Handle file path
        if isinstance(file_source, str):
            result["filename"] = os.path.basename(file_source)
            doc = fitz.open(file_source)
        # Handle bytes
        elif isinstance(file_source, bytes):
            doc = fitz.open(stream=file_source, filetype="pdf")
        # Handle file-like stream (Streamlit upload)
        else:
            # Check if it has a name attribute (Streamlit's UploadedFile does)
            if hasattr(file_source, "name"):
                result["filename"] = file_source.name
            
            # Read bytes from stream
            if hasattr(file_source, "read"):
                # Seek to start just in case
                if hasattr(file_source, "seek"):
                    file_source.seek(0)
                file_bytes = file_source.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
            else:
                raise ValueError("Unsupported file source type")
        
        if doc is None:
            raise Exception("Failed to open PDF document.")
            
        result["page_count"] = len(doc)
        pages_content = {}
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Extract text using PyMuPDF
            text = page.get_text("text")
            
            # Clean up whitespace
            cleaned_text = clean_text(text)
            
            # Use 1-indexed page numbering
            pages_content[page_num + 1] = cleaned_text
            
        doc.close()
        result["pages"] = pages_content
        result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        
    return result

def clean_text(text: str) -> str:
    """
    Cleans up extracted text by removing excessive whitespace and normalizing newlines.
    """
    if not text:
        return ""
    
    # Split text into lines, strip each line
    lines = [line.strip() for line in text.splitlines()]
    
    # Remove empty lines but keep paragraph breaks (represented by double newlines)
    # We will combine lines that don't end in punctuation or look like sentence continuations,
    # but for simple cleaning, we strip each line and re-join with a single space
    # unless it's an empty line which indicates a paragraph boundary.
    cleaned_paragraphs = []
    current_paragraph = []
    
    for line in lines:
        if line == "":
            if current_paragraph:
                cleaned_paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []
        else:
            current_paragraph.append(line)
            
    if current_paragraph:
        cleaned_paragraphs.append(" ".join(current_paragraph))
        
    return "\n\n".join(cleaned_paragraphs)
