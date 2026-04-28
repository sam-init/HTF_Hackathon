"""
utils/doc_router.py
-------------------
FastAPI router for the Documentation Generator endpoints.

Endpoints:
  POST /docs/generate/zip      - Upload a ZIP file, get README + graph
  POST /docs/generate/github   - Provide GitHub repo URL, get README + graph
  GET  /docs/query             - Ask a question about an indexed repo (RAG)
"""
import asyncio
import logging
import tempfile
import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional

from docs.repo_loader import load_from_zip, load_from_github
from docs.parser import parse_repo
from docs.readme_generator import generate_readme, PersonaMode
from docs.graph_builder import build_dependency_graph, save_graph_image
from rag.rag_pipeline import RAGPipeline
from config.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/docs", tags=["documentation"])

OUTPUT_DIR = Path("./data/docs_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class GithubDocRequest(BaseModel):
    repo_url: str                         # e.g. "https://github.com/owner/repo"
    persona: PersonaMode = "backend"
    ref: str = "main"
    token: Optional[str] = None           # optional PAT for private repos


class RAGQueryRequest(BaseModel):
    store_name: str   # must match a previously indexed repo
    question: str


async def _run_doc_pipeline(
    file_dict: dict,
    repo_name: str,
    persona: PersonaMode,
    job_id: str,
) -> dict:
    """
    Core pipeline: parse → index → generate README + graph.
    Returns paths to generated files.
    """
    # 1. Parse AST
    parsed = parse_repo(file_dict)

    # 2. Index into RAG vector store
    store_name = repo_name.replace("/", "_").replace("-", "_")
    pipeline = RAGPipeline(store_name)
    chunk_count = await pipeline.index_repo(file_dict)

    # 3. Generate README (LLM call)
    readme_text = await generate_readme(parsed, repo_name, persona=persona)

    # 4. Build dependency graph image
    G = build_dependency_graph(parsed)
    graph_path = str(OUTPUT_DIR / f"{job_id}_dep_graph.png")
    save_graph_image(G, graph_path)

    # 5. Save README to disk
    readme_path = str(OUTPUT_DIR / f"{job_id}_README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_text)

    # 6. Update DB job record
    async with get_db() as db:
        await db.execute(
            "UPDATE doc_jobs SET status='completed', result_path=? WHERE id=?",
            (readme_path, job_id),
        )
        await db.commit()

    logger.info(f"[DocRouter] Job {job_id} complete. {chunk_count} chunks indexed.")
    return {
        "readme_path": readme_path,
        "graph_path": graph_path,
        "chunks_indexed": chunk_count,
        "files_parsed": len(parsed),
    }


@router.post("/generate/zip")
async def generate_from_zip(
    persona: PersonaMode = "backend",
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a ZIP of your codebase → get a generated README.md + dependency graph.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted.")

    zip_bytes = await file.read()
    if len(zip_bytes) > 50_000_000:  # 50MB limit
        raise HTTPException(status_code=413, detail="ZIP file too large (max 50MB).")

    # Create DB job record
    async with get_db() as db:
        result = await db.execute(
            "INSERT INTO doc_jobs (repo_url, status) VALUES (?, 'processing')",
            (file.filename,),
        )
        job_id = str(result.lastrowid)
        await db.commit()

    try:
        file_dict = load_from_zip(zip_bytes)
        repo_name = Path(file.filename).stem
        result = await _run_doc_pipeline(file_dict, repo_name, persona, job_id)
        return JSONResponse({
            "job_id": job_id,
            "status": "completed",
            "persona": persona,
            **result,
        })
    except Exception as e:
        logger.exception(f"[DocRouter] ZIP pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/github")
async def generate_from_github(req: GithubDocRequest):
    """
    Provide a GitHub repo URL → get a generated README.md + dependency graph.
    """
    # Parse owner/repo from URL
    parts = req.repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL.")
    repo_full = f"{parts[-2]}/{parts[-1]}"

    async with get_db() as db:
        result = await db.execute(
            "INSERT INTO doc_jobs (repo_url, status) VALUES (?, 'processing')",
            (req.repo_url,),
        )
        job_id = str(result.lastrowid)
        await db.commit()

    try:
        file_dict = await load_from_github(repo_full, token=req.token or "", ref=req.ref)
        result = await _run_doc_pipeline(file_dict, repo_full, req.persona, job_id)
        return JSONResponse({
            "job_id": job_id,
            "status": "completed",
            "repo": repo_full,
            "persona": req.persona,
            **result,
        })
    except Exception as e:
        logger.exception(f"[DocRouter] GitHub pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/readme/{job_id}")
async def download_readme(job_id: str):
    """Download the generated README.md for a job."""
    readme_path = OUTPUT_DIR / f"{job_id}_README.md"
    if not readme_path.exists():
        raise HTTPException(status_code=404, detail="README not found for this job.")
    return FileResponse(str(readme_path), media_type="text/markdown", filename="README.md")


@router.get("/download/graph/{job_id}")
async def download_graph(job_id: str):
    """Download the dependency graph PNG for a job."""
    graph_path = OUTPUT_DIR / f"{job_id}_dep_graph.png"
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Graph not found for this job.")
    return FileResponse(str(graph_path), media_type="image/png", filename="dependency_graph.png")


@router.post("/query")
async def query_codebase(req: RAGQueryRequest):
    """
    Ask a natural-language question about a previously indexed codebase.
    Returns an AI-generated answer using RAG.
    """
    store_name = req.store_name.replace("/", "_").replace("-", "_")
    pipeline = RAGPipeline(store_name)
    answer = await pipeline.query(req.question, repo_context=req.store_name)
    return {"question": req.question, "answer": answer, "store": store_name}
