import io
import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import require_user
from app.models.user import User
from app.models.document import Document
from app.services import rag
from app.services.deepseek import get_ai_reply_with_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI"])


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "pdf"):
        raise HTTPException(status_code=400, detail="仅支持 TXT 和 PDF 文件")

    content = await file.read()


    if ext == "pdf":
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {e}")
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"文件编码不支持: {e}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空或无法提取文本")

    doc_id = uuid.uuid4()
    chunk_count = await rag.store_document(current_user.id, file.filename, text, doc_id)

    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        chunk_count=chunk_count,
    )
    db.add(doc)
    await db.commit()

    return {
        "document_id": str(doc_id),
        "filename": file.filename,
        "chunk_count": chunk_count,
    }


@router.get("/documents")
async def list_documents(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "document_id": str(d.id),
            "filename": d.filename,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    await rag.delete_document(document_id)
    await db.delete(doc)
    await db.commit()

    return {"status": "deleted"}


@router.post("/rag-query")
async def rag_query(
    req: RAGQueryRequest,
    current_user: User = Depends(require_user),
):
    chunks = await rag.search_similar(req.query, current_user.id, req.top_k)

    sources = [
        {
            "filename": c["metadata"].get("filename", "未知"),
            "snippet": c["content"][:200],
            "distance": round(c["distance"], 4),
        }
        for c in chunks
    ]

    async def event_stream():
        # NDJSON：一行一个事件。json.dumps 会把正文里的换行转义掉，
        # 所以每条事件天然占一行，前端按行切分即可。
        yield json.dumps({"type": "sources", "sources": sources}) + "\n"

        if not chunks:
            yield json.dumps({"type": "delta", "text": "你的文档知识库中暂无相关内容"}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return

        context = "\n\n".join(
            f"[来源{i+1}: {c['metadata'].get('filename', '未知')}]\n{c['content']}"
            for i, c in enumerate(chunks)
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个文档问答助手。请基于以下文档内容回答用户的问题。\n"
                    "如果文档中有相关信息，请引用来源。\n"
                    "如果文档中没有相关信息，请如实告知。\n\n"
                    f"文档内容:\n{context}"
                ),
            },
            {"role": "user", "content": req.query},
        ]

        async for piece in get_ai_reply_with_tools(messages):
            yield json.dumps({"type": "delta", "text": piece}) + "\n"

        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
