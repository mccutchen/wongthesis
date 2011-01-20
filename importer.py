import datetime
import logging
import re
from itertools import takewhile
from functools import wraps

from google.appengine.api import urlfetch
from google.appengine.ext import db

from lib.BeautifulSoup import BeautifulSoup, Tag, NavigableString
from lib import feedparser
from models import Sector, Author, Post, Idea


def make_soup(url):
    html = urlfetch.fetch(url).content
    return BeautifulSoup(html)

def withsoup(url):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            return f(make_soup(url), *args, **kwargs)
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
        raw = unicode(content)

        # Pull out content first
        title, author, sector = content.findAll('a')[:3]
        idea_id = find_int(title['href'])

        raw_date = sector.nextSibling
        created_at = parse_idea_date(raw_date)

        author = make_author(author)

        sector_id = find_int(sector['href'])
        sector = Sector.get_by_id(sector_id)

        upvotes_el = votes.find('strong')
        upvotes = find_int(upvotes_el.string.strip())

        downvotes = upvotes_el.nextSibling.nextSibling.nextSibling
        downvotes = find_int(str(downvotes).strip())

        views = find_int(re.search(r'(\d+) Views', raw).group(1))
        stage = re.search(r'Stage : (\w+)', raw).group(1)

        # Create the idea
        key = db.Key.from_path('Idea', idea_id)
        idea = Idea(
            key=key,
            author=author,
            sector=sector,
            title=unicode(title.string),
            upvotes=upvotes,
            downvotes=downvotes,
            views=views,
            stage=stage,
            created_at=created_at)
        ideas.append(idea)

    if commit:
        db.put(ideas)

    return ideas

def import_posts(commit=True):
    ideas = Idea.all().fetch(1000)
    print 'Importing posts for %s idea(s)' % len(ideas)

    to_put = []
    for idea in ideas:
        soup = make_soup(idea.source_url)

        # We get the idea's actual body from the RSS feed
        rss = feedparser.parse(idea_feed_url(idea))
        idea.body = rss.feed.subtitle.replace(
            '\nFeed Created by spigit.com feed manager.', '')
        to_put.append(idea)

        headers = soup.find('td', 'main')\
            .findAll('div', 'commentheader', recursive=False)
        print ' Found %s posts on idea %s' % (len(headers), idea)

        for header in headers:
            content = header.findNextSiblings('div', limit=1)[0]
            post = make_post(idea, header, content, commit=False)
            to_put.extend(post)

    to_put = filter(None, to_put)

    if commit:
        db.put(to_put)

    return to_put

def make_post(parent, header, content, commit=True):
    author_link = header.find('span', 'avatarusername').find('a')
    author = make_author(author_link)
    print '  Adding post by %s' % (author)

    # gather up content elements
    els = iter(content)
    def is_body(el):
        return el.get('class') != 'smvote' if isinstance(el, Tag) else True
    body = takewhile(is_body, els)
    body = '\n'.join(str(el) for el in body)

    id = find_int(content['id'])
    key = db.Key.from_path('Post', id, parent=parent.key())
    post = Post(key=key, author=author, body=body)

    to_put = [post]

    if commit:
        db.put(to_put)

    return to_put

def make_author(author_link, commit=True):
    id = find_int(author_link['href'])
    username = unicode(author_link.string)
    key = db.Key.from_path('Author', int(id))
    author = Author(key=key, username=username)
    if commit:
        author.put()
    return author

def find_int(s):
    return int(re.search(r'(\d+)', s).group(1))

def parse_idea_date(s):
    s = ' '.join(s.strip().split(' ')[1:-1])
    return datetime.datetime.strptime(s, '%m/%d/%Y %I:%M %p')

def idea_feed_url(idea):
    return 'http://manorlabs.spigit.com/feed/idea/%s' % idea.key().id()
