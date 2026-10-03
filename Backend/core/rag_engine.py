import io
import fitz  # PyMuPDF
import docx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

class RAGEngine:
    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> str:
        ext = filename.lower().split('.')[-1]
        text = ""
        
        if ext == "pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n"
        elif ext in ["docx", "doc"]:
            doc_file = io.BytesIO(file_bytes)
            document = docx.Document(doc_file)
            for p in document.paragraphs:
                text += p.text + "\n"
        elif ext == "txt":
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1")
        else:
            raise ValueError(f"Unsupported file format: {ext}")
            
        return text.strip()

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += (chunk_size - overlap)
            
        return chunks

    @staticmethod
    def get_relevant_context_from_chunks(query: str, chunks: List[str], top_k: int = 3) -> str:
        if not chunks:
            return ""
            
        if len(chunks) <= top_k:
            return "\n---\n".join(chunks)
            
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(chunks + [query])
            
            chunk_vectors = tfidf_matrix[:-1]
            query_vector = tfidf_matrix[-1]
            
            similarities = cosine_similarity(query_vector, chunk_vectors).flatten()
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            relevant_chunks = [chunks[i] for i in top_indices if similarities[i] > 0.01]
            if not relevant_chunks:
                # If no strong match, take the top 2 chunks
                relevant_chunks = [chunks[i] for i in top_indices[:2]]
                
            return "\n---\n".join(relevant_chunks)
        except Exception as e:
            # Fallback to simple slice if TF-IDF fails (e.g., all stop words)
            return "\n---\n".join(chunks[:top_k])

    @staticmethod
    def get_relevant_context(query: str, raw_text: str, top_k: int = 3) -> str:
        if not raw_text.strip():
            return ""
        chunks = RAGEngine.chunk_text(raw_text)
        return RAGEngine.get_relevant_context_from_chunks(query, chunks, top_k=top_k)
