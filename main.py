import os
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from models import Idea, Sector, Author, Post


class BaseHandler(webapp.RequestHandler):

    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

    def render(self, path, context, status=200):
        path = os.path.join(self.template_dir, path)
        self.response.set_status(200)
        self.response.out.write(template.render(path, context))


class IndexHandler(BaseHandler):

    def get(self):
        ideas = Idea.all().fetch(1000)
        self.render('index.html', {'ideas': ideas})


urls = [
    (r'^/$', IndexHandler),
    ]

application = webapp.WSGIApplication(urls, debug=True)

def main():
	run_wsgi_app(application)

if __name__ == '__main__':
	main()
