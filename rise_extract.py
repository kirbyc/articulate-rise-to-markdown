#!/usr/bin/env python3
r"""
Rise Course Text Extractor v4.4

Extracts learner-visible text from an unzipped Articulate Rise export into:
  - course.md
  - extraction-report.json

v4.4 hotfix:
- Safely handles Rise fields that are dict/list objects instead of strings.
- This fixes crashes like: TypeError: can only concatenate str (not "dict") to str.

Usage:
  python rise_extract_v4_4.py "C:\path\to\unzipped\rise\export" -o out
"""
from __future__ import annotations

import argparse, base64, json, re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

PLACEHOLDERS = {
    "When we show up to the present moment with all of our senses, we invite the world to fill us with joy. The pains of the past are behind us. The future has yet to unfold. But the now is full of beauty simply waiting for our attention.",
    "Heading",
}
CONTENT_KEYS = {"title","description","heading","paragraph","text","label","quote","attribution","prompt","correct","incorrect","feedback","alt","altText","caption","buttonText","question","choice","transcript","subtitle","content","value","placeholder","html","srcdoc"}
NON_CONTENT_KEYS = {"id","type","family","variant","globalBlockId","blockumentId","l10nId","backgroundColor","backgroundType","cardMode","src","srcId","srcName","createdAt","updatedAt","tenantId","originalId","copyOf","shareId","sharePassword","reviewId","jobType","author","authorType","selectedAuthorId","color","rgb","fill","contentPrefix","courseId","key","crushedKey","thumbnail","course_id","version","player","processing","identifier","filename","format","target","targetName","navigationMode","sidebarMode","themeId","coverImageDefault","name"}
SKIP_DICT_KEYS = {"media","sandbox","storyline","meta","metadata","settings","theme","labelSet","labels","fonts","exportSettings","lmsOptions","style","styles"}
CODE_ARTIFACT_TERMS = {"tri","dia","sq","strip","confetti","tabindex","role","button","aria-label","aria-hidden","aria-expanded","aria-controls","class","id","div","span","svg","path","circle","rect","section","article","grid","card","cards","container","wrapper","active","inactive","true","false","null","undefined","onclick","keydown","keyup","click","open","closed","close","resize","load","img","item","p","row","fan","f","lit"}
IMAGE_EXTS={".jpg",".jpeg",".png",".gif",".svg",".webp"}; VIDEO_EXTS={".mp4",".mov",".webm"}; AUDIO_EXTS={".mp3",".wav",".m4a",".aac"}

L10N_LOOKUP: Dict[str, str] = {}
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def clean_text(x: Any) -> str:
    s = unescape("" if x is None else str(x))
    s = s.replace("\u202f"," ").replace("\xa0"," ").replace("\r\n","\n").replace("\r","\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    # For QA-bot input, remove markdown/emphasis markers that would be read literally.
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"(?<!\w)_(?!\w)|(?<!\w)\*(?!\w)", "", s)
    return s.strip()


def norm(x: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(x)).strip().lower()


def is_placeholder(x: Any) -> bool:
    n=norm(x)
    return not n or any(n == norm(p) for p in PLACEHOLDERS)



