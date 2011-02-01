import os
import logging

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


class TagsHandler(BaseHandler):

    def get(self, path=None):
        if 'q' in self.request.params and not path:
            q = self.request.params.get('q').strip()
            matches = [tag for tag in TAGS if q.lower() in tag.lower()]
            resp = [{'id': match, 'name': match} for match in matches]
            self.response.headers['Content-Type'] = 'application/json'
            self.response.out.write(json.dumps(resp))

    def post(self, path=None):
        key = self.request.POST.get('key')
        tags = self.request.POST.get('tags')

        if None in (key, tags):
            self.error(500)
            return self.response.out.write('Missing key or tags')

        tags = [tag.strip() for tag in tags.split(',') if tag.strip() in TAGS]
        if not tags:
            self.error(500)
            return self.response.out.write('No valid tags given')

        def txn():
            obj = db.get(key)
            if obj is None:
                self.error(500)
                return self.response.out.write('Entity %r not found' % key)
            obj.tags = list(set(obj.tags or []).union(set(tags)))
            obj.put()
            return obj
        obj = db.run_in_transaction(txn)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(obj.tags))


urls = [
    (r'^/$', IndexHandler),
    (r'^/idea/(\d+)', IdeaHandler),
    (r'^/tags(.*)', TagsHandler),
    ]

application = webapp.WSGIApplication(urls, debug=True)

def main():
	run_wsgi_app(application)

if __name__ == '__main__':
	main()
