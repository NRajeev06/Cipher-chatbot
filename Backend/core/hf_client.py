import base64
import io
import json
import re
import time
from datetime import datetime
import requests
from typing import Generator, List, Dict
from huggingface_hub import InferenceClient
from PIL import Image, ImageDraw, ImageFont
from core.config import settings

class HuggingFaceClient:
    def __init__(self):
        self.token = settings.HUGGINGFACE_TOKEN.strip().strip('"').strip("'") if settings.HUGGINGFACE_TOKEN else ""
        self.image_model = settings.HF_IMAGE_MODEL
        self.chat_model = getattr(settings, 'HF_CHAT_MODEL', 'Qwen/Qwen2.5-7B-Instruct')
        self._client = InferenceClient(token=self.token) if self.token else None

    def stream_chat(self, prompt: str, history: List[Dict[str, str]] = None, rag_context: str = "", api_key: str = None) -> Generator[str, None, None]:
        # Determine effective key: user custom key first, then system default token
        effective_key = api_key if api_key else (settings.GROQ_API_KEY or self.token)
        if effective_key:
            effective_key = effective_key.strip().strip('"').strip("'")
        
        # Build prompt with dynamic date and clean RAG context
        now = datetime.now()
        date_str = now.strftime("%B %d, %Y")
        day_str = now.strftime("%A")
        date_context = f"Today's date is {date_str}, a {day_str}."

        system_prompt = f"You are CIPHER, an intelligent, helpful, and versatile AI assistant. {date_context} Provide clear, accurate, and well-structured answers."
        if rag_context:
            system_prompt += f"\n\nDocument Context:\n\"\"\"\n{rag_context}\n\"\"\"\nUse the document context above to answer the user's questions accurately. If the document context does not contain relevant information, answer based on your general knowledge."

        if not effective_key:
            fallback_response = self._generate_fallback_response(prompt, rag_context)
            for char in fallback_response:
                yield char
                time.sleep(0.01)
            return

        messages = [{"role": "system", "content": system_prompt}]
        for msg in (history or []):
            clean_content = re.sub(r'\[CIPHER System.*?\].*?\n*', '', msg.get("content", "")).strip()
            messages.append({"role": msg.get("role", "user"), "content": clean_content})
        messages.append({"role": "user", "content": prompt})

        # 1. Groq Engine (gsk_...)
        if effective_key.startswith("gsk_") or (not effective_key.startswith("sk-") and not effective_key.startswith("AIzaSy") and not effective_key.startswith("hf_")):
            try:
                from groq import Groq, AuthenticationError, RateLimitError, NotFoundError, APIStatusError
                groq_client = Groq(api_key=effective_key)
                models_to_try = [settings.GROQ_CHAT_MODEL, "qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant"]
                stream = None
                last_err = None
                for m in models_to_try:
                    if not m:
                        continue
                    try:
                        stream = groq_client.chat.completions.create(
                            model=m,
                            messages=messages,
                            temperature=0.7,
                            max_tokens=2048,
                            stream=True
                        )
                        break
                    except AuthenticationError:
                        yield "⚠️ **[Groq API Error 401 Unauthorized]** Invalid Groq API Key. Please verify or update your key in Settings."
                        return
                    except RateLimitError as e:
                        yield f"⚠️ **[Groq API Error 429 Rate Limit]** {str(e)}"
                        return
                    except NotFoundError as e:
                        last_err = f"Model {m} not found on account."
                        continue
                    except Exception as e:
                        last_err = str(e)
                        continue

                if not stream:
                    yield f"⚠️ **[Groq API Error]** Could not connect to Groq models ({', '.join(models_to_try[:3])}). Last error: {last_err}"
                    return

                for chunk in stream:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        yield token
                return
            except Exception as e:
                yield f"⚠️ **[Groq Error]** {str(e)}"
                return

        # 2. OpenAI Routing
        elif effective_key.startswith("sk-"):
            try:
                headers = {
                    "Authorization": f"Bearer {effective_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7
                }
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=30
                )
                
                if response.status_code != 200:
                    try:
                        err_msg = response.json().get("error", {}).get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    yield f"⚠️ **[OpenAI API Error {response.status_code}]** {err_msg}"
                    return
                
                for line in response.iter_lines():
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
                return
            except Exception as e:
                yield f"⚠️ **[OpenAI Connection Error]** {str(e)}"
                return

        # 3. Gemini Routing
        elif effective_key.startswith("AIzaSy"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse&key={effective_key}"
                headers = {"Content-Type": "application/json"}
                
                contents = []
                for msg in (history or []):
                    clean_content = re.sub(r'\[CIPHER System.*?\].*?\n*', '', msg.get("content", "")).strip()
                    role = "user" if msg.get("role") == "user" else "model"
                    contents.append({
                        "role": role,
                        "parts": [{"text": clean_content}]
                    })
                contents.append({
                    "role": "user",
                    "parts": [{"text": prompt}]
                })
                
                data = {
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7
                    }
                }
                response = requests.post(url, headers=headers, json=data, stream=True, timeout=30)
                if response.status_code != 200:
                    try:
                        err_msg = response.json().get("error", {}).get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    yield f"⚠️ **[Gemini API Error {response.status_code}]** {err_msg}"
                    return
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8").strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            try:
                                chunk = json.loads(data_str)
                                token = chunk["candidates"][0]["content"]["parts"][0].get("text", "")
                                if token:
                                    yield token
                            except Exception:
                                continue
                return
            except Exception as e:
                yield f"⚠️ **[Gemini Connection Error]** {str(e)}"
                return
        
        # 4. HuggingFace Routing
        else:
            models_to_try = []
            if self.chat_model:
                models_to_try.append(self.chat_model)
            
            backups = [
                "meta-llama/Llama-3.1-8B-Instruct",
                "Qwen/Qwen2.5-7B-Instruct",
                "mistralai/Mistral-7B-Instruct-v0.3"
            ]
            for model in backups:
                if model not in models_to_try:
                    models_to_try.append(model)

            client = InferenceClient(token=effective_key)
            last_err = None
            
            for model in models_to_try:
                try:
                    stream = client.chat_completion(
                        messages=messages,
                        model=model,
                        max_tokens=1024,
                        stream=True,
                        temperature=0.7
                    )
                    for chunk in stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            token = chunk.choices[0].delta.content or ""
                            if token:
                                yield token
                    return
                except Exception as e:
                    last_err = str(e)
                    continue
            
            yield f"⚠️ **[Hugging Face API Error]** Failed to connect to models ({', '.join(models_to_try[:2])}). Details: {last_err}"

    def generate_image(self, prompt: str, api_key: str = None) -> str:
        effective_key = api_key if api_key else self.token
        error_msg = None
        if effective_key:
            effective_key = effective_key.strip().strip('"').strip("'")
            # 1. OpenAI Image Generation
            if effective_key.startswith("sk-"):
                try:
                    headers = {
                        "Authorization": f"Bearer {effective_key}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "response_format": "b64_json"
                    }
                    response = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=data, timeout=60)
                    if response.status_code == 200:
                        return response.json()["data"][0]["b64_json"]
                    else:
                        error_msg = f"OpenAI error {response.status_code}: {response.text[:50]}"
                        print(f"OpenAI Image Gen error: {response.text}")
                except Exception as e:
                    error_msg = f"OpenAI exception: {str(e)[:50]}"
                    print(f"OpenAI Image Gen Exception: {e}")
            
            # 2. HuggingFace Image Generation
            else:
                try:
                    client = InferenceClient(token=effective_key)
                    image = client.text_to_image(prompt, model=self.image_model)
                    buffered = io.BytesIO()
                    image.save(buffered, format="PNG")
                    return base64.b64encode(buffered.getvalue()).decode("utf-8")
                except Exception as e:
                    error_msg = f"HF error: {str(e)[:50]}"
                    if "402" in str(e):
                        error_msg = "HF error: 402 Credits Depleted"
                    elif "410" in str(e) or "deprecated" in str(e).lower():
                        error_msg = "HF error: SDXL Deprecated on Serverless"
                    print(f"HF Image Generation Error: {e}")

        # Fallback modern canvas generation if HF key not available
        return self._generate_fallback_image(prompt, error_msg=error_msg)

    def _generate_fallback_response(self, prompt: str, rag_context: str) -> str:
        res = "Hello! I am CIPHER, your AI assistant."
        if rag_context:
            res += f"\n\n**Active Document Context:**\n{rag_context[:350]}...\n\n"
        res += f"\n\nNo API key is configured. To connect directly to dynamic engines (Groq, OpenAI, Google Gemini, or Hugging Face), please enter your API key in **Settings**."
        return res

    def _generate_fallback_image(self, prompt: str, error_msg: str = None) -> str:
        img = Image.new('RGB', (512, 512), color=(18, 21, 31))
        d = ImageDraw.Draw(img)
        
        # Subtle modern border
        d.rectangle([10, 10, 501, 501], outline=(99, 102, 241), width=2)
        d.rectangle([20, 20, 491, 491], outline=(40, 45, 65), width=1)
        
        # Text overlay
        d.text((40, 190), "CIPHER IMAGE SYNTHESIS", fill=(240, 243, 250))
        d.text((40, 230), f"Prompt: {prompt[:35]}...", fill=(148, 163, 184))
        d.text((40, 270), "Status: Preview Canvas", fill=(99, 102, 241))
        
        if error_msg:
            d.text((40, 310), f"Notice: {error_msg}", fill=(239, 68, 68))
            
        d.text((40, 440), "Configure an API key in Settings for DALL-E 3 / SDXL", fill=(148, 163, 184))

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

hf_client = HuggingFaceClient()