def raw_l10n_text(value: Any) -> str:
    """Extract likely strings from a localization table value without using L10N_LOOKUP."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return ""
    if isinstance(value, list):
        return "\n".join(t for t in (raw_l10n_text(v) for v in value) if t.strip())
    if isinstance(value, dict):
        parts = []
        preferred = ["html", "text", "value", "content", "description", "title", "label", "caption", "alt", "altText", "children", "items", "nodes", "blocks", "en", "en-US", "en_us", "default"]
        for k in preferred:
            if k in value and k not in {"id", "l10nId"}:
                t = raw_l10n_text(value.get(k))
                if t.strip():
                    parts.append(t)
        if parts:
            return "\n".join(parts)
        for k, v in value.items():
            if k in SKIP_DICT_KEYS or k in NON_CONTENT_KEYS or k == "l10nId":
                continue
            t = raw_l10n_text(v)
            if t.strip():
                parts.append(t)
        return "\n".join(parts)
    return ""


def build_l10n_lookup(data: Any) -> Dict[str, str]:
    """Build a best-effort lookup for Rise localization references.

    Newer Rise exports may replace visible strings with {'l10nId': '<uuid>'}
    and store the real English text elsewhere in runtime-data.js. This scans for
    dictionary keys that are UUIDs and for array entries with id/l10nId fields.
    """
    lookup: Dict[str, str] = {}

    def add(key: Any, val: Any):
        if not isinstance(key, str) or not UUID_RE.match(key):
            return
        txt = clean_text(raw_l10n_text(val))
        if txt and not is_placeholder(txt) and txt != key:
            # Prefer longer/more useful text if duplicates appear.
            if key not in lookup or len(txt) > len(lookup[key]):
                lookup[key] = txt

    def walk(node: Any):
        if isinstance(node, dict):
            for k, v in node.items():
                add(k, v)
            node_id = node.get("id") or node.get("l10nId")
            if isinstance(node_id, str) and UUID_RE.match(node_id):
                txt = clean_text(raw_l10n_text({k: v for k, v in node.items() if k not in {"id", "l10nId"}}))
                if txt and not is_placeholder(txt):
                    if node_id not in lookup or len(txt) > len(lookup[node_id]):
                        lookup[node_id] = txt
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return lookup


def resolve_l10n_ref(value: Any) -> str:
    if isinstance(value, dict) and "l10nId" in value:
        key = value.get("l10nId")
        if isinstance(key, str):
            return L10N_LOOKUP.get(key, "")
    return ""

def stringify_htmlish(value: Any) -> str:
    """Safely convert Rise HTML-ish/localized/rich-text values to a string.

    Some Rise exports store description/content fields as dicts or lists, even
    in English-only exports. html.parser and re.sub require strings, so all
    direct HTML parsing should pass through this function first.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            t = stringify_htmlish(item)
            if t.strip():
                parts.append(t)
        return "\n".join(parts)
    if isinstance(value, dict):
        resolved = resolve_l10n_ref(value)
        if resolved:
            return resolved
        # If this is only a localization pointer and we cannot resolve it, do not
        # expose {'l10nId': '...'} as learner-facing text.
        if set(value.keys()).issubset({"l10nId"}):
            return ""
        parts = []

        # Prefer common Rise, localization, and rich-text wrapper keys.
        preferred_keys = [
            "html", "srcdoc", "text", "value", "content", "description", "title", "label", "caption", "alt", "altText",
            "en", "en-US", "en_us", "en-US-x-mtfrom-en", "default", "original", "localized", "translation",
            "children", "items", "blocks", "nodes",
        ]
        for key in preferred_keys:
            if key in value:
                t = stringify_htmlish(value.get(key))
                if t.strip():
                    parts.append(t)

        # Tiptap / ProseMirror text node: {"type":"text", "text":"..."}
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            parts.append(value["text"])

        if parts:
            return "\n".join(parts)

        # Last-resort walk, avoiding obvious runtime/system fields.
        for key, item in value.items():
            if key in SKIP_DICT_KEYS or key in NON_CONTENT_KEYS:
                continue
            t = stringify_htmlish(item)
            if t.strip():
                parts.append(t)
        return "\n".join(parts)
    return str(value)


def is_probably_content(x: Any) -> bool:
    s=clean_text(x); n=norm(s)
    if not s or is_placeholder(s) or n in CODE_ARTIFACT_TERMS:
        return False
    if sum(c.isalpha() for c in s)==0:
        return False
    if re.fullmatch(r"[A-Za-z0-9_-]{18,}",s) or re.fullmatch(r"[0-9a-fA-F-]{24,}",s):
        return False
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}",s):
        return False
    if re.match(r"^(https?:)?//",s):
        return False
    if re.search(r"\.(js|css|woff2?|png|jpe?g|gif|svg|webp|mp4|html?)$",s,re.I):
        return False
    alpha=sum(c.isalpha() for c in s)
    if len(s)>20 and alpha/max(len(s),1)<0.25:
        return False
    return True


