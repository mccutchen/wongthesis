import logging
from google.appengine.ext import db


class Sector(db.Model):
    name = db.StringProperty()


class Author(db.Model):
    username = db.StringProperty()


class Post(db.Model):
    body = db.TextProperty()
    author = db.ReferenceProperty(Author, collection_name='posts')
    upvotes = db.IntegerProperty(default=0)
    downvotes = db.IntegerProperty(default=0)
    tags = db.StringListProperty()


class Idea(Post):
    title = db.StringProperty()
    sector = db.ReferenceProperty(Sector, collection_name='ideas')
