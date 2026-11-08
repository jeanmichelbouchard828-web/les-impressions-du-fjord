"""Payment and taxation invariants, with no live payment service or bank access."""
import unittest
from private_fjord import (_quote_amounts, _quote_military_discount,
                           _active_square_url, _square_checkout_url,
                           _payment_link_provider, _quote_acceptance_digest)

def quote(**extras):
    q={"id":1,"customer":"Client test","email":"test@example.invalid","title":"Pièce sur mesure",
       "description":"Support 3D","material":"PETG","unit_price":100.0,"quantity":1,
       "shipping":0.0,"apply_taxes":True,"military_discount":False,
       "square_link_url":None,"square_link_amount_cents":None}
    q.update(extras)
    return q

class FinancialSafetyTests(unittest.TestCase):
    def test_quebec_taxes_half_cent_round_up(self):
        self.assertEqual(_quote_amounts(quote()),(100.0,5.0,9.98,114.98))
        self.assertEqual(_quote_amounts(quote(unit_price=10.0)),(10.0,0.5,1.0,11.5))

    def test_optional_military_discount_excludes_shipping(self):
        q=quote(unit_price=20,quantity=2,shipping=10,military_discount=True,apply_taxes=False)
        self.assertEqual(_quote_military_discount(q),2.0)
        self.assertEqual(_quote_amounts(q),(48.0,0.0,0.0,48.0))

    def test_no_tax_when_quote_not_marked_taxable(self):
        self.assertEqual(_quote_amounts(quote(apply_taxes=False)),(100.0,0.0,0.0,100.0))

    def test_exact_square_link_must_match_current_total(self):
        q=quote(apply_taxes=False,square_link_url="https://square.link/u/FJORD-TEST",
                square_link_amount_cents=10000)
        self.assertEqual(_active_square_url(q),"https://square.link/u/FJORD-TEST")
        q["quantity"]=2
        self.assertIsNone(_active_square_url(q))

    def test_stripe_and_square_allowlist_and_no_url_credentials(self):
        for url,provider in (("https://square.link/u/valid","Square"),
                             ("https://checkout.square.site/merchant/abc","Square"),
                             ("https://buy.stripe.com/test_checkout","Stripe")):
            self.assertEqual(_payment_link_provider(url),provider)
        for bad in ("http://square.link/u/valid","https://square.link.evil.test/u/a",
                    "https://user:password@square.link/u/a",
                    "https://evil.test/payment", "javascript:alert(1)",
                    "https://square.link/u/abc#fragment"):
            self.assertIsNone(_square_checkout_url(bad))

    def test_acceptance_hash_invalidated_when_price_changes(self):
        q=quote()
        before=_quote_acceptance_digest(q)
        q["unit_price"]=101.0
        self.assertNotEqual(before,_quote_acceptance_digest(q))

if __name__=="__main__":
    unittest.main(verbosity=2)