def dedupe(items: Iterable[Any]) -> List[str]:
    out=[]; seen:set[str]=set()
    for i in items:
        s=clean_text(i)
        if not is_probably_content(s):
            continue
        k=norm(s)
        if k not in seen:
            seen.add(k); out.append(s)
    return out


def looks_like_html(s: Any) -> bool:
    s = stringify_htmlish(s)
    return bool(re.search(r"<\s*/?\s*[a-zA-Z][\w:-]*(\s|>|/)", s or ""))


class HtmlTextParser(HTMLParser):
    BLOCKS={"p","div","li","h1","h2","h3","h4","h5","h6","br","tr","section","article"}
    SKIP={"style","template","svg","canvas"}

    def __init__(self,capture_scripts=False):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.scripts=[]; self.skip=0; self.script=0; self.capture=capture_scripts

    def handle_starttag(self,tag,attrs):
        tag=tag.lower(); attrs=dict(attrs or [])
        style=attrs.get("style","").replace(" ","").lower()
        if attrs.get("aria-hidden","").lower()=="true" or "display:none" in style:
            self.skip+=1; return
        if tag=="script":
            self.script+=1; return
        if tag in self.SKIP:
            self.skip+=1; return
        if self.skip:
            return
        if tag=="li": self.parts.append("\n")
        elif tag in {"h1","h2","h3","h4","h5","h6"}: self.parts.append("\n")
        elif tag=="br": self.parts.append("\n")
        elif tag in {"strong","b","em","i"}: pass
        elif tag in self.BLOCKS: self.parts.append("\n")
        if tag=="img" and is_probably_content(attrs.get("alt","")):
            self.parts.append("\n"+attrs["alt"]+"\n")

    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag=="script":
            self.script=max(0,self.script-1); return
        if tag in self.SKIP or self.skip:
            self.skip=max(0,self.skip-1); return
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self,data):
        if self.script:
            if self.capture: self.scripts.append(data)
            return
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return clean_text("".join(self.parts))


def decode_js_string(raw: str) -> str:
    if "\\" not in raw:
        return raw
    try: return bytes(raw,"utf-8").decode("unicode_escape")
    except Exception: return raw


def string_literal_context(script: str, start: int, end: int) -> Tuple[str,str]:
    return script[max(0,start-120):start].lower(), script[end:min(len(script),end+120)].lower()


def is_code_context_string(s: str, before: str, after: str) -> bool:
    n=norm(s); stripped=s.strip()
    if n in CODE_ARTIFACT_TERMS: return True
    if stripped.startswith((".","#")): return True
    if re.fullmatch(r"-?\d+(px|deg|s|ms|rem|em|vh|vw|%)", stripped, re.I): return True
    if re.fullmatch(r"(px|deg|s|ms|rem|em|vh|vw|%)", stripped, re.I): return True
    if re.search(r"\b(rotate|translate|scale|skew|matrix)\s*\(", stripped, re.I): return True
    if re.fullmatch(r"[.#]?[a-z0-9_-]+(\s+[a-z0-9_-]+){0,3}", stripped) and stripped.lower()==stripped:
        if len(stripped.split()) <= 4: return True

    context = before[-25:] + " " + after[:25]
    code_markers = [
        "class=", "classlist", "classname", "queryselector", "queryselectorall", "getelementbyid", "getelementsby",
        "addeventlistener", "removeeventlistener", ".style", "style.", "setattribute", "removeattribute", "dataset",
        "localstorage", "sessionstorage", "matchmedia", "requestanimationframe", "innerhtml +=", "innerhtml=",
        "insertadjacenthtml", "createelement", "appendchild", "document.", "window.", "e.key", "event.key", ".key",
        "keydown", "keyup", "keypress", "toggle(", "contains(", "preventdefault", "stoppropagation",
    ]
    if any(m in context for m in code_markers):
        if re.search(r"[.#{};=<>]|\b(px|deg|ms)\b", stripped, re.I): return True
        if n in {"enter","escape","tab","space","arrowup","arrowdown","arrowleft","arrowright"}: return True
    return False


