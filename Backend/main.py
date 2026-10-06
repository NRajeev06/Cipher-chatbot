from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from models.database import engine, Base, init_db
from routes import auth, chat, rag, image
from core.limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cipher.backend")

# Create database tables automatically on startup
try:
    init_db()
except Exception as e:
    logger.error(f"Error creating database tables: {e}")

# Validate and log API configuration status on boot
tavily_key = (settings.TAVILY_API_KEY or "").strip().strip('"').strip("'")
if tavily_key:
    masked_tavily = f"{tavily_key[:4]}...{tavily_key[-4:]}" if len(tavily_key) > 8 else "***"
    logger.info(f"🌐 [CIPHER STARTUP] Tavily Real-time Web Search: ACTIVE (Key: {masked_tavily})")
else:
    logger.warning("⚠️ [CIPHER STARTUP] Tavily Real-time Web Search: DISABLED (TAVILY_API_KEY not found in .env)")

if settings.GROQ_API_KEY:
    masked_groq = f"{settings.GROQ_API_KEY[:6]}...{settings.GROQ_API_KEY[-4:]}" if len(settings.GROQ_API_KEY) > 10 else "***"
    logger.info(f"⚡ [CIPHER STARTUP] Groq Engine: ACTIVE (Model: {settings.GROQ_CHAT_MODEL}, Key: {masked_groq})")
else:
    logger.warning("⚠️ [CIPHER STARTUP] Groq Engine: No system GROQ_API_KEY configured.")

app = FastAPI(
    title="CIPHER AI API",
    description="Backend API for CIPHER Neural Interface with HuggingFace streaming, RAG, and SDXL Image Synthesis",
    version="2.0.0"
)

# Register slowapi rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS configuration allowing React frontend (local dev and Vercel production)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://cipher-chatbot.vercel.app",
    "*"
]
frontend_url = getattr(settings, "FRONTEND_URL", "").strip().rstrip("/")
if frontend_url and frontend_url not in origins:
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(rag.router)
app.include_router(image.router)

@app.get("/")
def root():
    return {
        "system": "CIPHER NEURAL BACKEND",
        "status": "ONLINE",
        "version": "2.0.0",
        "endpoints": {
            "auth": "/api/auth",
            "chat": "/api/chat",
            "rag": "/api/rag",
            "image": "/api/chat/image"
        }
    }
