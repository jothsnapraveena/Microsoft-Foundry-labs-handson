"""Product agent: model-generated queries plus keyword search over the local catalog."""
import json
from pathlib import Path
import re

from contracts import COMMON, ContractError

NAME = "product"
PROMPT = COMMON + ('\nProduce search queries for a product catalog from the ordered and '
                   'received items. Return {"queries":["..."]} with 1 to 5 short strings.')
CATALOG_FILE = Path(__file__).parents[3] / "catalog/products.json"
CATALOG = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
MAX_MATCHES = 5


def valid(value):
    queries = value.get("queries")
    return (set(value) == {"queries"} and isinstance(queries, list) and 1 <= len(queries) <= 5
            and all(isinstance(q, str) and 0 < len(q.strip()) <= 100 for q in queries))


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def keyword_search(query, top_k=2):
    """Keyword-overlap search keeping only the best-scoring products."""
    wanted = words(query)
    scored = [(len(wanted & words(f"{p['title']} {p['content']}")), p) for p in CATALOG]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best = scored[0][0]
    return [p for score, p in scored[:top_k] if score and score == best]


def find_products(pipeline, facts, result):
    # The customer message is withheld: queries come from trusted facts only.
    try:
        queries = (yield from pipeline.invoke(NAME, {"trusted_facts": facts}, result))["queries"]
    except ContractError:
        queries = []
    # The fact values are always searched, so retrieval never depends on the model.
    matches = {}
    for query in (facts["ordered"], facts["received"], *queries):
        for item in keyword_search(query):
            matches.setdefault(item["id"], item)
    return list(matches.values())[:MAX_MATCHES]
