"""Local lexical vectors. No semantic model, external embeddings or uploads."""
from collections import Counter
import math
from ..common import fold

class VectorMemory:
    def __init__(self, store):
        self.store=store
    @staticmethod
    def vector(text):
        words=fold(text).split()
        # Character trigrams tolerate Turkish endings. This is lexical retrieval.
        return Counter(word[i:i+3] for word in words if len(word)>2 for i in range(len(word)-2))
    def search(self, query, limit=4):
        q=self.vector(query)
        qnorm=math.sqrt(sum(v*v for v in q.values()))
        if not qnorm:
            return []
        results=[]
        for row in self.store.knowledge():
            f=self.vector(row['fact'])
            norm=math.sqrt(sum(v*v for v in f.values()))
            score=sum(v*f.get(k,0) for k,v in q.items())/(qnorm*norm) if norm else 0
            if score>=0.25:
                results.append(row | {'score':round(score,3)})
        return sorted(results,key=lambda r:r['score'],reverse=True)[:limit]
