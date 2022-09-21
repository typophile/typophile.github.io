import glob
import yaml
import os

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from tqdm import tqdm

from elasticsearch import Elasticsearch, helpers

es = Elasticsearch("http://localhost:9200")

from io import StringIO
from html.parser import HTMLParser
import markdown2


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(md):
    html = markdown2.markdown(md)
    s = MLStripper()
    s.feed(html)
    return s.get_data()


try:
    es.indices.delete(index="typophile")
except Exception as e:
    pass

es.indices.create(
    index="typophile",
    mappings={
        "properties": {
            "date": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
        }
    },
)


def bulk_data():
    for i in tqdm(glob.glob("content/node/*.md")):
        nid = int(os.path.basename(i).replace(".md", ""))
        doc = open(i).read()
        doc = doc[:-4]
        doc = doc[4:]
        doc = yaml.load(doc, Loader=Loader)
        if "author" in doc:
            doc["author"] = doc["author"].get("name")
        doc["body"] = strip_tags(doc["body"])
        yield {"_index": "typophile", "_id": nid, "_source": doc}


# es.index(index="typophile", id=nid, document=doc)
response = helpers.bulk(es, bulk_data())
