"""Offline checks for 50 authenticated Commons photographs and ready-to-quote ideas."""
import unittest
from html.parser import HTMLParser
from urllib.parse import urlparse,parse_qs
from fjord_inspirations import IDEAS,html_fragment,CATEGORIES,_safe_url

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.images=[];self.links=[];self.articles=[];self.filters=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="img":self.images.append(d)
        if tag=="a":self.links.append(d.get("href",""))
        if tag=="article":self.articles.append(d)
        if tag=="button" and "data-fji-filter" in d:self.filters.append(d)

class InspirationTests(unittest.TestCase):
    def test_50_unique_authentic_commons_images_with_licences(self):
        self.assertEqual(len(IDEAS),50)
        self.assertEqual(len({x["filename"].casefold() for x in IDEAS}),50)
        self.assertEqual(len({x["image"] for x in IDEAS}),50)
        self.assertEqual(len({x["category"] for x in IDEAS}),6)
        allowed=("CC BY 2.0","CC BY 2.5","CC BY 3.0","CC BY 4.0",
                 "CC BY-SA 2.0","CC BY-SA 3.0","CC BY-SA 4.0","CC0","CC0 1.0","Public domain")
        for idea in IDEAS:
            with self.subTest(title=idea["title"]):
                self.assertIn(idea["license"],allowed)
                self.assertTrue(idea["author"])
                self.assertTrue(_safe_url(idea["image"],("thumb.wikimedia.org","upload.wikimedia.org")))
                self.assertTrue(_safe_url(idea["source"],("commons.wikimedia.org",)))
                self.assertTrue(_safe_url(idea["license_url"],("creativecommons.org","commons.wikimedia.org")))
                self.assertIn(idea["category"],dict(CATEGORIES))

    def test_clearly_marked_as_inspiration_not_our_portfolio(self):
        text=html_fragment()
        self.assertIn("50 photos provenant de Wikimedia Commons",text)
        self.assertIn("ce ne sont pas des réalisations de notre atelier",text)
        self.assertIn("licences photo ne donnent pas automatiquement le droit",text)
        self.assertNotIn("Nos réalisations",text)
        self.assertIn('id="inspirations-3d"',text)
        self.assertIn('id="fji-prev"',text)
        self.assertIn('id="fji-next"',text)
        self.assertIn('aria-live="off"',text)
        dom=Links();dom.feed(text)
        self.assertEqual(len(dom.articles),50)
        self.assertEqual(len(dom.images),50)
        self.assertEqual(len(dom.filters),7)
        self.assertEqual(dom.filters[0]["data-fji-filter"],"all")
        for index,(idea,image) in enumerate(zip(IDEAS,dom.images)):
            self.assertEqual(image["src"],idea["image"])
            self.assertEqual(image["loading"],"lazy")
            self.assertTrue(image["alt"])
            self.assertIn("width",image)
            self.assertIn("height",image)
            self.assertIn(idea["source"],dom.links)
            self.assertIn(idea["license_url"],dom.links)
            links=[x for x in dom.links if x.startswith("/soumission?")
                   and parse_qs(urlparse(x).query).get("inspiration")==[str(index)]]
            self.assertEqual(len(links),1)

    def test_no_unexpected_hosts_or_inline_scripts_in_source(self):
        text=html_fragment()
        self.assertNotIn("<script",text)
        self.assertNotIn("javascript:",text)
        self.assertNotIn('onclick=',text)
        for idea in IDEAS:
            self.assertNotIn('onerror=',idea["image"])

if __name__=="__main__":unittest.main(verbosity=2)
