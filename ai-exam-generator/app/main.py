import os
import shutil
import tempfile
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fastapi.staticfiles import StaticFiles

from app.config import PROVIDER_CONFIGS, DEFAULT_PROVIDER, GROQ_DEPRECATED_MODELS, get_api_key
from app.services.parser import extract_content_from_file
from app.services.generator import (
    analyze_document_content,
    generate_exam_questions,
    regenerate_single_question
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

app = FastAPI(title="AI Exam Generator", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


class GenerateRequest(BaseModel):
    passage: str
    question_style: str
    difficulty: str = "고2 기본"
    question_count: int = 3
    subject: Optional[str] = "korean"
    provider: str = "groq"
    model: Optional[str] = None
    api_key: Optional[str] = None

class RegenerateRequest(BaseModel):
    passage: str
    question_style: str
    difficulty: str
    existing_questions: List[dict]
    target_number: int
    subject: Optional[str] = "korean"
    provider: str = "groq"
    model: Optional[str] = None
    api_key: Optional[str] = None

class ApiKeyCheckRequest(BaseModel):
    provider: str = "groq"
    api_key: Optional[str] = None

class LiveModelRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None


@app.get("/api/providers")
async def get_providers():
    return {
        "providers": PROVIDER_CONFIGS,
        "default_provider": DEFAULT_PROVIDER
    }


@app.post("/api/fetch-live-models")
async def fetch_live_models(req: LiveModelRequest):
    provider = req.provider.lower()
    conf = PROVIDER_CONFIGS.get(provider, {})
    api_key = get_api_key(provider, req.api_key)
    
    if not api_key:
        return {"success": False, "models": conf.get("models", [])}

    # If provider is OpenAI-compatible (Cerebras, Groq, OpenAI, Solar, DeepSeek)
    if provider in ["cerebras", "groq", "openai", "solar", "deepseek"] and OpenAI:
        try:
            base_url = conf.get("base_url")
            client_args = {"api_key": api_key}
            if base_url:
                client_args["base_url"] = base_url
            client = OpenAI(**client_args)
            models_res = client.models.list()
            
            # Filter chat/completion models
            live_models = []
            for m in models_res.data:
                mid = m.id
                if mid in GROQ_DEPRECATED_MODELS:
                    continue
                # exclude audio/embedding/guard models
                if "whisper" not in mid and "embed" not in mid and "tts" not in mid and "guard" not in mid:
                    live_models.append({"id": mid, "name": mid})
            
            if live_models:
                return {"success": True, "models": live_models}
        except Exception:
            pass

    return {"success": True, "models": conf.get("models", [])}


@app.post("/api/check-api-key")
async def check_api_key(req: ApiKeyCheckRequest):
    provider = req.provider or DEFAULT_PROVIDER
    key = get_api_key(provider, req.api_key)
    conf = PROVIDER_CONFIGS.get(provider, {})
    return {
        "provider": provider,
        "has_key": bool(key),
        "masked_key": f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "",
        "default_model": conf.get("default_model", "")
    }


@app.post("/api/upload-and-analyze")
async def upload_and_analyze(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    page_range: Optional[str] = Form(None),
    provider: str = Form("groq"),
    model: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None)
):
    try:
        content_text = ""
        images = []
        filename = "직접_입력_텍스트"
        file_format = "txt"
        page_info = ""

        if file:
            filename = file.filename
            file_format = os.path.splitext(filename)[1].lower().replace(".", "")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
                
            try:
                extracted = extract_content_from_file(tmp_path, filename, page_range=page_range)
                content_text = extracted["text"]
                images = extracted.get("images", [])
                page_info = extracted.get("page_info", "")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        elif raw_text:
            content_text = raw_text
            page_info = "직접 입력한 텍스트"
        else:
            raise HTTPException(status_code=400, detail="업로드된 파일이나 텍스트가 없습니다.")

        if not content_text.strip() and not images:
            raise HTTPException(status_code=400, detail="선택한 페이지 범위 또는 파일에서 텍스트 내용을 추출하지 못했습니다.")

        # AI 문서 분석 (요약, 본문 정돈, 문제양식 식별)
        analysis_result = analyze_document_content(
            text_content=content_text,
            provider=provider,
            model=model,
            custom_api_key=api_key
        )

        return {
            "success": True,
            "filename": filename,
            "format": file_format,
            "page_info": page_info,
            "raw_length": len(content_text),
            "summary": analysis_result.get("summary", ""),
            "passage": analysis_result.get("passage", content_text),
            "detected_style": analysis_result.get("detected_style", {
                "has_question_style": False,
                "template_name": "수능 표준 5지선다형",
                "description": "기본 5지선다 객관식 양식"
            })
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/generate-questions")
async def generate_questions(req: GenerateRequest):
    try:
        questions = generate_exam_questions(
            passage=req.passage,
            question_style=req.question_style,
            difficulty=req.difficulty,
            question_count=req.question_count,
            subject=req.subject or "korean",
            provider=req.provider,
            model=req.model,
            custom_api_key=req.api_key
        )
        return {
            "success": True,
            "difficulty": req.difficulty,
            "subject": req.subject or "korean",
            "questions": questions
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/regenerate-question")
async def regenerate_question(req: RegenerateRequest):
    try:
        new_question = regenerate_single_question(
            passage=req.passage,
            question_style=req.question_style,
            difficulty=req.difficulty,
            existing_questions=req.existing_questions,
            target_number=req.target_number,
            subject=req.subject or "korean",
            provider=req.provider,
            model=req.model,
            custom_api_key=req.api_key
        )
        return {
            "success": True,
            "target_number": req.target_number,
            "subject": req.subject or "korean",
            "question": new_question
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/", response_class=HTMLResponse)
async def read_root():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    return "<h1>AI Exam Generator is running</h1>"
