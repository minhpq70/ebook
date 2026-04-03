"""
FastAPI Application Entry Point
Ebook Platform — Private RAG Backend (POC)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers import books, rag

app = FastAPI(
    title="Ebook Platform API",
    description="Nền tảng xuất bản điện tử với Private RAG — POC",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — cho phép Next.js frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(books.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "ebook-platform-api",
        "version": "0.1.0",
        "env": settings.app_env,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Ebook Platform API",
        "docs": "/docs",
        "health": "/health",
    }
