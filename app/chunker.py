import re
from typing import List, Dict, Any

def chunk_document(pages_dict: Dict[int, str], max_chars: int = 3000, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Chunks a parsed document's text into blocks of max_chars size, preserving sentence boundaries
    where possible, and tracks page numbers for each chunk.
    
    Args:
        pages_dict: Dictionary mapping page numbers (1-indexed) to cleaned text.
        max_chars: Maximum characters per chunk (approximate target).
        overlap: Character overlap between contiguous chunks to maintain context (optional).
        
    Returns:
        List of dictionaries, each representing a chunk:
        {
            "index": int (1-indexed chunk number),
            "text": str (chunk text content),
            "pages": List[int] (list of source pages contributing to this chunk),
            "char_count": int (character length)
        }
    """
    chunks = []
    current_chunk_text = ""
    current_pages = []
    
    # Sort pages by page number
    sorted_pages = sorted(pages_dict.items())
    
    for page_num, page_text in sorted_pages:
        if not page_text.strip():
            continue
            
        # We can split the page's text into paragraphs first
        paragraphs = page_text.split("\n\n")
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # If adding this paragraph to current chunk exceeds max_chars
            if len(current_chunk_text) + len(para) + 2 > max_chars:
                # If current chunk is already populated, save it
                if current_chunk_text:
                    chunks.append({
                        "index": len(chunks) + 1,
                        "text": current_chunk_text.strip(),
                        "pages": list(sorted(set(current_pages))),
                        "char_count": len(current_chunk_text.strip())
                    })
                    # Set up the next chunk with overlap from the end of the current chunk if requested
                    if overlap > 0 and len(current_chunk_text) > overlap:
                        # Find a sentence boundary within the overlap window to avoid hard cuts
                        overlap_candidate = current_chunk_text[-overlap:]
                        sentence_start_idx = overlap_candidate.find(". ")
                        if sentence_start_idx != -1 and sentence_start_idx < len(overlap_candidate) - 10:
                            current_chunk_text = overlap_candidate[sentence_start_idx + 2:]
                        else:
                            current_chunk_text = overlap_candidate
                    else:
                        current_chunk_text = ""
                        current_pages = []
                
                # If the single paragraph itself is larger than max_chars, split by sentences
                if len(para) > max_chars:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if not sentence:
                            continue
                        
                        if len(current_chunk_text) + len(sentence) + 1 > max_chars:
                            if current_chunk_text:
                                chunks.append({
                                    "index": len(chunks) + 1,
                                    "text": current_chunk_text.strip(),
                                    "pages": list(sorted(set(current_pages))),
                                    "char_count": len(current_chunk_text.strip())
                                })
                                current_chunk_text = ""
                                current_pages = []
                            
                            # If a single sentence exceeds max_chars, chunk it by characters
                            if len(sentence) > max_chars:
                                for i in range(0, len(sentence), max_chars):
                                    sub_chunk = sentence[i:i+max_chars]
                                    chunks.append({
                                        "index": len(chunks) + 1,
                                        "text": sub_chunk,
                                        "pages": [page_num],
                                        "char_count": len(sub_chunk)
                                    })
                                current_chunk_text = ""
                                current_pages = []
                            else:
                                current_chunk_text = sentence
                                current_pages = [page_num]
                        else:
                            current_chunk_text = f"{current_chunk_text} {sentence}".strip() if current_chunk_text else sentence
                            if page_num not in current_pages:
                                current_pages.append(page_num)
                else:
                    current_chunk_text = para
                    current_pages = [page_num]
            else:
                # Add paragraph to current chunk
                if current_chunk_text:
                    current_chunk_text = f"{current_chunk_text}\n\n{para}"
                else:
                    current_chunk_text = para
                if page_num not in current_pages:
                    current_pages.append(page_num)
                    
    # Add final remaining chunk if any
    if current_chunk_text.strip():
        chunks.append({
            "index": len(chunks) + 1,
            "text": current_chunk_text.strip(),
            "pages": list(sorted(set(current_pages))),
            "char_count": len(current_chunk_text.strip())
        })
        
    return chunks

if __name__ == "__main__":
    # Standard helper script execution for testing chunker directly
    import sys
    import json
    from parser import extract_pdf_text_and_metadata
    
    if len(sys.argv) < 2:
        print("Usage: python chunker.py <path_to_pdf>")
    else:
        pdf_path = sys.argv[1]
        print(f"Parsing PDF: {pdf_path}")
        parse_result = extract_pdf_text_and_metadata(pdf_path)
        if parse_result["success"]:
            print(f"Extraction successful! Page count: {parse_result['page_count']}")
            print("Chunking document...")
            chunks_list = chunk_document(parse_result["pages"], max_chars=3000)
            print(f"Created {len(chunks_list)} chunks.")
            for c in chunks_list:
                print(f"\n--- CHUNK {c['index']} (Pages: {c['pages']}, Chars: {c['char_count']}) ---")
                print(c["text"][:300] + ("..." if len(c["text"]) > 300 else ""))
        else:
            print(f"Error parsing PDF: {parse_result['error']}")
