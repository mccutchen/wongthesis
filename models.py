import logging
from google.appengine.ext import db


STAGES = ('Incubation', 'Validation', 'Emergence', 'Closed', 'Aborted')


class BaseModel(db.Model):

    host = 'http://manorlabs.spigit.com'

    @property
    def source_url(self):
        return '%s%s' % (self.host, self.make_source_url())

    def make_source_url(self):
        raise NotImplemented

    def __str__(self):
        return unicode(self).encode('utf-8')


class Sector(BaseModel):
    name = db.StringProperty()

    def make_source_url(self):
        return '/Sector/View?sectorid=%s' % self.key().id()

    def __unicode__(self):
        return self.name


class Author(BaseModel):
    username = db.StringProperty()

    def make_source_url(self):
        return '/User/View?userid=%s' % self.key().id()

    def __unicode__(self):
        return self.username


class Post(BaseModel):
    body = db.TextProperty()
    author = db.ReferenceProperty(Author, collection_name='posts')
    upvotes = db.IntegerProperty(default=0)
    downvotes = db.IntegerProperty(default=0)
    tags = db.StringListProperty()
    created_at = db.DateTimeProperty()

    def __unicode__(self):
        return u'Post:%s' % self.key().id()


class Idea(Post):
    title = db.StringProperty()
    sector = db.ReferenceProperty(Sector, collection_name='ideas')
    stage = db.StringProperty(choices=STAGES)
    views = db.IntegerProperty(default=0)

    @property
    def posts(self):
        return db.Query(Post).ancestor(self)

    def make_source_url(self):
        return '/Idea/View?ideaid=%s' % self.key().id()

    def __unicode__(self):
        return self.title