def extract_script_strings(script: Any) -> List[str]:
    script = stringify_htmlish(script)
    out=[]
    for m in re.finditer(r"(?<!\\)(['\"`])((?:\\.|(?!\1).)*?)\1", script or "", re.S):
        quote, raw=m.group(1), m.group(2)
        if quote=="`" and "${" in raw:
            continue
        s=clean_text(decode_js_string(raw)); n=norm(s)
        if not s or n in CODE_ARTIFACT_TERMS:
            continue
        before, after = string_literal_context(script, m.start(), m.end())
        if is_code_context_string(s, before, after):
            continue
        if looks_like_html(s):
            v,_=html_to_text(s,False)
            if is_probably_content(v): out.append(v)
            continue
        if "<" in s or ">" in s:
            continue
        if re.search(r"[{};=]",s) and len(s)>15:
            continue
        if is_probably_content(s): out.append(s)
    return dedupe(out)


def html_to_text(html: Any, include_script_strings=True) -> Tuple[str,List[str]]:
    html = stringify_htmlish(html)
    p=HtmlTextParser(include_script_strings)
    try:
        p.feed(html or "")
    except Exception:
        return clean_text(re.sub(r"<[^>]+>"," ",html or "")), []
    scripts=[]
    if include_script_strings:
        for sc in p.scripts:
            scripts.extend(extract_script_strings(sc))
    return p.text(), dedupe(scripts)


JSONP_RE=re.compile(r'__jsonp\(\s*"runtime-data\.js"\s*,\s*"(.*)"\s*\)\s*;?\s*$',re.S)
GLOBAL_RE=re.compile(r"globalProvideData\(\s*'([^']+)'\s*,\s*'(.*)'\s*\)\s*;?\s*$",re.S)


def find_runtime_data(root: Path) -> Optional[Path]:
    if root.is_file() and root.name=="runtime-data.js": return root
    found=list(root.rglob("runtime-data.js")); found.sort(key=lambda p:(len(p.parts),str(p)))
    return found[0] if found else None


def decode_runtime_data(path: Path) -> Dict[str,Any]:
    raw=path.read_text(encoding="utf-8-sig",errors="replace")
    m=JSONP_RE.search(raw.strip())
    return json.loads(base64.b64decode(m.group(1)).decode("utf-8",errors="replace")) if m else json.loads(raw)


def unescape_storyline_js(s: str) -> str:
    return re.sub(r"\\\\",r"\\",s).replace("\\'","'")


def load_global(js: Path) -> Optional[Any]:
    raw=js.read_text(encoding="utf-8-sig",errors="replace")
    m=GLOBAL_RE.search(raw.strip())
    return json.loads(unescape_storyline_js(m.group(2))) if m else None


def extract_storyline_text_runs(node: Any, out: List[str]):
    if isinstance(node,dict):
        if isinstance(node.get("text"),str): out.append(node["text"])
        for v in node.values(): extract_storyline_text_runs(v,out)
    elif isinstance(node,list):
        for v in node: extract_storyline_text_runs(v,out)


def resolve_storyline_dir(content_root: Path, prefix: str) -> Optional[Path]:
    prefix=(prefix or "").replace("\\","/")
    prefixes=[prefix]
    if prefix.endswith("/story.html"): prefixes.append(prefix.rsplit("/",1)[0])
    if "/" in prefix: prefixes.append(prefix.split("/",1)[0])
    roots=[content_root/"assets",content_root,content_root.parent/"content"/"assets",content_root.parent/"assets"]
    for pref in dict.fromkeys(prefixes):
        for root in roots:
            c=root/pref
            if c.is_file(): c=c.parent
            if c.is_dir(): return c
    export_root=content_root.parent if content_root.name.lower()=="content" else content_root
    last=prefixes[-1]
    matches=[p for p in export_root.rglob(last) if p.is_dir()]
    return matches[0] if matches else None


def clean_storyline_runs(runs: List[str]) -> List[str]:
    texts=[]
    for r in runs:
        t=html_to_text(r,False)[0] if looks_like_html(r) else clean_text(r)
        if not is_probably_content(t): continue
        words=re.findall(r"[A-Za-z0-9]+",t)
        if len(words)<=1 and not re.search(r"[.!?:]$",t) and t[:1].islower(): continue
        texts.append(t)
    return dedupe(texts)


