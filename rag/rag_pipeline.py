"""
rag/rag_pipeline.py
--------------------
RAG pipeline: indexes a repo into FAISS, then answers questions
about the codebase using retrieved chunks + NVIDIA NIM LLM.

Usage:
  pipeline = RAGPipeline(store_name="owner_repo")
  await pipeline.index_repo(file_dict)   # file_dict = {path: source_code}
  answer = await pipeline.query("How does authentication work?")
"""
import logging
from typing import Dict, List, Any
from openai import AsyncOpenAI
from rag.vector_store import FAISSVectorStore
from rag.chunker import chunk_file, chunks_to_store_format
from rag.embedder import embed_single
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Extensions worth indexing
INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rb", ".rs", ".cpp", ".c", ".h", ".cs", ".php",
    ".md", ".rst", ".txt",
}

MAX_CONTEXT_CHUNKS = 5  # max chunks to include in LLM context window


class RAGPipeline:
    """
    Encapsulates the full Retrieve-Augment-Generate loop for a single repo.
    """

    def __init__(self, store_name: str):
        self.store = FAISSVectorStore(store_name)
        self.client = AsyncOpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_repo(self, file_dict: Dict[str, str]) -> int:
        """
        Index all source files into the vector store.

        Args:
            file_dict: {relative_file_path: source_code_string}

        Returns:
            Number of chunks indexed.
        """
        self.store.clear()  # Re-index from scratch
        all_texts: List[str] = []
        all_metas: List[Dict[str, Any]] = []

        for file_path, source_code in file_dict.items():
            if not any(file_path.endswith(ext) for ext in INDEXABLE_EXTENSIONS):
                continue
            chunks = chunk_file(source_code, file_path)
            texts, metas = chunks_to_store_format(chunks)
            all_texts.extend(texts)
            all_metas.extend(metas)

        if all_texts:
            self.store.add_texts(all_texts, all_metas)
        logger.info(f"[RAG] Indexed {len(all_texts)} chunks from {len(file_dict)} files.")
        return len(all_texts)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(self, question: str, repo_context: str = "") -> str:
        """
        Answer a question about the codebase using RAG.

        1. Embed the question
        2. Retrieve top-k relevant chunks
        3. Build a context-stuffed prompt
        4. Call NIM LLM for the answer
        """
        # Retrieve relevant chunks
        chunks = self.store.similarity_search(question, k=MAX_CONTEXT_CHUNKS)

        if not chunks:
            context_text = "No relevant code found in the indexed repository."
        else:
            context_parts = []
            for c in chunks:
                context_parts.append(
                    f"--- File: {c.get('file')} (L{c.get('start_line')}-{c.get('end_line')}) ---\n"
                    f"{c.get('text', '')}"
                )
            context_text = "\n\n".join(context_parts)

        system_prompt = (
            "You are an expert software engineer assistant. "
            "Answer questions about the codebase using ONLY the provided code context. "
            "Be specific, mention file names and line numbers when relevant. "
            "If the context doesn't contain enough information, say so clearly."
        )

        user_prompt = f"""Repository: {repo_context}

Relevant code context:
{context_text}

Question: {question}

Provide a clear, accurate answer based on the code above."""

        try:
            response = await self.client.chat.completions.create(
                model=settings.nim_docs_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            return response.choices[0].message.content or "No answer generated."
        except Exception as e:
            logger.error(f"[RAG] LLM query failed: {e}")
            return f"Error generating answer: {str(e)}"

    # ------------------------------------------------------------------
    # Augmented doc generation query
    # ------------------------------------------------------------------

    async def generate_docstring(self, function_code: str, context_query: str = "") -> str:
        """
        Generate a docstring for a specific function using RAG context.
        Used by the documentation generator.
        """
        if context_query:
            relevant = self.store.similarity_search(context_query, k=3)
            extra_context = "\n".join(c.get("text", "") for c in relevant)
        else:
            extra_context = ""

        prompt = f"""Generate a complete, professional docstring for the following function.
Include: description, Args, Returns, Raises (if applicable), Example.

Related codebase context:
{extra_context}

Function:
```python
{function_code}
```

Return ONLY the docstring text (without the triple quotes)."""

        try:
            resp = await self.client.chat.completions.create(
                model=settings.nim_docs_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=512,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"[RAG] Docstring generation failed: {e}")
            return ""
