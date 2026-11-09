"""Match photo/model pairs by clear, unique filename identities.

This is never visual inference or reverse-engineering a photo into STL.
Ambiguous names are deliberately not linked; operators choose explicitly.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import PurePath

PHOTO_SUFFIX = re.compile(r"(?:[-_ ](?:photo|image|img|vue|angle|render|preview)(?:[-_ ]?\\d{1,2})?)$",re.I)

def model_stem(name):
    name=unicodedata.normalize("NFKD",str(name or ""))
    name="".join(c for c in name if not unicodedata.combining(c))
    base=PurePath(name.replace("\\","/")).name.rsplit(".",1)[0]
    return re.sub(r"[^a-z0-9]+","-",base.casefold()).strip("-")

def photo_stems(filename):
    path=PurePath(str(filename or "").replace("\\","/")).name
    base=path.rsplit(".",1)[0]
    candidates=[base]
    simpler=PHOTO_SUFFIX.sub("",base)
    if simpler and simpler!=base:candidates.append(simpler)
    normalized=[]
    for item in candidates:
        value=model_stem(item)
        if value and value not in normalized:normalized.append(value)
    return normalized

def unique_photo_match(filename,candidates):
    """Return the only matching candidate, otherwise None."""
    values=list(candidates)
    for stem in photo_stems(filename):
        matched=[row for row in values if stem in
                 (model_stem(row.get("name")),model_stem(row.get("filename")))]
        if len(matched)==1:return matched[0]
        if len(matched)>1:return None
    return None
