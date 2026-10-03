from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import time
import re
import json
import logging
import requests

from models.database import get_db, SessionLocal
from models.entities import User, ChatSession, ChatMessage, Document, DocumentChunk
from auth.jwt import get_current_user
from groq import Groq, AuthenticationError, RateLimitError, NotFoundError, APIConnectionError, APIStatusError
from huggingface_hub import InferenceClient
from core.rag_engine import RAGEngine
from core.search_service import search_web
from core.config import settings
from core.limiter import limiter, get_user_or_ip

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger("cipher.chat")

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the live web for real-time information, breaking news, live data, or current facts not in your training data.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web"
                }
            },
            "required": ["query"]
        }
    }
}

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str

class MessageRequest(BaseModel):
    message: str
    session_id: str

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    type: str
    created_at: str

@router.get("/sessions")
def get_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]

@router.post("/sessions")
@router.post("/session")
def create_session(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_session = ChatSession(user_id=current_user.id, title="New Session")
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"id": new_session.id, "session_id": new_session.id, "title": new_session.title, "created_at": new_session.created_at.isoformat()}

@router.delete("/sessions/{session_id}")
@router.delete("/session/{session_id}")
def delete_session(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted"}

@router.get("/sessions/{session_id}/messages")
@router.get("/history/{session_id}")
def get_session_history(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    cleaned_messages = []
    for m in messages:
        content = m.content
        if m.role == "assistant" and content:
            content = re.sub(r'\[CIPHER System.*?\].*?\n*', '', content).strip()
        cleaned_messages.append({"id": m.id, "role": m.role, "content": content, "type": m.msg_type, "created_at": m.created_at.isoformat()})
    return cleaned_messages

@router.post("/stream")
@limiter.limit(settings.CHAT_RATE_LIMIT, key_func=get_user_or_ip)
def stream_chat(request: Request, req: MessageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == req.session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update title if it's default
    if session.title == "New Session" or session.title == "New Chat Session":
        session.title = req.message[:30] + ("..." if len(req.message) > 30 else "")
        db.commit()

    # Save user message to database
    user_msg = ChatMessage(session_id=req.session_id, role="user", content=req.message, msg_type="text")
    db.add(user_msg)
    db.commit()

    # Check for RAG context from persisted database chunks
    # 1. Check session-bound active document
    doc = db.query(Document).filter(
        Document.session_id == req.session_id,
        Document.user_id == current_user.id,
        Document.is_active == True
    ).order_by(Document.created_at.desc()).first()

    # 2. Fallback to user's active document if not found on session
    if not doc:
        doc = db.query(Document).filter(
            Document.user_id == current_user.id,
            Document.is_active == True
        ).order_by(Document.created_at.desc()).first()

    rag_context = ""
    if doc:
        # Read pre-split chunks directly from the database
        chunks = [c.content for c in doc.chunks]
        if chunks:
            rag_context = RAGEngine.get_relevant_context_from_chunks(req.message, chunks)
        elif doc.raw_text:
            rag_context = RAGEngine.get_relevant_context(req.message, doc.raw_text)

    # Get conversation history with sanitized contents
    past_messages = db.query(ChatMessage).filter(ChatMessage.session_id == req.session_id).order_by(ChatMessage.created_at.asc()).all()
    history = []
    for m in past_messages[:-1]: # Exclude current msg
        content = m.content
        if m.role == "assistant" and content:
            content = re.sub(r'\[CIPHER System.*?\].*?\n*', '', content).strip()
        history.append({"role": m.role, "content": content})

    # Dynamically inject current date and day of the week at request time
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    day_str = now.strftime("%A")
    date_context = f"Today's date is {date_str}, a {day_str}."

    # Check if Tavily web search capability is configured
    tavily_key = (settings.TAVILY_API_KEY or "").strip().strip('"').strip("'")
    has_search = bool(tavily_key)

    # Assemble conversation prompt incorporating date, search instructions, and RAG context
    system_prompt = (
        f"You are CIPHER, an intelligent, helpful, and versatile AI assistant. "
        f"{date_context}"
    )

    if has_search:
        system_prompt += (
            " You have access to a live web search tool ('web_search'). "
            "Use this tool whenever the user asks about current events, real-time data, recent news, "
            "or facts that may have changed or occurred recently. "
            "Do NOT call web search for general knowledge, coding, or math questions that do not require real-time information."
        )
    else:
        system_prompt += (
            " Real-time web search is currently disabled (no search API key is configured). "
            "If the user asks about real-time events or current information that you cannot know due to your training cutoff, "
            "naturally and politely inform them that you do not have internet/search access enabled right now, "
            "rather than guessing or making up facts."
        )

    if rag_context:
        system_prompt += (
            f"\n\nDocument Context:\n\"\"\"\n{rag_context}\n\"\"\"\n"
            "Use the document context above to answer the user's questions accurately. "
            "If the document context does not contain relevant information, answer based on your general knowledge."
        )

    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": req.message})

    # Engine routing & API key resolution:
    # Prioritize user-configured custom key from Settings, then system GROQ_API_KEY
    user_key = (current_user.api_key or "").strip().strip('"').strip("'")
    system_key = (settings.GROQ_API_KEY or "").strip().strip('"').strip("'")
    effective_api_key = user_key if user_key else system_key

    def generator():
        if not effective_api_key:
            fallback = (
                "Hello! I am CIPHER, your AI assistant.\n\n"
                "No inference API key is configured. To connect directly to dynamic engines "
                "(Groq, OpenAI, Google Gemini, or Hugging Face), please enter your API key in **Settings**."
            )
            yield fallback
            with SessionLocal_context() as save_db:
                ai_msg = ChatMessage(session_id=req.session_id, role="assistant", content=fallback, msg_type="text")
                save_db.add(ai_msg)
                save_db.commit()
            return

        def stream_provider():
            # 1. OpenAI Engine (sk-...)
            if effective_api_key.startswith("sk-"):
                headers = {
                    "Authorization": f"Bearer {effective_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.7,
                    "stream": True
                }
                try:
                    resp = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        stream=True,
                        timeout=30
                    )
                    if resp.status_code != 200:
                        try:
                            err_data = resp.json().get("error", {})
                            err_detail = err_data.get("message", resp.text)
                        except Exception:
                            err_detail = resp.text
                        yield f"⚠️ **[OpenAI API Error {resp.status_code}]** {err_detail}"
                        return

                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8").strip()
                            if line_str.startswith("data: "):
                                data_str = line_str[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    token = chunk["choices"][0]["delta"].get("content", "")
                                    if token:
                                        yield token
                                except Exception:
                                    continue
                except Exception as e:
                    yield f"⚠️ **[OpenAI Connection Error]** {str(e)}"
                return

            # 2. Google Gemini Engine (AIzaSy...)
            elif effective_api_key.startswith("AIzaSy"):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse&key={effective_api_key}"
                headers = {"Content-Type": "application/json"}
                contents = []
                for msg in history:
                    role = "user" if msg.get("role") == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
                contents.append({"role": "user", "parts": [{"text": req.message}]})

                payload = {
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": contents,
                    "generationConfig": {"temperature": 0.7}
                }
                try:
                    resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=30)
                    if resp.status_code != 200:
                        try:
                            err_data = resp.json().get("error", {})
                            err_detail = err_data.get("message", resp.text)
                        except Exception:
                            err_detail = resp.text
                        yield f"⚠️ **[Google Gemini API Error {resp.status_code}]** {err_detail}"
                        return

                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8").strip()
                            if line_str.startswith("data: "):
                                data_str = line_str[6:]
                                try:
                                    chunk = json.loads(data_str)
                                    candidates = chunk.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        for p in parts:
                                            token = p.get("text", "")
                                            if token:
                                                yield token
                                except Exception:
                                    continue
                except Exception as e:
                    yield f"⚠️ **[Google Gemini Connection Error]** {str(e)}"
                return

            # 3. Hugging Face Engine (hf_...)
            elif effective_api_key.startswith("hf_"):
                try:
                    client = InferenceClient(token=effective_api_key)
                    models = [
                        "meta-llama/Llama-3.1-8B-Instruct",
                        "Qwen/Qwen2.5-7B-Instruct",
                        "mistralai/Mistral-7B-Instruct-v0.3"
                    ]
                    success = False
                    last_err = None
                    for model in models:
                        try:
                            stream = client.chat_completion(
                                messages=messages,
                                model=model,
                                max_tokens=2048,
                                stream=True,
                                temperature=0.7
                            )
                            for chunk in stream:
                                if chunk.choices and len(chunk.choices) > 0:
                                    token = chunk.choices[0].delta.content or ""
                                    if token:
                                        success = True
                                        yield token
                            return
                        except Exception as e:
                            last_err = str(e)
                            continue
                    if not success:
                        yield f"⚠️ **[Hugging Face API Error]** All models failed. Last error: {last_err}"
                except Exception as e:
                    yield f"⚠️ **[Hugging Face Client Error]** {str(e)}"
                return

            # 4. Groq Engine (gsk_... or Default System Key)
            else:
                try:
                    groq_client = Groq(api_key=effective_api_key)
                except Exception as e:
                    yield f"⚠️ **[Groq Client Initialization Error]** {str(e)}"
                    return

                # Build model candidate priority list
                models_to_try = []
                if settings.GROQ_CHAT_MODEL:
                    models_to_try.append(settings.GROQ_CHAT_MODEL)
                for fallback_m in [
                    "qwen/qwen3.8-27b",
                    "llama-3.3-70b-versatile",
                    "openai/gpt-oss-120b",
                    "llama-3.1-8b-instant",
                    "llama3-70b-8192"
                ]:
                    if fallback_m not in models_to_try:
                        models_to_try.append(fallback_m)

                stream = None
                last_error_detail = None

                for model_id in models_to_try:
                    try:
                        # Case A: Tavily Search is enabled -> Tool Calling Flow
                        if has_search:
                            first_resp = groq_client.chat.completions.create(
                                model=model_id,
                                messages=messages,
                                tools=[WEB_SEARCH_TOOL],
                                tool_choice="auto"
                            )
                            first_msg = first_resp.choices[0].message

                            # Check if the model triggered web search
                            if first_msg.tool_calls:
                                logger.info(f"🛠️ [GROQ TOOL CALL] Model triggered {len(first_msg.tool_calls)} tool call(s)")
                                yield "🔍 *Searching the web for current information...*\n\n"

                                tool_messages = list(messages)
                                tool_messages.append({
                                    "role": "assistant",
                                    "content": first_msg.content or "",
                                    "tool_calls": [
                                        {
                                            "id": tc.id,
                                            "type": "function",
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments
                                            }
                                        } for tc in first_msg.tool_calls
                                    ]
                                })

                                all_sources = []
                                for tc in first_msg.tool_calls:
                                    try:
                                        args = json.loads(tc.function.arguments)
                                        query = args.get("query", req.message)
                                    except Exception:
                                        query = req.message

                                    logger.info(f"🔎 [GROQ TOOL CALL] Function: '{tc.function.name}' | Extracted Query: '{query}'")
                                    search_data = search_web(query)
                                    if search_data.get("sources"):
                                        all_sources.extend(search_data["sources"])

                                    tool_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc.id,
                                        "name": tc.function.name,
                                        "content": json.dumps(search_data)
                                    })

                                # Stream the synthesized response with search results injected
                                stream = groq_client.chat.completions.create(
                                    model=model_id,
                                    messages=tool_messages,
                                    temperature=0.7,
                                    max_tokens=2048,
                                    stream=True
                                )
                                for chunk in stream:
                                    delta = chunk.choices[0].delta
                                    token = delta.content or ""
                                    if token:
                                        yield token

                                # Append clickable Sources section
                                if all_sources:
                                    sources_md = "\n\n---\n**Sources:**\n"
                                    seen_urls = set()
                                    for s in all_sources:
                                        url = s.get("url")
                                        title = s.get("title") or url
                                        if url and url not in seen_urls:
                                            seen_urls.add(url)
                                            sources_md += f"- [{title}]({url})\n"
                                    yield sources_md
                                return
                            else:
                                # Model decided it does NOT need web search (e.g. general question, coding)
                                content = first_msg.content or ""
                                words = re.split(r'(\s+)', content)
                                for w in words:
                                    if w:
                                        yield w
                                        time.sleep(0.005)
                                return

                        # Case B: Search is not enabled -> Direct streaming
                        else:
                            stream = groq_client.chat.completions.create(
                                model=model_id,
                                messages=messages,
                                temperature=0.7,
                                max_tokens=2048,
                                stream=True
                            )
                            for chunk in stream:
                                delta = chunk.choices[0].delta
                                token = delta.content or ""
                                if token:
                                    yield token
                            return

                    except AuthenticationError:
                        yield "⚠️ **[Groq API Error: 401 Unauthorized]** Invalid Groq API Key. Please verify or update your key in Settings."
                        return
                    except RateLimitError as e:
                        yield f"⚠️ **[Groq API Error: 429 Rate Limit Exceeded]** {str(e)}"
                        return
                    except NotFoundError as e:
                        last_error_detail = f"Model '{model_id}' not found on account ({e.message if hasattr(e, 'message') else str(e)})"
                        continue
                    except APIStatusError as e:
                        last_error_detail = f"Status {e.status_code}: {e.message if hasattr(e, 'message') else str(e)}"
                        continue
                    except Exception as e:
                        last_error_detail = str(e)
                        continue

                if not stream:
                    yield f"⚠️ **[Groq API Error]** Could not connect to Groq models ({', '.join(models_to_try[:3])}). Last error: {last_error_detail}"
                    return

        full_reply = ""
        for chunk_token in stream_provider():
            full_reply += chunk_token
            yield chunk_token

        # Save complete assistant response once finished streaming
        with SessionLocal_context() as save_db:
            cleaned_reply = re.sub(r'\[CIPHER System.*?\].*?\n*', '', full_reply).strip()
            ai_msg = ChatMessage(session_id=req.session_id, role="assistant", content=cleaned_reply or full_reply, msg_type="text")
            save_db.add(ai_msg)
            save_db.commit()

    return StreamingResponse(generator(), media_type="text/plain")

def SessionLocal_context():
    from models.database import SessionLocal
    return SessionLocal()

