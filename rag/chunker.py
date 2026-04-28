"""
rag/chunker.py
--------------
Splits source code files into semantically meaningful chunks for indexing.

Strategy:
  - Python files: split by function/class definition boundaries
  - Other files: fixed-size sliding window with overlap
  - Each chunk carries metadata: file, type, start_line, end_line
"""
import re
from typing import List, Dict, Any, Tuple

# Fixed chunking defaults
CHUNK_SIZE = 60     # lines per chunk
CHUNK_OVERLAP = 10  # lines of overlap between chunks


def chunk_python_file(source: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Split a Python source file at function and class boundaries.
    Falls back to fixed-size chunking for files without clear boundaries.
    """
    lines = source.splitlines()
    chunks: List[Dict[str, Any]] = []

    # Find function/class definition start lines
    boundary_pattern = re.compile(r"^(?:def |class |async def )\s*\w+", re.MULTILINE)
    boundaries: List[int] = []
    for m in boundary_pattern.finditer(source):
        line_no = source[:m.start()].count("\n")
        boundaries.append(line_no)

    if len(boundaries) < 2:
        # Fall back to fixed-size chunking
        return chunk_fixed(source, file_path)

    # Add end sentinel
    boundaries.append(len(lines))
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = min(boundaries[i + 1], len(lines))
        chunk_lines = lines[start:end]
        if not chunk_lines:
            continue
        chunk_text = "\n".join(chunk_lines)
        chunks.append({
            "file": file_path,
            "type": "code_block",
            "start_line": start + 1,
            "end_line": end,
            "chunk_text": chunk_text,
        })

    return chunks


def chunk_fixed(source: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Fixed-size sliding window chunker for non-Python files.
    """
    lines = source.splitlines()
    chunks = []
    i = 0
    while i < len(lines):
        chunk_lines = lines[i: i + CHUNK_SIZE]
        chunk_text = "\n".join(chunk_lines)
        chunks.append({
            "file": file_path,
            "type": "code_block",
            "start_line": i + 1,
            "end_line": min(i + CHUNK_SIZE, len(lines)),
            "chunk_text": chunk_text,
        })
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def chunk_file(source: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Dispatch to the appropriate chunking strategy based on file extension.
    """
    if file_path.endswith(".py"):
        return chunk_python_file(source, file_path)
    return chunk_fixed(source, file_path)


def chunks_to_store_format(
    chunks: List[Dict[str, Any]]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Convert chunk dicts into (texts, metadatas) suitable for FAISSVectorStore.add_texts().
    """
    texts = [c["chunk_text"] for c in chunks]
    metadatas = [{k: v for k, v in c.items() if k != "chunk_text"} for c in chunks]
    return texts, metadatas
