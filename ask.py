import urllib.request, json, textwrap


def ask(question):
    data = json.dumps({"query": question}).encode()
    req = urllib.request.Request(
        "http://localhost:8000/query", data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    print()
    print("═" * 70)
    print("  QUESTION")
    print("═" * 70)
    print(f"  {result['query']}")
    print()
    print("═" * 70)
    print("  ANSWER")
    print("═" * 70)
    for line in textwrap.wrap(result["answer"], width=66):
        print(f"  {line}")
    print()
    print("═" * 70)
    print("  SOURCES")
    print("═" * 70)
    for i, s in enumerate(result["sources"], 1):
        print(f"  [{i}] {s['document_title']}")
        print(
            f"      Page {s['page_number']}  |  RRF: {s['rrf_score']:.4f}  |  BM25: {s['bm25_score']:.4f}"
        )
        if s.get("section_heading"):
            print(f"      Section: {s['section_heading']}")
    print("═" * 70)
    print()


ask(
    "Among all employees listed in the knowledge base, identify who has the strongest background in Data Science. For each candidate, state their specific skills, years of experience, relevant certifications, and current project workload. Then rank them and recommend the single best person to lead a new Data Science pipeline development project, with a clear justification based on skills and availability."
)
