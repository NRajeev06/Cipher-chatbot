from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models.database import get_db
from models.entities import User, ChatSession, ChatMessage
from auth.jwt import get_current_user
from core.hf_client import hf_client
from core.config import settings
from core.limiter import limiter, get_user_or_ip

router = APIRouter(tags=["image"])

class ImageRequest(BaseModel):
    prompt: str
    session_id: str

@router.post("/api/chat/image")
@router.post("/api/image/generate")
@limiter.limit(settings.IMAGE_RATE_LIMIT, key_func=get_user_or_ip)
def generate_image(request: Request, req: ImageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == req.session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    prompt_clean = req.prompt.strip()
    if prompt_clean.lower().startswith("generate:"):
        prompt_clean = prompt_clean[len("generate:"):].strip()

    if not prompt_clean:
        raise HTTPException(status_code=400, detail="Image generation prompt cannot be empty")

    # Save user message
    user_msg = ChatMessage(session_id=req.session_id, role="user", content=f"generate: {prompt_clean}", msg_type="text")
    db.add(user_msg)
    db.commit()

    # Generate image via dynamic models
    b64_img = hf_client.generate_image(prompt_clean, api_key=current_user.api_key)

    # Save assistant image message
    ai_msg = ChatMessage(session_id=req.session_id, role="assistant", content=b64_img, msg_type="image")
    db.add(ai_msg)
    db.commit()

    return {
        "status": "success",
        "image_b64": b64_img,
        "prompt": prompt_clean
    }
