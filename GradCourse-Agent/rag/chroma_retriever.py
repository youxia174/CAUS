"""可选 Chroma 后端。
默认仍使用轻量 TF-IDF；安装 chromadb 后，可将检索切换到本地 Chroma。
这里使用预计算的 TF-IDF 向量作为 embedding，因此不需要下载 embedding 模型。
"""
import numpy as np


class ChromaCourseRetriever:
    def __init__(self, summary, persist_dir="data/chroma"):
        try:
            import chromadb
        except ImportError as e:
            raise RuntimeError("未安装 chromadb，请 pip install chromadb") from e
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.data = summary.reset_index(drop=True).copy()
        self.data["_text"] = self.data.fillna("").astype(str).agg(" ".join, axis=1)
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3), min_df=1)
        matrix = self.vectorizer.fit_transform(self.data["_text"]).astype(np.float32).toarray()
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("courses_v3")
        ids = self.data["课程ID"].astype(str).tolist()
        self.collection.upsert(ids=ids, embeddings=matrix.tolist(), documents=self.data["_text"].tolist())

    def search(self, query, top_k=10):
        q = self.vectorizer.transform([query]).astype(np.float32).toarray()[0].tolist()
        res = self.collection.query(query_embeddings=[q], n_results=top_k)
        ids = (res.get("ids") or [[]])[0]
        lookup = self.data.set_index(self.data["课程ID"].astype(str))
        out = lookup.loc[[x for x in ids if x in lookup.index]].reset_index(drop=True)
        return out.drop(columns=["_text"], errors="ignore")
