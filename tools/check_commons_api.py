"""Diagnostic Wikimedia metadata query for licensed inspiration thumbnails."""
import json,urllib.parse,urllib.request,urllib.error,time
params={"action":"query","generator":"categorymembers",
"gcmtitle":"Category:3D printed objects","gcmtype":"file","gcmlimit":"3",
"prop":"imageinfo","iiprop":"url|extmetadata","iiurlwidth":"480",
"format":"json","formatversion":"2"}
url="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode(params)
request=urllib.request.Request(url,headers={"User-Agent":"Fjord3DInspiration/1.0 (https://fjord-render-apercu-20261104.onrender.com; contact via site)"})
try:
 with urllib.request.urlopen(request,timeout=24) as response:
  raw=response.read()
  print("HTTP",response.status,"response bytes",len(raw))
  doc=json.loads(raw)
  for entry in doc.get("query",{}).get("pages",[]):
   info=entry.get("imageinfo",[{}])[0]
   meta=info.get("extmetadata",{})
   print(json.dumps({"title":entry.get("title"),"thumburl":info.get("thumburl"),"license":meta.get("LicenseShortName",{}).get("value"),"artist":meta.get("Artist",{}).get("value"),"attribution":meta.get("AttributionRequired",{}).get("value")},ensure_ascii=False)[:1900])
except Exception as exc:
 print("WIKIMEDIA_ERROR",type(exc).__name__,str(exc))
 raise
