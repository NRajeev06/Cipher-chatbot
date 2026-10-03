# CIPHER ⬡ Cyberpunk AI Neural Interface

CIPHER is an AI chatbot featuring a **cyberpunk-themed React (Vite) frontend** and a **FastAPI backend**. It supports token-by-token streaming responses powered by Hugging Face's `Qwen2.5-7B-Instruct`, document-based Retrieval-Augmented Generation (RAG) with TF-IDF similarity search over PDF, DOCX, and TXT files, and text-to-image synthesis using `Stable Diffusion XL`.

---

## 🚀 Key Features

- **Cyberpunk UI Aesthetic**: High-tech terminal interface (`#00ff41` neon green on pitch black), CRT scanline overlays, glowing cards, and monospace typography.
- **JWT Authentication**: User signup and login with bcrypt password hashing and JWT stored in `localStorage`.
- **Session Management**: Create, switch, and delete chat sessions with auto-titling.
- **Token-by-Token Streaming**: Live response streaming standard via FastAPI `StreamingResponse` and Web `ReadableStream`.
- **RAG Document Injection**: Upload PDF, DOCX, or TXT files. Context is extracted, chunked, and queried using TF-IDF cosine similarity to answer document-specific questions.
- **Image Generation Mode**: Toggle Image Mode or prefix any prompt with `generate:` to create AI images via Stable Diffusion XL.
- **PostgreSQL Database**: Persistent storage for users, sessions, chat history, and document metadata with automatic SQLite fallback for rapid local testing.

---

## 📁 Directory Structure

```
Cipher/
├── Backend/
│   ├── auth/            # JWT authentication & password hashing
│   ├── core/            # Config, Hugging Face streaming client, & RAG engine
│   ├── models/          # SQLAlchemy database engine & ORM entities
│   ├── routes/          # API endpoints (auth, chat, RAG, image generation)
│   ├── .env             # Environment secrets
│   ├── main.py          # FastAPI application entry point
│   └── requirements.txt # Python dependencies
├── Frontend/
│   └── Frontend/        # React + Vite application codebase
├── .gitignore           # Git ignore rules
└── README.md            # Application guide
```

---

## 🛠️ PostgreSQL Setup Guide

### 1. Install PostgreSQL
- **Windows / macOS / Linux**: Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/).

### 2. Create the Database
Open your terminal or `psql` shell:

```sql
-- Access psql console
psql -U postgres

-- Create the database
CREATE DATABASE cipher_db;
```

### 3. Connection String
In your `Backend/.env` file, set `DATABASE_URL`:
```env
DATABASE_URL=postgresql://postgres:your_postgres_password@localhost:5432/cipher_db
```
*(Note: If PostgreSQL is not installed or running, CIPHER will automatically fall back to SQLite `sqlite:///./cipher.db` for instant local testing).*

---

## ⚙️ Backend Setup & Running

### 1. Create Virtual Environment
Navigate to `Backend/`:
```bash
cd Backend
python -m venv venv
```

Activate the environment:
- **Windows (PowerShell)**: `.\venv\Scripts\Activate.ps1`
- **Linux / macOS**: `source venv/bin/activate`

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create or edit `Backend/.env`:
```env
HUGGINGFACE_TOKEN=your_hf_api_token_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cipher_db
JWT_SECRET=super_secret_cipher_key_2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

HF_CHAT_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
```

### 4. Launch FastAPI Server
```bash
uvicorn main:app --reload --port 8000
```
Backend API docs will be available at: `http://localhost:8000/docs`

---

## 💻 Frontend Setup & Running

### 1. Navigate to Frontend Directory
```bash
cd Frontend/Frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Run Development Server
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🎮 Usage Guide

1. **Sign Up / Log In**: Register a new account or log in. JWT tokens are automatically stored and attached to all requests.
2. **Chat & Stream**: Type a question in the input prompt (`prompt >`). Responses will stream token-by-token.
3. **Upload RAG Document**: Click `[ UPLOAD FILE ]` in the left sidebar to attach a `.pdf`, `.docx`, or `.txt` file. CIPHER will retrieve relevant context for your questions.
4. **Generate AI Images**: Enable `IMAGE MODE` toggle or start your prompt with `generate:` (e.g. `generate: a futuristic neon matrix hacker station`).
