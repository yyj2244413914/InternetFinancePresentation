# -*- coding: utf-8 -*-
"""
text_analysis —— 违规事由的文本挖掘（D 线）
==========================================
不依赖分词器的中文短语抽取：处罚事由本身就由「、，；」分句，
分句后长度 4–20 字的片段即为规范表述（如「贷款三查不到位」），
比通用分词更贴合监管文本。

功能：
  · phrase_freq      高频违规表述
  · tfidf_kmeans     字符 n-gram TF-IDF + KMeans 主题聚类
  · cooccurrence     违规表述共现（同一案件内共同出现）
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

SPLIT_RE = re.compile(r"[、，,；;。\n（）()【】\[\]]")
# 无信息量的泛化表述
STOP_PHRASES = {
    "以上违规行为", "上述行为", "违法行为", "违规行为", "违法违规行为", "相关责任人",
    "其他违规行为", "违反审慎经营规则", "严重违反审慎经营规则", "违反《中华人民共和国银行业监督管理法》",
}


def phrases(texts, min_len: int = 4, max_len: int = 20) -> Counter:
    cnt = Counter()
    for t in texts:
        if not isinstance(t, str):
            continue
        for seg in SPLIT_RE.split(t):
            seg = re.sub(r"\s+", "", seg)
            if min_len <= len(seg) <= max_len and seg not in STOP_PHRASES:
                cnt[seg] += 1
    return cnt


def phrase_freq(df: pd.DataFrame, column: str = "违法违规事实",
                top: int = 30, min_len: int = 4) -> pd.Series:
    cnt = phrases(df[column].dropna().astype(str), min_len=min_len)
    return pd.Series(dict(cnt.most_common(top)), name="出现次数")


def tfidf_kmeans(texts, k: int = 5, top_terms: int = 8,
                 seed: int = 42) -> tuple[pd.DataFrame, np.ndarray, TfidfVectorizer]:
    """字符 2–4 gram TF-IDF + KMeans，返回每个主题的高权重词与样本归属。"""
    docs = [re.sub(r"\s+", "", t) if isinstance(t, str) else "" for t in texts]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                          min_df=5, max_features=4000)
    X = vec.fit_transform(docs)
    km = KMeans(n_clusters=k, random_state=seed, n_init=10)
    labels = km.fit_predict(X)
    terms = np.array(vec.get_feature_names_out())
    rows = []
    for i in range(k):
        center = km.cluster_centers_[i]
        idx = center.argsort()[::-1][:top_terms]
        rows.append({
            "主题": f"主题{i + 1}",
            "样本数": int((labels == i).sum()),
            "占比": f"{(labels == i).mean():.1%}",
            "代表性表述": "、".join(terms[idx]),
        })
    return pd.DataFrame(rows), labels, vec


def cooccurrence(df: pd.DataFrame, column: str = "违法违规事实",
                 top: int = 15, min_len: int = 4) -> pd.DataFrame:
    """同一处罚记录内高频表述的共现矩阵。"""
    cnt = phrases(df[column].dropna().astype(str), min_len=min_len)
    vocab = [w for w, _ in cnt.most_common(top)]
    idx = {w: i for i, w in enumerate(vocab)}
    mat = np.zeros((len(vocab), len(vocab)), dtype=int)
    for t in df[column].dropna().astype(str):
        present = {idx[s] for s in (re.sub(r"\s+", "", x)
                                    for x in SPLIT_RE.split(t))
                   if s in idx}
        for a in present:
            for b in present:
                if a != b:
                    mat[a, b] += 1
    return pd.DataFrame(mat, index=vocab, columns=vocab)


# ---------------------------------------------------------------- 关键词检索
def top_keywords_in(df: pd.DataFrame, keyword: str, column: str = "违法违规事实",
                    top: int = 15) -> pd.Series:
    """含某关键词的记录里，还高频出现哪些表述（用于"贷款三查"下钻）。"""
    sub = df[df[column].astype(str).str.contains(keyword, na=False)]
    return phrase_freq(sub, column=column, top=top)
