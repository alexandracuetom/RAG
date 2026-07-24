from fastapi import FastAPI
import inngest 
import inngest.fast_api
from inngest.experimental import ai
from dotenv import load_dotenv
import uuid
import os 
import datetime
import logging

from groq import Groq

from qdrant_storage.data_loader import load_and_chunk_pdf, embed_texts
from qdrant_storage.vector_db import QdrantStorage

from custom_types import RAGQueryResult, RAGChunk, RAGSearchResult, RAGUpsertResult


load_dotenv()

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logging.getLogger("uvicorn"),
    is_production=False,
    serializer=inngest.PydanticSerializer()
)

@inngest_client.create_function(
    fn_id="RAG: Ingest PDF",
    trigger=inngest.TriggerEvent(event="rag/ingest_pdf")
)
async def rag_ingest_pdf(ctx: inngest.Context):
    def _load(ctx: inngest.Context) -> RAGChunk:
        pdf_path = ctx.event.data["pdf_path"]
        source_id = ctx.event.data.get("source_id", pdf_path)
        chunks = load_and_chunk_pdf(pdf_path)
        return RAGChunk(chunks = chunks, source_id=source_id)
    

    def _upsert(chunks_and_src: RAGChunk) -> RAGUpsertResult:
        chunks = chunks_and_src.chunks
        source_id = chunks_and_src.source_id
        vecs = embed_texts(chunks)
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}"))
                for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} 
                    for i in range(len(chunks))]
        
        QdrantStorage().upsert(ids, vecs, payloads)
        return RAGUpsertResult(ingested=len(chunks))

    chunks_and_src = await ctx.step.run("load-and-chunk", lambda:_load(ctx), output_type=RAGChunk)
    ingested = await ctx.step.run("embed-and-upsert", lambda:_upsert(chunks_and_src), output_type=RAGUpsertResult)
    return ingested.model_dump() 


@inngest_client.create_function(
    fn_id="RAG: Query PDF",
    trigger=inngest.TriggerEvent(event="rag/query_pdf_ai")

)
async def rag_query_pdf_ai(ctx: inngest.Context):
    def _search(question: str, top_k: int = 5,) -> RAGSearchResult:
        query_vec = embed_texts([question])[0]

        if hasattr(query_vec, "tolist"):
            query_vec = query_vec.tolist()
        
        print("Dimensión de la consulta:", len(query_vec))
        
        store = QdrantStorage()

        found = store.search(query_vec, top_k)

        print("Resultado de search:", found)
        print("Contexts encontrados:", found.get("contexts", []))
        print("Sources encontrados:", found.get("sources", []))
        
        return RAGSearchResult(contexts=found["contexts"], sources=found["sources"])
    
    question = ctx.event.data["question"]
    top_k = int(ctx.event.data.get("top_k", 5))

    found = await ctx.step.run("embed-and-search", lambda:_search(question, top_k), output_type=RAGSearchResult)

    #prompt
    context_block = "\n\n".join(f"-{c}" for c in found.contexts)
    user_content = (
        "Use the following context to answer the question. \n.\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n"
        "Answer concisely using the context above."
        "If the answer is not in the context, poltely indicate that you don't have the answer."
    )

    def _generate_answer() -> str:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens= 1024,
            temperature= 0.2,
            messages= [
                {"role": "system",
                "content": (
                    "You answer questions using only the provided context and don't ask any further questions to the user."
                    "You are polite and never respond to hate messages."),},
                {"role": "user",
                "content": user_content},
            ],
        
    )

        answer = response.choices[0].message.content
        return answer.strip()

    answer = await ctx.step.run(
    "llm-answer",
    _generate_answer,
    )

    return {
        "answer": answer,
        "sources": found.sources,
        "num_contexts": len(found.contexts),
    }
app = FastAPI()


inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf_ai])