def extract_storyline_block(story_dir: Path, report: Dict[str,Any]) -> Optional[str]:
    data_js=story_dir/"html5"/"data"/"js"/"data.js"
    if not data_js.exists():
        report["storyline_blocks"].append({"path":str(story_dir),"status":"missing html5/data/js/data.js"}); return None
    try: data=load_global(data_js)
    except Exception as e:
        report["storyline_blocks"].append({"path":str(story_dir),"status":f"failed to parse data.js: {e}"}); return None
    if not data:
        report["storyline_blocks"].append({"path":str(story_dir),"status":"empty data.js"}); return None
    slides=[]
    for scene in data.get("scenes",[]) if isinstance(data,dict) else []:
        if scene.get("isMessageScene"): continue
        slides.extend(scene.get("slides",[]) or [])
    slide_dir=story_dir/"html5"/"data"/"js"; lines=[]; missing=[]; parsed=0
    for slide in slides:
        sid=slide.get("id")
        if not sid: continue
        sj=slide_dir/f"{sid}.js"
        if not sj.exists(): missing.append(sid); continue
        try: sd=load_global(sj)
        except Exception: missing.append(sid); continue
        runs=[]; extract_storyline_text_runs(sd,runs); texts=clean_storyline_runs(runs)
        if texts: lines.extend(texts); lines.append(""); parsed+=1
    report["storyline_blocks"].append({"path":str(story_dir),"status":"extracted" if lines else "no text found","slides_total":len(slides),"slides_parsed":parsed,"slides_unparsed":missing})
    return "\n".join(lines).strip() if lines else None


def extract_tiptap(node: Any, out: List[str]):
    if isinstance(node,dict):
        if node.get("type")=="text" and isinstance(node.get("text"),str): out.append(node["text"])
        for v in node.values(): extract_tiptap(v,out)
    elif isinstance(node,list):
        for v in node: extract_tiptap(v,out)


def extract_mondrian(course: Dict[str,Any], bid: str, report: Dict[str,Any]) -> Optional[str]:
    mond=course.get("mondrian") or {}; b=(mond.get("blockuments") or {}).get(bid); items=mond.get("items") or {}
    if not b:
        report["custom_blocks"].append({"blockumentId":bid,"status":"missing blockument"}); return None
    ordered=[]
    def walk(iid):
        it=items.get(iid) or {}
        if not it or it.get("removed"): return
        ordered.append(iid)
        for ch in sorted(it.get("children") or [],key=lambda c:c.get("visualOrder",0)):
            if ch.get("id"): walk(ch["id"])
    for ch in sorted(b.get("children") or [],key=lambda c:c.get("visualOrder",0)):
        if ch.get("id"): walk(ch["id"])
    texts=[]
    for iid in ordered:
        for st in ((items.get(iid) or {}).get("states") or {}).values():
            if not isinstance(st,dict): continue
            if is_probably_content(st.get("altText","")): texts.append(st["altText"])
            to=st.get("text")
            if isinstance(to,dict) and to.get("json"): extract_tiptap(to["json"],texts)
    texts=dedupe(texts)
    report["custom_blocks"].append({"blockumentId":bid,"title":b.get("title"),"status":"extracted" if texts else "no text found","text_count":len(texts)})
    return "\n".join(texts) if texts else None


def resolve_sandbox(content_root: Path, src: str) -> Optional[Path]:
    for root in [content_root/"assets",content_root,content_root.parent/"content"/"assets",content_root.parent/"assets"]:
        p=root/src
        if p.is_dir(): return p
    export_root=content_root.parent if content_root.name.lower()=="content" else content_root
    found=[p for p in export_root.rglob(src) if p.is_dir()]
    return found[0] if found else None


