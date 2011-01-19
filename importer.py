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
    # <td style="padding-top: 10px;" valign="top">
    attrs = {'style': 'padding-top: 10px;', 'valign': 'top'}
    tds = soup.findAll('td', attrs)

    ideas = []
    for i, td in enumerate(tds):
        title, author, sector = td.findAll('a')[:3]
        idea_id = find_id(title['href'])

        author_id = find_id(author['href'])
        author = make_author(author_id, author.string)

        sector_id = find_id(sector['href'])
        sector = Sector.get_by_id(sector_id)

        body = td.findAll('p', limit=1)[0]
        body = str(body)

        key = db.Key.from_path('Idea', idea_id)
        idea = Idea(key=key, author=author, sector=sector, body=body)
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

def find_id(s):
    return int(re.search(r'id=(\d+)', s).group(1))
