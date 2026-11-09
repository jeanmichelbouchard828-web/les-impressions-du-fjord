"""Non-destructive checks for the public third-party inspiration carousel."""
import unittest
from urllib.parse import urlparse,parse_qs
from html.parser import HTMLParser
from fjord_inspirations import IDEAS,html_fragment,_src

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images=[]
        self.links=[]
        self.articles=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='img':self.images.append(d)
        if tag=='a':self.links.append(d.get('href',''))
        if tag=='article':self.articles.append(d)

class InspirationTests(unittest.TestCase):
    def test_all_curated_examples_have_verifiable_image_rights(self):
        self.assertGreaterEqual(len(IDEAS),5)
        allowed={'CC0 1.0','CC BY-SA 4.0','CC BY-SA 3.0'}
        for idea in IDEAS:
            with self.subTest(title=idea['title']):
                self.assertIn(idea['license'],allowed)
                self.assertTrue(idea['license_url'].startswith('https://creativecommons.org/'))
                self.assertTrue(idea['author'])
                self.assertTrue(idea['file'].endswith('.jpg'))
                self.assertIn('/wikipedia/commons/thumb/',_src(idea['file']))
                self.assertTrue(idea['title'])

    def test_marked_as_inspiration_not_our_portfolio(self):
        text=html_fragment()
        self.assertIn('Photos d’inspiration provenant de Wikimedia Commons',text)
        self.assertIn('non de notre atelier',text)
        self.assertNotIn('Nos réalisations',text)
        self.assertIn('id="inspirations-3d"',text)
        self.assertIn('id="fji-prev"',text)
        self.assertIn('id="fji-next"',text)
        self.assertIn('aria-live="off"',text)
        dom=Links();dom.feed(text)
        self.assertEqual(len(dom.articles),len(IDEAS))
        self.assertEqual(len(dom.images),len(IDEAS))
        for idea,image in zip(IDEAS,dom.images):
            self.assertEqual(image['src'],_src(idea['file']))
            self.assertEqual(image['loading'],'lazy')
            self.assertTrue(image['alt'])
            self.assertIn('width',image)
            self.assertIn('height',image)
            self.assertTrue(any('commons.wikimedia.org' in link and idea['file'] in link for link in dom.links))
            self.assertIn(idea['license_url'],dom.links)
            matching_quotes=[u for u in dom.links if u.startswith('/soumission?') and parse_qs(urlparse(u).query).get('projet')==[idea['title']]]
            self.assertEqual(len(matching_quotes),1)

if __name__=='__main__':unittest.main(verbosity=2)
