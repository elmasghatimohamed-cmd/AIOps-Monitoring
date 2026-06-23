# bridge/services/vector_store.py
import chromadb
from chromadb.config import Settings

class ChromaVectorStore:
    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        self.host = host
        self.port = port
        self.client = None
        self.collections = {
            "incidents": None,
            "root_causes": None,
            "remediation": None,
            "operational_docs": None
        }

    def connect(self):
        """Establishes connection to the persistent ChromaDB service container."""
        try:
            self.client = chromadb.HttpClient(host=self.host, port=self.port)
            
            # Pre-initialize and cache all four core operations vector spaces
            for key in self.collections.keys():
                self.collections[key] = self.client.get_or_create_collection(name=key)
                
            print("[ChromaDB]: Vector semantic spaces initialized successfully.")
        except Exception as e:
            print(f"[ChromaDB Error]: Failed to build HTTP vector interface connections: {e}")

    def add_document(self, collection_name: str, doc_id: str, text: str, metadata: dict = None):
        """Helper to inject a raw text document block into a specific vector domain."""
        if not self.client or collection_name not in self.collections:
            print(f"[ChromaDB Warning]: Collection '{collection_name}' unmapped or connection dead.")
            return False
        
        try:
            collection = self.collections[collection_name]
            collection.add(
                documents=[text],
                metadatas=[metadata or {}],
                ids=[doc_id]
            )
            return True
        except Exception as e:
            print(f"[ChromaDB Write Error]: Failed writing to {collection_name}: {e}")
            return False

    def query_semantic_context(self, collection_name: str, query_text: str, n_results: int = 2):
        """Queries a collection to find matching text based on semantic meaning."""
        if not self.client or collection_name not in self.collections:
            return []
        
        try:
            collection = self.collections[collection_name]
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"[ChromaDB Query Error]: Retrieval operation failed: {e}")
            return []

vector_memory = ChromaVectorStore()