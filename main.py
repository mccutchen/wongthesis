import os
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from models import Idea, Sector, Author, Post


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


urls = [
    (r'^/$', IndexHandler),
    (r'^/idea/(\d+)', IdeaHandler),
    ]

application = webapp.WSGIApplication(urls, debug=True)

def main():
	run_wsgi_app(application)

if __name__ == '__main__':
	main()