def extract_html_file(path: Path, report: Dict[str,Any]) -> List[str]:
    try: html=path.read_text(encoding="utf-8-sig",errors="replace")
    except Exception as e:
        report["html_blocks"].append({"path":str(path),"status":f"read failed: {e}"}); return []
    visible,scripts=html_to_text(html,True); texts=dedupe([visible]+scripts)
    report["html_blocks"].append({"path":str(path),"status":"extracted" if texts else "no text found","text_count":len(texts)})
    return texts


def extract_sandbox_code(content_root: Path, sandbox: Dict[str,Any], report: Dict[str,Any]) -> Optional[str]:
    src=sandbox.get("src") or ""; name=sandbox.get("srcName") or "uploaded code block"; folder=resolve_sandbox(content_root,src)
    if not folder:
        report["html_blocks"].append({"src":src,"srcName":name,"status":"asset folder not found"}); return None
    htmls=[]
    if (folder/"index.html").exists(): htmls.append(folder/"index.html")
    htmls += [p for p in sorted(folder.rglob("*.html")) if p not in htmls and "node_modules" not in p.parts]
    if not htmls:
        report["html_blocks"].append({"src":src,"srcName":name,"path":str(folder),"status":"no html files found"}); return None
    texts=[]
    for h in htmls: texts.extend(extract_html_file(h,report))
    texts=dedupe(texts)
    return "\n".join(texts) if texts else None


def extract_inline_code(srcdoc: Any, report: Dict[str,Any]) -> Optional[str]:
    visible,scripts=html_to_text(srcdoc,True); texts=dedupe([visible]+scripts)
    report["html_blocks"].append({"kind":"inline srcdoc","status":"extracted" if texts else "no text found","text_count":len(texts)})
    return "\n".join(texts) if texts else None


def extract_generic(v: Any, out: List[str], key=""):
    if isinstance(v,str):
        if key in NON_CONTENT_KEYS: return
        if looks_like_html(v):
            t=html_to_text(v,False)[0]
            if is_probably_content(t): out.append(t)
        elif key in CONTENT_KEYS and is_probably_content(v): out.append(v)
    elif isinstance(v,dict):
        # If the dict itself is a content/localization wrapper, stringify it as a unit first.
        if key in CONTENT_KEYS:
            t=html_to_text(v,False)[0]
            if is_probably_content(t): out.append(t)
            return
        for k,val in v.items():
            if k in SKIP_DICT_KEYS: continue
            extract_generic(val,out,k)
    elif isinstance(v,list):
        for val in v: extract_generic(val,out,key)


def native_block_text(block: Dict[str,Any]) -> List[str]:
    out=[]; safe={k:v for k,v in block.items() if k not in {"settings","media","style","background"}}
    extract_generic(safe,out); return dedupe(out)


def parse_vtt(p: Path) -> str:
    cues=[]; buf=[]
    for line in p.read_text(encoding="utf-8-sig",errors="replace").splitlines():
        line=line.strip()
        if not line:
            if buf: cues.append(" ".join(buf)); buf=[]
            continue
        if line.upper().startswith("WEBVTT") or "-->" in line or re.match(r"^\d+$",line): continue
        buf.append(re.sub(r"<[^>]+>","",line))
    if buf: cues.append(" ".join(buf))
    return clean_text(" ".join(dedupe(cues)))


