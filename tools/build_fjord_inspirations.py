"""Build a stable, attributed list of ~50 Commons 3D inspiration photos.

Only includes media with a verified Wikimedia Commons image URL, author and an
explicitly permitted commercial re-use license. Curated candidates are manually
chosen for practical diversity; no copyrighted 3D models are distributed.
Run in CI to update the checked-in manifest; the website has no API dependency.
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"fjord_inspirations_manifest.json"
RAW="""Animaux|Grenouille arboricole|Tree frog figurine|3D Red-Eyed Tree Frog.jpg
Animaux|Lapin stylisé|Stylized rabbit|3D printed cartoon rabbit.JPG
Animaux|Éléphant miniature|Miniature elephant|Impression 3D d'un elephant (1).JPG
Animaux|Pieuvre décorative|Decorative octopus|Octopus! (5841817489).jpg
Animaux|Petit cochon|Little pig|3d printed Piggy..webp
Animaux|Chat imprimé en 3D|3D printed cat|3d printed Cat.jpg
Animaux|Chien imprimé en 3D|3D printed dog|3d Printed Dog.jpg
Animaux|Lion décoratif|Decorative lion|3D PRINTED LION FACE.jpg
Animaux|Écureuil imprimé en 3D|3D printed squirrel|BEEVERYCREATIVE BEETHEFIRST 3D-prints a squirrel - 13964774176.jpg
Animaux|Lapin géométrique|Geometric bunny|Low Poly Stanford Bunny.jpg
Animaux|Abeille multicolore|Multicolour bee|The BEEVERYCREATIVE BEE as multi-colour 3D-print.jpg
Objets utiles|Clé de serrage imprimée|3D printed wrench|Fully assembled 3D printable wrench.jpg
Objets utiles|Poignée de remplacement|Replacement handle|3D printed Handle.jpg
Objets utiles|Guide pour outil de défonceuse|Router guide adapter|3D printed router template adaptor.jpg
Objets utiles|Ouvre-bouteille|Bottle opener|Bottle Opener (5849549547).jpg
Objets utiles|Cadran solaire|Digital sundial|Digital Sundial - photo 2 2 preview featured.jpg
Objets utiles|Anneau de ventilation|Ventilation ring|3D printed Vent Ring.jpg
Objets utiles|Petite roue|Small wheel|3-D printed wheel.JPG
Objets utiles|Support de tubes|Tube rack|3D printed 4x3 test tube rack.jpg
Objets utiles|Embout de pied de meuble|Furniture leg end cap|3D printed table leg tip.jpg
Objets utiles|Support pour ruban adhésif|Tape dispenser insert|3D printed tape dispenser cores.jpg
Objets utiles|Pare-soleil pour appareil photo|Camera lens hood|3D printed lens hood Tamron Minolta A-mount 17-35mm F2.8-4.jpg
Objets utiles|Bouton de commande|Replacement knob|3d printed Knob.webp
Objets utiles|Sifflet de berger|Shepherd's whistle|3-D-printed shepherd's whistle.jpg
Objets utiles|Adaptateur de gabarit|Template follower adapter|3D printed adaptor with template follower.jpg
Objets utiles|Filtre de cafetière|Coffee press|Coffee press - printed object.jpg
Objets utiles|Petit embout technique|Technical nozzle|3D printed snow machine nozzle.jpg
Maison & déco|Cache-pots|Decorative plant pots|3D printed flower pots.jpg
Maison & déco|Vase imprimé|3D printed vase|3D PRINTED VASE.jpg
Maison & déco|Bol décoratif|Decorative bowl|3D PRINTED BOWL.jpg
Maison & déco|Tasse créative|Creative cup|3D PRINTED MONKEY CUP.jpg
Maison & déco|Labyrinthe de table|Tabletop maze|3D PRINTED MAZE (10X10).jpg
Maison & déco|Porte-brosse à dents ajouré|Toothbrush holder|3D printed toothbrush holder.jpg
Maison & déco|Sphère Voronoï|Voronoi sphere|Voronoi Sphere.jpg
Maison & déco|Boule ajourée|Voronoi ball|Voronoi Ball.jpg
Maison & déco|Fleur décorative|Decorative flower|3-d printed flower model.jpg
Maison & déco|Étoile lumineuse de Noël|Light-up Christmas star|350 - Vega - The LED-lit Christmas Star (15943417585).jpg
Maison & déco|Cache-pot personnalisé|Custom planter|3D Printer flowerpot.jpg
Maison & déco|Structure alvéolée|Honeycomb form|3D PRINTED HEXAGONAL HONEYCOMB CORE STRUCTURE.jpg
Cadeaux & figurines|Dragon miniature|Mini dragon|Dragon print.jpg
Cadeaux & figurines|Jouet à propulsion élastique|Rubber-band toy|Kit Educativo - auto propulsado por bandas elásticas.jpg
Cadeaux & figurines|Ornements de Noël|Christmas ornaments|3D printed Christmas Ornaments at Deezmaker (8303586571).jpg
Cadeaux & figurines|Buste de Beethoven|Beethoven bust|3D printed Beethoven (9415625226).jpg
Cadeaux & figurines|Figurine égyptienne|Egyptian figurine|3D Printed Ancient Egyptian Figurine 1.png
Cadeaux & figurines|Livre décoratif|Decorative open book|3D printed open book 1.jpg
Cadeaux & figurines|Crâne de dinosaure|Dinosaur skull|3D printed Spinosaurus skulls.jpg
Cadeaux & figurines|Petit robot|Miniature robot|3D Printed Robot.jpg
Cadeaux & figurines|Figurine de fleur|Flower figurine|3-d printed flower model.jpg
Cadeaux & figurines|Sculpture de lion|Lion sculpture|3D printed Lion.jpg
Technique|Boîtier Raspberry Pi|Raspberry Pi enclosure|Raspberry Pi case.jpg
Technique|Boîtier ventilé|Ventilated electronics case|Raspberry with fan and case.jpg
Technique|Pièces de turbine|Turbine components|3D Printed Turbine Parts.png
Technique|Pièce de bobine|Spool hub adapter|3-D-printed NAB reel hub (16264562294).jpg
Technique|Connecteurs|Connector holders|IDC Connectors (5821886966).jpg
Technique|Pièce de prototype|Prototype part|3D Printed RFB cell frame printed on Prusa i3.jpg
Technique|Nid d'abeille technique|Honeycomb prototype|3D PRINTED HEXAGONAL HONEYCOMB CORE STRUCTURE.jpg
Technique|Boîtier électronique|Electronics box|Raspberry with case.jpg
Technique|Support de tube de laboratoire|Laboratory tube rack|3D printed 4x3 test tube drying rack.jpg
Bijoux & design|Bague topographique|Topographic ring|Rebeleer - The Wanderer - 3D printed Map pin ring.jpg
Bijoux & design|Bijoux imprimés|3D printed jewelry|Jewelry-3d-pringint.jpg
Bijoux & design|Bague noire|Black ring|Rebeleer - The Wanderer - 3D printed Map pin black nylon ring .jpg
Bijoux & design|Design de visage de lion|Lion face design|3D PRINTED LION FACE 2.jpg
Bijoux & design|Sphère géométrique|Geometric sphere|Voronoi Sphere.jpg
Bijoux & design|Structure de design|Decorative design|A Schematic Digital Material Representation.jpg
"""
QUOTAS={"Animaux":9,"Objets utiles":12,"Maison & déco":10,
        "Cadeaux & figurines":8,"Technique":7,"Bijoux & design":4}

class TextOnly(HTMLParser):
 def __init__(self):
  super().__init__();self.parts=[]
 def handle_data(self,data): self.parts.append(data)
 def result(self):
  return html.unescape(re.sub(r"\s+"," "," ".join(self.parts)).strip())

def clean_html(raw):
 parser=TextOnly()
 parser.feed(str(raw or ""))
 return parser.result()[:160]

def query_files(names):
 params={"action":"query","titles":"|".join("File:"+n for n in names),
   "prop":"imageinfo","iiprop":"url|extmetadata|size","iiurlwidth":"640",
   "format":"json","formatversion":"2"}
 url="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode(params)
 request=urllib.request.Request(url,headers={"User-Agent":
 "Fjord3DInspiration/1.2 (https://fjord-render-apercu-20261104.onrender.com; credits and commercial licensing audit)"})
 with urllib.request.urlopen(request,timeout=45) as response:
  return json.loads(response.read()).get("query",{}).get("pages",[])

def valid_license(value):
 value=value.strip()
 return bool(re.fullmatch(r"CC BY(?:-SA)? (?:2\.0|2\.5|3\.0|4\.0)",value)
     or value in {"CC0","CC0 1.0","Public domain"})

def main():
 items=[]
 for line in RAW.strip().splitlines():
  category,title,english,name=line.split("|",3)
  items.append({"category":category,"title":title,"english":english,"filename":name})
 by_title={}
 for start in range(0,len(items),14):
  pages=query_files([i["filename"] for i in items[start:start+14]])
  for page in pages:
   if "imageinfo" in page:
    by_title[page["title"].removeprefix("File:")]=page["imageinfo"][0]
  time.sleep(.25)
 selected=[];counts={key:0 for key in QUOTAS};skipped=[]
 used=set()
 for item in items:
  category=item["category"]
  if counts[category]>=QUOTAS[category]:continue
  name=item["filename"]
  if name.lower() in used:continue
  info=by_title.get(name)
  if not info:
   skipped.append((name,"missing Wikimedia file"));continue
  meta=info.get("extmetadata",{})
  lic=meta.get("LicenseShortName",{}).get("value","")
  artist=clean_html(meta.get("Artist",{}).get("value",""))
  license_url=meta.get("LicenseUrl",{}).get("value","")
  thumb=info.get("thumburl","")
  source=info.get("descriptionurl","")
  if not valid_license(lic):
   skipped.append((name,"license "+lic));continue
  if not artist or not source.startswith("https://commons.wikimedia.org/wiki/File:"):
   skipped.append((name,"missing attribution"));continue
  if not thumb.startswith("https://"):
   skipped.append((name,"missing HTTPS thumbnail"));continue
  if not license_url.startswith(("https://","http://")):
   license_url=source+"#Licensing"
  if license_url.startswith("http://"):
   license_url="https://"+license_url[7:]
  selected.append({"title":item["title"],"english":item["english"],
   "category":category,"filename":name,"image":thumb,
   "source":source,"author":artist,
   "license":lic,"license_url":license_url})
  counts[category]+=1
  used.add(name.lower())
 print("COUNTS",json.dumps(counts,ensure_ascii=False))
 print("SKIPPED",json.dumps(skipped,ensure_ascii=False))
 print("ACCEPTED",len(selected),"CURATED CANDIDATES",len(items))
 if len(selected)!=50 or sorted(counts.values())!=sorted(QUOTAS.values()):
  raise SystemExit("Insufficient distinct, reusable images; edit the shortlist before release")
 manifest={"source":"Wikimedia Commons official imageinfo + extmetadata",
 "description":"Examples by other authors; not Les Impressions du Fjord products or STL licenses.",
 "items":selected}
 DEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("PREVIEW_FIRST",json.dumps(selected[:3],ensure_ascii=False)[:4500])
 print("PREVIEW_LAST",json.dumps(selected[-2:],ensure_ascii=False)[:2500])
 print("OUTPUT",DEST,len(DEST.read_bytes()))

if __name__=="__main__":
 main()
