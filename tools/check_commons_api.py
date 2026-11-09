"""Check Wikimedia Commons file counts and licensing for printable inspiration categories."""
import json,urllib.parse,urllib.request,time
categories=[
"3D printed toys","3D printed tools","3D printed art","3D printed animals",
"3D printed jewelry","3D printed furniture","3D printed Raspberry Pi cases",
"Voronoi pattern shaped 3D printed objects","3D printed objects"]
for category in categories:
 params={"action":"query","generator":"categorymembers",
 "gcmtitle":"Category:"+category,"gcmtype":"file","gcmlimit":"90",
 "prop":"imageinfo","iiprop":"url|extmetadata","iiurlwidth":"480",
 "format":"json","formatversion":"2"}
 url="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode(params)
 request=urllib.request.Request(url,headers={"User-Agent":"Fjord3DInspiration/1.1 (https://fjord-render-apercu-20261104.onrender.com; contact via site)"})
 try:
  with urllib.request.urlopen(request,timeout=30) as response:
   doc=json.loads(response.read())
  pages=doc.get("query",{}).get("pages",[])
  good=[]
  for entry in pages:
   info=(entry.get("imageinfo") or [{}])[0]
   meta=info.get("extmetadata",{})
   lic=meta.get("LicenseShortName",{}).get("value","")
   if any(p in lic for p in ("CC BY","CC0","Public domain")) and info.get("thumburl") and entry.get("title","").lower().endswith((".jpg",".jpeg",".png",".webp")):
    good.append((entry["title"][5:],lic))
  print(json.dumps({"category":category,"pages":len(pages),"usable_license_photos":len(good),"sample":good[:23]},ensure_ascii=False))
 except Exception as error:
  print("ERROR",category,type(error).__name__,str(error)[:280])
 time.sleep(.35)
