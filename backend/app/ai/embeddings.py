import hashlib
from typing import List

class MockEmbeddings:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        # Create a deterministic pseudorandom vector based on the string hash
        vec = []
        for i in range(self.dimension):
            h = int(hashlib.md5((text + str(i)).encode('utf-8')).hexdigest(), 16)
            # Normalize roughly to [-1, 1]
            val = (h % 2000 - 1000) / 1000.0
            vec.append(val)
        
        # normalize to unit length
        norm = sum(x**2 for x in vec) ** 0.5
        if norm > 0:
            return [x / norm for x in vec]
        return vec

def get_embeddings():
    return MockEmbeddings()
