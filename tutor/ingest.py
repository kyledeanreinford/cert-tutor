import hashlib
import json
import uuid
from pathlib import Path

import chromadb
import fitz
from rich.progress import Progress

from tutor.openai_client import OpenAIEmbedder


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_text(pdf_path: Path) -> list[dict[str, str | int]]:
    doc = fitz.open(pdf_path)
    pages: list[dict[str, str | int]] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        if text.strip():
            pages.append({"text": text, "page": page_num, "source": pdf_path.name})
    doc.close()
    return pages


def extract_text_from_txt(txt_path: Path, page_size: int = 3000) -> list[dict[str, str | int]]:
    text = txt_path.read_text(encoding="utf-8")
    pages: list[dict[str, str | int]] = []
    page_num = 1
    start = 0
    while start < len(text):
        page_text = text[start : start + page_size]
        if page_text.strip():
            pages.append({"text": page_text, "page": page_num, "source": txt_path.name})
            page_num += 1
        start += page_size
    return pages


def chunk_pages(
    pages: list[dict[str, str | int]], chunk_size: int, chunk_overlap: int
) -> list[dict[str, str | int]]:
    chunks: list[dict[str, str | int]] = []
    for page in pages:
        text = str(page["text"])
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "source": page["source"],
                    "page": page["page"],
                    "chunk_id": str(uuid.uuid4()),
                })
            start += chunk_size - chunk_overlap
    return chunks


def load_index_state(data_dir: Path) -> dict[str, str]:
    index_file = data_dir / "indexed.json"
    if index_file.exists():
        return json.loads(index_file.read_text())
    return {}


def save_index_state(data_dir: Path, state: dict[str, str]) -> None:
    index_file = data_dir / "indexed.json"
    index_file.write_text(json.dumps(state, indent=2))


def ingest(
    docs_dir: Path,
    chroma_dir: Path,
    data_dir: Path,
    embedder: OpenAIEmbedder,
    chunk_size: int,
    chunk_overlap: int,
    reset: bool = False,
) -> None:
    chroma = chromadb.PersistentClient(path=str(chroma_dir))

    if reset:
        try:
            chroma.delete_collection("cert_docs")
        except ValueError:
            pass
        save_index_state(data_dir, {})

    collection = chroma.get_or_create_collection("cert_docs")
    index_state = load_index_state(data_dir) if not reset else {}

    files = list(docs_dir.glob("*.pdf")) + list(docs_dir.glob("*.txt"))
    if not files:
        print("No PDF or TXT files found in docs/. Add some and try again.")
        return

    with Progress() as progress:
        task = progress.add_task("Indexing documents...", total=len(files))
        for file_path in files:
            current_hash = file_hash(file_path)
            if file_path.name in index_state and index_state[file_path.name] == current_hash:
                progress.console.print(f"  Skipping {file_path.name} (unchanged)")
                progress.advance(task)
                continue

            progress.console.print(f"  Processing {file_path.name}...")
            if file_path.suffix.lower() == ".pdf":
                pages = extract_text(file_path)
            else:
                pages = extract_text_from_txt(file_path)
            chunks = chunk_pages(pages, chunk_size, chunk_overlap)

            for chunk in chunks:
                embedding = embedder.embed(str(chunk["text"]))
                collection.upsert(
                    ids=[str(chunk["chunk_id"])],
                    embeddings=[embedding],
                    documents=[str(chunk["text"])],
                    metadatas=[{"source": str(chunk["source"]), "page": int(chunk["page"])}],
                )

            index_state[file_path.name] = current_hash
            progress.advance(task)

    save_index_state(data_dir, index_state)
    count = collection.count()
    print(f"Done. {count} chunks in the vector store.")
