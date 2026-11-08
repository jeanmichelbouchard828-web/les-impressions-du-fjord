"""Read-only print-system capabilities plus a tiny, disposable FFF preview slice.

A POST to /api/slice/real runs only a generic PrusaSlicer geometry preview:
no order, payment, database mutation, Bambu command or printer connection.
"""
import json
import os
import struct
import urllib.error
import urllib.request
import uuid
BASE=os.environ.get("FJORD_TEST_BASE","https://fjord-render-apercu-20261104.onrender.com").rstrip("/")

def cube_stl(size=9.0):
    p=[(0,0,0),(size,0,0),(size,size,0),(0,size,0),
       (0,0,size),(size,0,size),(size,size,size),(0,size,size)]
    triangles=[
        (0,2,1),(0,3,2),(4,5,6),(4,6,7),
        (0,1,5),(0,5,4),(1,2,6),(1,6,5),
        (2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    raw=b"FJORD-TEST-NON-PRINTABLE"+bytes(80-24)+struct.pack("<I",len(triangles))
    for t in triangles:
        raw+=struct.pack("<3f",0,0,1)
        for index in t:
            raw+=struct.pack("<3f",*p[index])
        raw+=struct.pack("<H",0)
    return raw

def multipart(fields,filedata):
    marker="fjord-test-"+uuid.uuid4().hex
    parts=[]
    for key,value in fields.items():
        parts.append(("--"+marker+"\r\nContent-Disposition: form-data; name=\""+key+"\"\r\n\r\n"+value+"\r\n").encode())
    parts.append(("--"+marker+"\r\nContent-Disposition: form-data; name=\"stl\"; filename=\"fjord-ci-cube.stl\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()+filedata+b"\r\n")
    parts.append(("--"+marker+"--\r\n").encode())
    return b"".join(parts),"multipart/form-data; boundary="+marker

payload,mime=multipart({"material":"PETG","layer_height":"0.2"},cube_stl())
req=urllib.request.Request(BASE+"/api/slice/real",data=payload,headers={"Content-Type":mime,"Accept":"application/json","User-Agent":"Fjord-Preview-Safe-Test/1.0"})
try:
    with urllib.request.urlopen(req,timeout=145) as response:
        code=response.status
        response_data=response.read()
except urllib.error.HTTPError as ex:
    code=ex.code
    response_data=ex.read()
try:
    result=json.loads(response_data)
except (ValueError,TypeError):
    raise AssertionError("Non-JSON slice response, HTTP "+str(code))
print("Slice response",json.dumps({
  "status":code,"error":result.get("error"),"detail":str(result.get("detail",""))[:450],
  "engine":result.get("engine"),"layer_count":result.get("layer_count"),
  "extrusion_moves":result.get("extrusion_moves"),
  "not_printer_ready":result.get("not_printer_ready")},ensure_ascii=False))
assert code==200, "Real preview slice failed with HTTP "+str(code)
assert result.get("not_printer_ready") is True
assert result.get("layer_count",0)>0
assert result.get("extrusion_moves",0)>0
print("PASS generic PrusaSlicer preview with real generated toolpaths; not X2D print-ready")
