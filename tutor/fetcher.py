import re
from pathlib import Path
from typing import Callable

import fitz
import httpx
from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    for role in ["navigation", "banner", "contentinfo"]:
        for el in soup.find_all(attrs={"role": role}):
            el.decompose()

    for substring in ["devsite-nav", "devsite-header", "devsite-footer", "devsite-banner"]:
        for el in soup.find_all(class_=lambda c: c and substring in c):
            el.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def pdf_to_text(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n\n".join(pages)


def fetch_resource(
    url: str,
    filename: str,
    resource_type: str,
    docs_dir: Path,
    client: httpx.Client,
) -> tuple[bool, str]:
    target = docs_dir / filename
    if target.exists():
        return False, f"Skipped {filename} (already exists)"

    response = client.get(url, follow_redirects=True)
    response.raise_for_status()

    if resource_type == "pdf":
        text = pdf_to_text(response.content)
    else:
        text = html_to_text(response.text)

    if len(text) < 200:
        return False, f"Warning: {filename} had very little content — page may require a browser"

    target.write_text(text, encoding="utf-8")
    return True, f"Downloaded {filename}"


def fetch_all(
    resources: list[dict[str, str]],
    docs_dir: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, int]:
    results = {"downloaded": 0, "skipped": 0, "failed": 0}

    with httpx.Client(timeout=30, headers={"User-Agent": "cert-tutor/0.1"}) as client:
        for i, resource in enumerate(resources):
            try:
                downloaded, message = fetch_resource(
                    url=resource["url"],
                    filename=resource["filename"],
                    resource_type=resource["type"],
                    docs_dir=docs_dir,
                    client=client,
                )
                if downloaded:
                    results["downloaded"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                message = f"Failed {resource['filename']}: {e}"
                results["failed"] += 1

            if on_progress:
                on_progress(i + 1, len(resources), message)

    return results
