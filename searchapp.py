from flask import Flask, request
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Q, SF
import re
from pybars import Compiler
import math
import glob
import os

DEBUGGING = True
HITS_PER_PAGE = 10
template_cache = {}

compiler = Compiler()

PARTIALS = [
    os.path.basename(p).replace(".html", "")
    for p in glob.glob("site_templates/_*.html")
]


def get_template(name):
    if not DEBUGGING and name in template_cache:
        return template_cache[name]
    template = compiler.compile(open("site_templates/" + name + ".html").read())
    template_cache[name] = template
    return template


def get_partials():
    return {p: get_template(p) for p in PARTIALS}


app = Flask(__name__)
client = Elasticsearch()
search = Search(using=client, index="typophile")


def pages(response, current_page):
    total = response.hits.total.value
    total_pages = math.ceil(total / HITS_PER_PAGE)
    last_page = total_pages - 1
    relevant_pages = [
        x
        for x in range(current_page - 1, current_page + 2)
        if x > 0 and x < total_pages
    ]
    if relevant_pages:
        if 1 not in relevant_pages:
            if 2 not in relevant_pages:
                relevant_pages.insert(0, "...")
            relevant_pages.insert(0, 1)
        if not last_page in relevant_pages:
            if (last_page - 1) not in relevant_pages:
                relevant_pages.append("...")
            relevant_pages.append(last_page)
    if len(relevant_pages) == 1:
        return
    return [
        {"page": x, "linked": x != "...", "current": x == current_page}
        for x in relevant_pages
    ]


def fix_page(page):
    if page is not None:
        try:
            page = max(1, int(page))
        except Exception as e:
            page = 1
    else:
        page = 1
    return page


def do_search(
    query, page, special_query=None, order="date", filter_query=None, highlight=True
):
    base_query = Q(
        "query_string",
        query=query or "*",
        fields=["title^5", "body^2", "comments.body", "author", "comments.author.name"],
        default_operator="and",
    )
    if filter_query:
        base_query = Q(
            "bool",
            must=base_query,
            filter=[filter_query],
        )
    if special_query:
        s = search.query(special_query)
    elif order == "comments":
        s = search.query(base_query).sort("-comment_count")
    else:
        s = search.query(
            Q(
                "function_score",
                query=base_query,
                functions=[
                    SF(
                        "gauss",
                        date={
                            "origin": "now",
                            "scale": "365d",
                            "decay": 0.9,
                        },
                    )
                ],
            )
        )

    if highlight:
        s.update_from_dict({"highlight": {"fields": {"body": {}}}})
    if page:
        response = s[(page - 1) * HITS_PER_PAGE : (page) * HITS_PER_PAGE].execute()
    else:
        response = s.execute()
    return response


@app.route("/")
def index():
    query = request.args.get("q")
    order = request.args.get("o")
    page = fix_page(request.args.get("p"))
    response = do_search(query, page, order=order)
    hits = []
    total = None
    for hit in response:
        if "highlight" in hit.meta:
            highlight = " ... ".join(hit.meta.highlight.body)
        else:
            highlight = re.sub(r"(?s)[\r\n].*", "", hit.body)
        hits.append(
            {
                "node": hit.meta.id,
                "title": hit.title,
                "author": hit.author,
                "date": hit.date,
                "node_type": hit.node_type,
                "score": hit.meta.score,
                "highlight": highlight,
                "comment_count": hit.comment_count,
            }
        )
    total = response.hits.total.value
    template = get_template("search")
    return template(
        {
            "query": query,
            "response": hits,
            "total": total,
            "pages": pages(response, page),
            "order_comments": order == "comments",
        },
        partials=get_partials(),
    )


@app.route("/imagesearch")
def image_index():
    query = request.args.get("q")
    page = fix_page(request.args.get("p"))
    response = do_search(query, page, filter_query=Q("exists", field="files"))
    total = response.hits.total.value
    hits = [
        {
            "node": hit.meta.id,
            "title": hit.title,
            "author": hit.author,
            "date": hit.date,
            "files": hit.files,
            "node_type": hit.node_type,
            "score": hit.meta.score,
        }
        for hit in response
    ]

    template = get_template("imagesearch")

    return template(
        {
            "query": query,
            "response": hits,
            "total": total,
            "pages": pages(response, page),
        },
        partials=get_partials(),
    )
