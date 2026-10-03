from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import Optional

from models.database import get_db
from models.entities import User, Document, DocumentChunk, ChatSession
from auth.jwt import get_current_user
from core.rag_engine import RAGEngine
from core.config import settings
from core.limiter import limiter, get_user_or_ip

router = APIRouter(tags=["rag"])

@router.post("/api/rag/upload")
@router.post("/api/upload/document")
@limiter.limit(settings.UPLOAD_RATE_LIMIT, key_func=get_user_or_ip)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not session_id:
        # Find latest session or create one
        latest_session = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()).first()
        if not latest_session:
            latest_session = ChatSession(user_id=current_user.id, title="New Chat Session")
            db.add(latest_session)
            db.commit()
            db.refresh(latest_session)
        session_id = latest_session.id

    content = await file.read()
    try:
        raw_text = RAGEngine.extract_text(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract document text: {str(e)}")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Uploaded document contains no extractable text.")

    # Extract chunks immediately upon upload
    chunks = RAGEngine.chunk_text(raw_text)

    # Deactivate / remove previous document for this session to maintain 1 active document per context
    previous_docs = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.session_id == session_id
    ).all()
    for prev in previous_docs:
        db.delete(prev)
    db.commit()

    # Create new document record persisted to database
    doc = Document(
        user_id=current_user.id,
        session_id=session_id,
        filename=file.filename,
        file_type=file.filename.split('.')[-1].lower(),
        raw_text=raw_text,
        is_active=True
    )
    db.add(doc)
    db.flush()

    # Persist all individual chunks into document_chunks table
    chunk_objs = [
        DocumentChunk(document_id=doc.id, chunk_index=idx, content=chunk_text)
        for idx, chunk_text in enumerate(chunks)
    ]
    db.add_all(chunk_objs)
    db.commit()
    db.refresh(doc)

    return {
        "status": "success",
        "filename": doc.filename,
        "session_id": session_id,
        "document_id": doc.id,
        "character_count": len(raw_text),
        "chunk_count": len(chunks)
    }

@router.get("/api/rag/status")
@router.get("/api/upload/document/status")
def get_rag_status(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = None
    # 1. Prioritize session-bound document
    if session_id:
        doc = db.query(Document).filter(
            Document.user_id == current_user.id,
            Document.session_id == session_id,
            Document.is_active == True
        ).order_by(Document.created_at.desc()).first()

    # 2. Fallback to latest active document for this user
    if not doc:
        doc = db.query(Document).filter(
            Document.user_id == current_user.id,
            Document.is_active == True
        ).order_by(Document.created_at.desc()).first()

    if not doc:
        return {"active": False, "filename": None}

    return {
        "active": True, 
        "filename": doc.filename, 
        "session_id": doc.session_id,
        "document_id": doc.id,
        "chunk_count": len(doc.chunks)
    }

@router.delete("/api/rag/document")
@router.delete("/api/upload/document")
def delete_rag_document(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if session_id:
        query = query.filter(Document.session_id == session_id)
    
    docs_to_delete = query.all()
    count = len(docs_to_delete)
    for d in docs_to_delete:
        db.delete(d)
    db.commit()

    return {"status": "success", "deleted_count": count}
