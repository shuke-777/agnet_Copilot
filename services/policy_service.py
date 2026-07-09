import math
from functools import lru_cache

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from memory.policy_knowledge import POLICY_DOCUMENTS
from schemas.policy import PolicySource


KEYWORD_VOCABULARY = (
    "物流",
    "超过",
    "72",
    "小时",
    "未更新",
    "异常",
    "催物流",
    "工单",
    "承运商",
    "卡点",
    "正常",
    "运输",
    "签收",
    "话术",
    "安抚",
    "回复",
)


class DeterministicPolicyEmbedding(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [float(text.count(keyword)) for keyword in KEYWORD_VOCABULARY]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


@lru_cache(maxsize=1)
def get_policy_vector_store() -> FAISS:
    return FAISS.from_documents(
        documents=POLICY_DOCUMENTS,
        embedding=DeterministicPolicyEmbedding(),
    )


def lexical_relevance(query: str, content: str) -> float:
    matched = sum(1 for keyword in KEYWORD_VOCABULARY if keyword in query and keyword in content)
    query_terms = sum(1 for keyword in KEYWORD_VOCABULARY if keyword in query)
    if query_terms == 0:
        return 0.0
    return matched / query_terms


def retrieve_after_sales_policies(
    *,
    query: str,
    is_abnormal: bool | None,
    limit: int = 2,
    score_threshold: float = 0.05,
) -> list[PolicySource]:
    vector_store = get_policy_vector_store()
    candidates = vector_store.similarity_search(query, k=len(POLICY_DOCUMENTS))

    ranked: list[PolicySource] = []
    for document in candidates:
        scenario = document.metadata.get("scenario")
        relevance = lexical_relevance(query, document.page_content)
        if is_abnormal is True and scenario == "abnormal_logistics":
            relevance += 0.3
        elif is_abnormal is False and scenario == "normal_logistics":
            relevance += 0.3
        elif scenario == "general_reply":
            relevance += 0.1

        if relevance < score_threshold:
            continue

        ranked.append(
            PolicySource(
                source_id=str(document.metadata["source_id"]),
                title=str(document.metadata["title"]),
                content=document.page_content,
                score=round(relevance, 4),
            )
        )

    ranked.sort(key=lambda policy: policy.score, reverse=True)
    return ranked[:limit]
