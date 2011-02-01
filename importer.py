import datetime
import logging
import re
from itertools import takewhile, imap
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
    print 'Importing sectors...'
    sectors = []
    links = soup.findAll('a', {'class':'sectiontitle'})
    for link in links:
        id = re.search(r'sectorid=(\d+)', link['href']).group(1)
        key = db.Key.from_path('Sector', int(id))
        sector = Sector(key=key, name=link.string.strip())
        sectors.append(sector)
        print u' - %s' % sector
    if commit:
        db.put(sectors)
    return sectors

def import_all():
    import_sectors()
    import_ideas()
    import_posts()

@withsoup('http://manorlabs.spigit.com/homepage?num_ideas=1000')
def import_ideas(soup, commit=True):
    print 'Importing ideas...'

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
        print ' - %s by %s' % (idea, author)

    if commit:
        db.put(ideas)

    return ideas

def import_posts(commit=True):
    ideas = Idea.all().fetch(1000)
    #ideas = [Idea.get_by_id(9)]
    print 'Importing posts for %s idea(s)...' % len(ideas)

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
        for header in headers:
            content = header.findNextSiblings('div', limit=1)[0]
            post = make_post(idea, header, content, commit=False)
            to_put.extend(post)

    to_put = filter(None, to_put)

    if commit:
        db.put(to_put)

    return to_put

def sibs(el):
    next = el.nextSibling
    while next:
        yield next
        next = next.nextSibling

def make_post(parent, header, content, commit=True, level=1):
    author_link = header.find('span', 'avatarusername').find('a')
    author = make_author(author_link)

    indent = ' ' * (level * 2)
    print '%s- Adding post by %s' % (indent, author)

    created_at = parse_post_date(author_link.parent.nextSibling)

    # gather up content elements
    els = iter(content) if content else sibs(header)
    def is_body(el):
        return el.name != 'pre' if isinstance(el, Tag) else True
    body = u'\n'.join(imap(unicode, takewhile(is_body, els)))

    post = Post.all()\
        .filter('papa =', parent)\
        .filter('author =', author)\
        .filter('created_at =', created_at)\
        .get()
    if post is None:
        post = Post(papa=parent, author=author,
                    created_at=created_at)
    post.body = body

    to_put = [post]

    if content:
        children = content.find('div', style='padding: 5px 0 0 40px;')
    else:
        children = None

    if children:
        to_put = []
        post.put()
        headers = children.findAll('div', 'commentheader', recursive=False)
        if headers:
            print '%s  (found %s child post(s))' % (indent, len(headers))
        for header in headers:
            to_put.extend(make_post(post, header, None, level=level+1))

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

def parse_post_date(s):
    s = s.replace('-', '').strip()
    now = datetime.datetime.now()
    date = datetime.datetime.strptime(s, '%b %d, %Y')
    return date.replace(hour=now.hour, minute=now.minute)



def idea_feed_url(idea):
    return 'http://manorlabs.spigit.com/feed/idea/%s' % idea.key().id()
