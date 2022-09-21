import glob
import yaml
import os
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from tqdm import tqdm

from elasticsearch import Elasticsearch
es = Elasticsearch()

es.indices.delete(index="typophile")

es.indices.create(index="typophile", mappings={
        "properties": {
            "date": { "type": "date","format": "yyyy-MM-dd HH:mm:ss" },
        }})


for i in tqdm(glob.glob("content/node/*.md")):
	nid = int(os.path.basename(i).replace(".md", ""))
	doc = open(i).read()
	doc = doc[:-4]
	doc = doc[4:]
	doc = yaml.load(doc, Loader=Loader)
	if "author" in doc:
		doc["author"] = doc["author"].get("name")
	es.index(index="typophile", id=nid, document=doc)


