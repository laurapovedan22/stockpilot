import hashlib
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.orm import Session

from stockpilot.db.models import PolicyChunk, PolicyDocument


def index_documents(session: Session, directory: Path) -> None:
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).hexdigest()
        existing = session.scalar(select(PolicyDocument).where(PolicyDocument.source == path.name))
        if existing:
            if existing.checksum != checksum:
                raise ValueError("Version document filename before changing an indexed policy")
            continue
        title = content.splitlines()[0].lstrip("# ")
        document = PolicyDocument(
            title=title, version="1.0", source=path.name, checksum=checksum, content=content
        )
        session.add(document)
        session.flush()
        for section in content.split("\n## "):
            lines = section.splitlines()
            for offset in range(0, len(section), 1200):
                session.add(
                    PolicyChunk(
                        document_id=document.id,
                        section=lines[0].lstrip("# "),
                        content=section[offset : offset + 1200],
                    )
                )


def search_policy(session: Session, query: str) -> list[dict]:
    chunks = list(session.scalars(select(PolicyChunk)))
    if not chunks:
        return []
    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform([chunk.content for chunk in chunks])
    scores = cosine_similarity(vectorizer.transform([query]), vectors)[0]
    output = []
    for index in np.argsort(scores)[::-1][:3]:
        if scores[index] < 0.08:
            continue
        chunk = chunks[index]
        document = session.get(PolicyDocument, chunk.document_id)
        if document is None:
            continue
        output.append(
            {
                "type": "document",
                "id": document.id,
                "title": document.title,
                "section": chunk.section,
                "version": document.version,
                "source": document.source,
                "excerpt": chunk.content[:600],
                "score": float(scores[index]),
            }
        )
    return output
