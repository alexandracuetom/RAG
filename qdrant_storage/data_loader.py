from groq import Groq
import os
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

EMBED_MODEL = SentenceTransformer("BAAI/bge-m3")
EMBED_DIM =1024 #must match dimension of qdrant

splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)

def load_and_chunk_pdf(path: str):
    docs = PDFReader().load_data(file=path)
    texts= [d.text for d in docs if getattr(d, "text", None)]
    chunks = []
    for t in texts:
        chunks.extend(splitter.split_text(t))

    return chunks

def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = EMBED_MODEL.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


from groq import Groq
import os
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

EMBED_MODEL = SentenceTransformer("BAAI/bge-m3")
EMBED_DIM =3072 #must match dimension of qdrant

splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)

def load_and_chunk_pdf(path: str):
    docs = PDFReader().load_data(file=path)
    texts= [d.text for d in docs if getattr(d, "text", None)]
    chunks = []
    for t in texts:
        chunks.extend(splitter.split_text(t))

    return chunks

def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = EMBED_MODEL.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()

