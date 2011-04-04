import os
import logging
import urllib

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from django.utils import simplejson as json

from models import Idea, Sector, Author, Post, TAGS, STAGES


class BaseHandler(webapp.RequestHandler):

    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

    context = {
        'tags': TAGS,
        'stages': STAGES,
        }

    def render(self, path, context=None, status=200):
        local_context = dict(self.context)
        local_context.update(context or {})
        path = os.path.join(self.template_dir, path)
        self.response.set_status(200)
        self.response.out.write(template.render(path, local_context))


class IndexHandler(BaseHandler):

    def get(self):
        ideas = Idea.all().fetch(1000)
        self.render('index.html', {'ideas': ideas})


class IdeaHandler(BaseHandler):

    def get(self, id):
        idea = Idea.get_by_id(int(id))
        if idea is None:
            self.error(404)
            self.response.out.write('Idea not found.')
            return

        self.render('idea.html', {'idea': idea})


class BrowseHandler(BaseHandler):

    def get_facet(self, facet, criteria):
        return None

    def get_ideas(self, facet, criteria):
        return []

    def get_posts(self, facet, criteria):
        return []

    def get(self, facet, criteria):
        try:
            facet = self.get_facet(facet, criteria)
            ideas = self.get_ideas(facet, criteria)
            posts = self.get_posts(facet, criteria)
        except Exception, e:
            raise
            logging.error('Could not browse by %s %r: %s', facet, criteria, e)
            self.error(404)
            self.response.out.write('%s %s not found.' % (facet, criteria))
        else:
            ctx = { 'facet': facet, 'ideas': ideas, 'posts': posts }
            return self.render('browse.html', ctx)


class SectorHandler(BrowseHandler):
    def get_facet(self, facet, criteria):
        return Sector.get_by_id(int(criteria))
    def get_ideas(self, facet, criteria):
        return facet.ideas.fetch(1000)

class StageHandler(BrowseHandler):
    def get_facet(self, facet, criteria):
        return criteria
    def get_ideas(self, facet, criteria):
        return Idea.all().filter('stage =', criteria).fetch(1000)

class AuthorHandler(BrowseHandler):
    def get_facet(self, facet, criteria):
        return Author.get_by_id(int(criteria))
    def get_ideas(self, facet, criteria):
        return Idea.all().filter('author =', facet).fetch(1000)
    def get_posts(self, facet, criteria):
        return Post.all().filter('author =', facet).fetch(1000)

class TagHandler(BrowseHandler):
    def get_facet(self, facet, criteria):
        return 'Tag'
    def get_ideas(self, facet, criteria):
        return Idea.all().filter('tags =', urllib.unquote(criteria))\
            .fetch(1000)
    def get_posts(self, facet, criteria):
        return Post.all().filter('tags =', urllib.unquote(criteria))\
            .fetch(1000)


class TagsHandler(BaseHandler):
    """Handles the tag-completion choices on GET and updates the tags on
    arbitrary items on POST."""

    def get(self, path=None):
        # Special case for tag completion choices
        if 'q' in self.request.params and not path:
            q = self.request.params.get('q').strip()
            matches = [tag for tag in TAGS if q.lower() in tag.lower()]
            resp = [{'id': match, 'name': match} for match in matches]
            self.response.headers['Content-Type'] = 'application/json'
            self.response.out.write(json.dumps(resp))
            return

    def post(self, path=None):
        key = self.request.POST.get('key')
        given_tags = self.request.POST.get('tags')

        if None in (key, given_tags):
            self.error(500)
            return self.response.out.write('Missing key or tags')

        tags = [tag.strip() for tag in given_tags.split(',')
                if tag.strip() in TAGS]
        logging.info('Given tags: %r', given_tags)
        logging.info('Valid tags: %r', tags)

        if not tags and not given_tags:
            self.error(500)
            return self.response.out.write('No valid tags given')

        def txn():
            obj = db.get(key)
            if obj is None:
                self.error(500)
                return self.response.out.write('Entity %r not found' % key)
            obj.tags = tags
            obj.put()
            return obj
        obj = db.run_in_transaction(txn)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(obj.tags))


urls = [
    (r'^/$', IndexHandler),
    (r'^/idea/(\d+)', IdeaHandler),
    (r'^/(sector)/(\d+)', SectorHandler),
    (r'^/(stage)/(\w+)', StageHandler),
    (r'^/(author)/(\d+)', AuthorHandler),
    (r'^/(tag)/(.+)', TagHandler),
    (r'^/tags$', TagsHandler),
    ]

application = webapp.WSGIApplication(urls, debug=True)

def main():
	run_wsgi_app(application)

if __name__ == '__main__':
	main()
