import unittest
from fjord_gallery_pairing import model_stem,photo_stems,unique_photo_match

class PairTests(unittest.TestCase):
 def test_accents_and_explicit_angles(self):
  items=[{"name":"Support mural","filename":"support_mural.3mf"},
         {"name":"Loquet 2026","filename":"loquet-2026.stl"}]
  self.assertEqual(unique_photo_match("support_mural_photo_2.jpeg",items),items[0])
  self.assertEqual(unique_photo_match("Support mural.png",items),items[0])
  self.assertEqual(unique_photo_match("loquet 2026.webp",items),items[1])
  self.assertEqual(model_stem("Réparation pièce-Élite.3mf"),"reparation-piece-elite")
 def test_refuses_ambiguous_or_unknown(self):
  a={"name":"Support","filename":"support.stl"}
  b={"name":"Support","filename":"support.3mf"}
  self.assertIsNone(unique_photo_match("support.jpg",[a,b]))
  self.assertIsNone(unique_photo_match("support_vue_1.jpg",[a,b]))
  self.assertIsNone(unique_photo_match("unrelated.jpg",[a]))
  self.assertIsNone(unique_photo_match("support_2.jpg",[a]))
 def test_prefers_exact_over_view_suffix(self):
  a={"name":"Panel","filename":"panel.stl"}
  b={"name":"Panel photo 1","filename":"panel_photo_1.stl"}
  self.assertEqual(unique_photo_match("panel_photo_1.jpg",[a,b]),b)

if __name__=="__main__":unittest.main(verbosity=2)