def scan_media(content_root: Path, report: Dict[str,Any]):
    assets=content_root/"assets"
    if not assets.exists(): return
    for p in sorted(assets.rglob("*.vtt")): report["captions_transcripts"].append({"file":str(p),"text":parse_vtt(p)})
    for p in sorted(assets.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS|VIDEO_EXTS|AUDIO_EXTS:
            report["media_assets"].append({"file":str(p),"type":p.suffix.lower().lstrip('.'),"status":"binary media - no OCR/transcription attempted"})


def content_root_from(runtime: Path) -> Path:
    return runtime.parent if runtime.parent.name.lower()=="content" else (runtime.parent/"content" if (runtime.parent/"content").exists() else runtime.parent)


def get_block_label(block: Dict[str, Any]) -> str:
    if block.get("blockumentId"):
        return "Custom Block"
    for item in block.get("items") or []:
        if not isinstance(item, dict): continue
        storyline = ((item.get("media") or {}).get("storyline") or {})
        if storyline: return "Embedded Storyline"
        if item.get("srcdoc"): return "Code Block"
        sandbox = ((item.get("media") or {}).get("sandbox") or {})
        if sandbox: return "Code Block"
    return "Native Rise Content"


def build_md(data: Dict[str,Any], content_root: Path, report: Dict[str,Any]) -> str:
    course=data.get("course") or {}
    course_title = clean_text(stringify_htmlish(course.get('title')) or 'Untitled Course')
    md=[f"# {course_title}"]
    if course.get("description"):
        t=html_to_text(course.get("description"),False)[0]
        if is_probably_content(t): md += ["",t]
    for li,lesson in enumerate(course.get("lessons") or [],1):
        lesson_title = clean_text(stringify_htmlish(lesson.get('title')) or f'Lesson {li}')
        md += ["",f"## {lesson_title}" ]
        if lesson.get("description"):
            t=html_to_text(lesson.get("description"),False)[0]
            if is_probably_content(t): md += ["",t]
        for bi,block in enumerate(lesson.get("items") or [],1):
            md += ["",f"### Block {bi} [{get_block_label(block)}]"]
            md.extend(native_block_text(block))
            btype,family=block.get("type"),block.get("family")
            if btype=="html" or family=="html":
                for item in block.get("items") or []:
                    if not isinstance(item,dict): continue
                    if item.get("srcdoc"):
                        x=extract_inline_code(item.get("srcdoc"),report)
                        if x: md += ["",x]
                    sandbox=((item.get("media") or {}).get("sandbox") or {})
                    if sandbox:
                        x=extract_sandbox_code(content_root,sandbox,report)
                        if x: md += ["",x]
            for item in block.get("items") or []:
                if not isinstance(item,dict): continue
                sl=((item.get("media") or {}).get("storyline") or {})
                if sl:
                    story_dir=resolve_storyline_dir(content_root, sl.get("contentPrefix") or sl.get("src") or "")
                    if story_dir:
                        x=extract_storyline_block(story_dir,report)
                        if x: md += ["",x]
                    else:
                        report["storyline_blocks"].append({"contentPrefix": sl.get("contentPrefix") or sl.get("src") or "", "status":"storyline folder not found"})
            if btype=="custom" or family=="mondrian" or block.get("blockumentId"):
                bid=block.get("blockumentId")
                if bid:
                    x=extract_mondrian(course,bid,report)
                    if x: md += ["",x]
    if report.get("captions_transcripts"):
        md += ["","## Appendix: Captions & Transcripts"]
        for t in report["captions_transcripts"]:
            if t.get("text"): md += ["",f"{t['file']}",t["text"]]
    final=[]; prev=None
    for line in md:
        if is_placeholder(line): continue
        n=norm(line)
        if n and n==prev and not line.startswith("#"): continue
        final.append(line)
        if n: prev=n
    return clean_text("\n\n".join(final))+"\n"


def main():
    ap=argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export_path"); ap.add_argument("-o","--output-dir",default="rise_extract_out")
    a=ap.parse_args(); root=Path(a.export_path).expanduser().resolve(); runtime=find_runtime_data(root)
    if not runtime: raise SystemExit(f"Could not find runtime-data.js under: {root}")
    content_root=content_root_from(runtime)
    report={"runtime_data":str(runtime),"content_root":str(content_root),"custom_blocks":[],"html_blocks":[],"storyline_blocks":[],"captions_transcripts":[],"media_assets":[],"warnings":[]}
    data=decode_runtime_data(runtime)
    global L10N_LOOKUP
    L10N_LOOKUP = build_l10n_lookup(data)
    report["localization_refs_resolved"] = len(L10N_LOOKUP)
    scan_media(content_root,report); md=build_md(data,content_root,report)
    out=Path(a.output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    (out/"course.md").write_text(md,encoding="utf-8")
    (out/"extraction-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Wrote: {out/'course.md'}")
    print(f"Wrote: {out/'extraction-report.json'}")

if __name__=="__main__": main()
