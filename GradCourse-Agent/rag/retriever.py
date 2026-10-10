from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class CourseRetriever:
    """轻量本地语义检索：字符 n-gram TF-IDF，避免首次运行下载大模型。"""
    def __init__(self, summary):
        self.data = summary.reset_index(drop=True).copy()
        self.data["_text"] = self.data.fillna("").astype(str).agg(" ".join, axis=1)
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3), min_df=1, sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(self.data["_text"]) if len(self.data) else None

    def search(self, query, top_k=10):
        if not query or self.matrix is None: return self.data.head(top_k).drop(columns=["_text"], errors="ignore")
        q = self.vectorizer.transform([query])
        scores = cosine_similarity(q, self.matrix).ravel()
        idx = scores.argsort()[::-1][:top_k]
        out = self.data.iloc[idx].copy()
        out["检索相关度"] = scores[idx].round(4)
        return out.drop(columns=["_text"], errors="ignore")
