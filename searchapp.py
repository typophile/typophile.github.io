from flask import Flask, request
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

from pybars import Compiler
import math

DEBUGGING = True
HITS_PER_PAGE = 10

compiler = Compiler()
template_src = open("search-template.html").read()
template = compiler.compile(template_src)


app = Flask(__name__)
client = Elasticsearch()
search = Search(using=client, index="typophile")


@app.route("/")
def index():
    if DEBUGGING:
        template_src = open("search-template.html").read()
        template = compiler.compile(template_src)

    query = request.args.get("q")
    page = request.args.get("p")
    if page is not None:
        try:
            page = max(1, int(page))
        except Exception as e:
            page = 1
    else:
        page = 1
    print(query)
    hits = []
    pages = []
    total = None
    if query:
        s = search.query("query_string", query=query, default_field="body").highlight(
            "title", "body"
        )
        s.source(includes=["date"])
        if page:
            response = s[(page - 1) * HITS_PER_PAGE : (page) * HITS_PER_PAGE].execute()
        else:
            response = s.execute()
        for hit in response:
            if "highlight" in hit.meta:
                highlight = " ... ".join(hit.meta.highlight.body)
            else:
                highlight = ""
            hits.append(
                {
                    "node": hit.meta.id,
                    "title": hit.title,
                    "author": hit.author,
                    "date": hit.date,
                    "score": hit.meta.score,
                    "highlight": highlight,
                }
            )
        total = response.hits.total.value
        total_pages = math.ceil(total / HITS_PER_PAGE)
        last_page = total_pages - 1
        relevant_pages = [
            x for x in range(page - 1, page + 2) if x > 0 and x < total_pages
        ]
        if 1 not in relevant_pages:
            if 2 not in relevant_pages:
                relevant_pages.insert(0, "...")
            relevant_pages.insert(0, 1)
        if not last_page in relevant_pages:
            if (last_page - 1) not in relevant_pages:
                relevant_pages.append("...")
            relevant_pages.append(last_page)
        pages = [
            {"page": x, "linked": x != "...", "current": x == page}
            for x in relevant_pages
        ]

    return template({"query": query, "response": hits, "total": total, "pages": pages})
