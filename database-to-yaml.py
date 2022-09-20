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
#   -> field_data_field_file

# comment
#   -> field_data_comment_body
#   -> field_revision_comment_body
#   -> field_data_field_file
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

    @property
    def files(self):
      res = session.scalars(select(FieldFile).filter_by(entity_id = self.nid, entity_type="node"))
      fids = [x.field_file_fid for x in res]
      file_list = session.query(ManagedFile).filter(ManagedFile.fid.in_(fids)).all()
      return file_list

class ManagedFile(Base):
    __tablename__ = "file_managed"
    fid = Column(primary_key=True)

class User(Base):
    __tablename__ = "users"
    uid = Column(primary_key=True)

class FieldFile(Base):
    __tablename__ = "field_data_field_file"

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

    @property
    def files(self):
      res = session.scalars(select(FieldFile).filter_by(entity_id = self.cid, entity_type="comment"))
      fids = [x.field_file_fid for x in res]
      file_list = session.query(ManagedFile).filter(ManagedFile.fid.in_(fids)).all()
      return file_list

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

def write_files(target, files):
  if not files:
    return

  target["files"] = [
    {
      "filename": f.filename,
      "uri": f.uri
    } for f in files
  ]

def add_nested_comments(c, target):
  comment = {
    "body": c.body.comment_body_value,
    "created": datetime.fromtimestamp(c.created).strftime(DATE_FORMAT)
  }
  write_files(comment, c.files)
  if c.children:
    comment["children"] = []

  write_user(c.user, comment)
  target.append(comment)
  for child in c.children:
    add_nested_comments(child, comment["children"])


for n in tqdm.tqdm(session.query(Node).all()):
  filename = "content/node/%i.md" % n.nid

  if not n.body:
    continue

  node = {
    "title": n.title,
    "node_type": n.type,
    "body": n.body.body_value,
    "date": datetime.fromtimestamp(n.created).strftime(DATE_FORMAT)
  }

  write_files(node, n.files)

  if n.comment_collection:
    node["comments"] = []
  write_user(n.user, node)
  for c in n.comment_collection:
    if c.pid != 0:
      continue
    add_nested_comments(c, node["comments"])
  yamlnode = dump(node, explicit_start=True,Dumper=Dumper)+"\n---\n"
  open(filename, "w").write(yamlnode)
