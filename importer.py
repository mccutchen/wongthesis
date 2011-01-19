import logging
import re
from functools import wraps

from google.appengine.api import urlfetch
from google.appengine.ext import db

from lib.BeautifulSoup import BeautifulSoup
from models import Sector, Author, Post, Idea

def withsoup(url):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            html = urlfetch.fetch(url).content
            soup = BeautifulSoup(html)
            return f(soup, *args, **kwargs)
        return decorated
    return decorator

@withsoup('http://manorlabs.spigit.com/Sector/List')
def import_sectors(soup, commit=True):
    sectors = []
    links = soup.findAll('a', {'class':'sectiontitle'})
    for link in links:
        id = re.search(r'sectorid=(\d+)', link['href']).group(1)
        key = db.Key.from_path('Sector', int(id))
        sector = Sector(key=key, name=link.string.strip())
        sectors.append(sector)
    if commit:
        db.put(sectors)
    return sectors

@withsoup('http://manorlabs.spigit.com/homepage?num_ideas=1000')
def import_ideas(soup, commit=True):
    # <table class="bottomline" width="100%">
    rows = soup\
        .find('table', 'bottomline')\
        .find('tbody')\
        .findAll('tr', recursive=False)

    ideas = []
    for i, row in enumerate(rows[:-1]):
        votes, content = row.findAll('td', recursive=False)

        # Pull out content first
        title, author, sector = content.findAll('a')[:3]
        idea_id = find_int(title['href'])

        author_id = find_int(author['href'])
        author = make_author(author_id, author.string)

        sector_id = find_int(sector['href'])
        sector = Sector.get_by_id(sector_id)

        body = content.findAll('p', limit=1)[0]
        body = str(body)

        # Then pull out votes
        upvotes_el = votes.find('strong')
        upvotes = find_int(upvotes_el.string.strip())

        downvotes = upvotes_el.nextSibling.nextSibling.nextSibling
        downvotes = find_int(str(downvotes).strip())

        # Create the idea
        key = db.Key.from_path('Idea', idea_id)
        idea = Idea(key=key, author=author, sector=sector,
                    title=str(title.string), body=body,
                    upvotes=upvotes, downvotes=downvotes)
        ideas.append(idea)

    if commit:
        db.put(ideas)

    return ideas

def make_author(id, username, commit=True):
    key = db.Key.from_path('Author', int(id))
    author = Author(key=key, username=unicode(username))
    if commit:
        author.put()
    return author

def find_int(s):
    return int(re.search(r'(\d+)', s).group(1))
