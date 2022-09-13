from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select, Integer
from sqlalchemy.orm import relationship
from sqlalchemy import Column, ForeignKey
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
import tqdm
import os
from datetime import datetime

DATE_FORMAT = r"%Y-%m-%d %H:%M:%S"

# node
#   -> field_solved_by
#   -> field_tags

# comment
#   -> field_data_comment_body
#   -> field_revision_comment_body
#   cid: ID
#   nid: node
#   pid: comment parent
#   subject
#   uid: user id

# user
#   -> field_data_field_twitter


Base = automap_base()

class Node(Base):
    __tablename__ = 'node'
    nid = Column(primary_key=True)
    uid = Column(ForeignKey('users.uid'))
    user = relationship("User")
    # body = relationship("NodeBody", uselist=False, foreign_keys='NodeBody.entity_id')
    comment_collection = relationship("Comment", foreign_keys='Comment.nid')
    @property
    def body(self):
      return session.scalar(select(NodeBody).where(NodeBody.entity_id == self.nid))

class User(Base):
    __tablename__ = "users"
    uid = Column(primary_key=True)

class NodeBody(Base):
    __tablename__ = "field_data_body"
    entity_id = Column(ForeignKey("node.nid"))

class Comment(Base):
    __tablename__ = "comment"
    cid = Column(primary_key=True)
    uid = Column(ForeignKey('users.uid'))
    nid = Column(ForeignKey('node.nid'))
    user = relationship("User")
    pid = Column(ForeignKey('comment.cid'))
    # body = relationship("CommentBody", foreign_keys="CommentBody.entity_id", uselist=False)
    children = relationship("Comment", primaryjoin=cid == pid)
    @property
    def body(self):
      return session.scalar(select(CommentBody).where(CommentBody.entity_id == self.cid))

class CommentBody(Base):
    __tablename__ = "field_data_comment_body"
    # entity_id = Column(ForeignKey("comment.cid"))
    # comment = relationship("Comment", primaryjoin=entity_id==Comment.cid)


engine = create_engine("mysql://root@localhost/typophile")
Base.prepare(autoload_with=engine)

session = Session(engine)

count = 1

def write_user(user, thing):
  if not user:
    return
  if user.name:
    thing["author"] = {
      "name": user.name,
    }
  if user.picture:
    thing["author"]["picture"] = user.picture

def add_nested_comments(c, target):
  comment = {
    "body": c.body.comment_body_value,
    "created": datetime.fromtimestamp(c.created).strftime(DATE_FORMAT)
  }
  if c.children:
    comment["children"] = []

  write_user(c.user, comment)
  target.append(comment)
  for child in c.children:
    add_nested_comments(child, comment["children"])

for n in tqdm.tqdm(session.query(Node).all()):
  filename = "yaml/%i.md" % n.nid
  if n.nid > 1000:
    break

  if not n.body:
    continue

  node = {
    "title": n.title,
    "body": n.body.body_value,
    "date": datetime.fromtimestamp(n.created).strftime(DATE_FORMAT)
  }
  if n.user.name:
    node["author"] = n.user.name

  if n.comment_collection:
    node["comments"] = []
  write_user(n.user, node)
  for c in n.comment_collection:
    if c.pid != 0:
      continue
    add_nested_comments(c, node["comments"])
  open(filename, "w").write(dump(node, explicit_start=True,explicit_end=True,Dumper=Dumper))
