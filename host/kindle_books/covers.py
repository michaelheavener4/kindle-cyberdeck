"""Keep good embedded covers, retrieve matching art, or compose a custom cover."""
import hashlib
from functools import lru_cache
import io
import json
from pathlib import Path
import re
import subprocess
import unicodedata
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

Image.MAX_IMAGE_PIXELS = 20_000_000
ASSET = Path(__file__).with_name("assets") / "fallback-cover.png"


def usable(path):
    try:
        with Image.open(path) as im:
            if im.width < 200 or im.height < 280 or im.width * im.height > 20_000_000:
                return False
            gray = im.convert("L")
            gray.thumbnail((160, 240))
            return ImageStat.Stat(gray).stddev[0] > 9 and gray.entropy() > 2
    except (OSError, ValueError, Image.DecompressionBombError):
        return False


def _tokens(value):
    return set(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold()))


def _request(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "CyberdeckBooks/1.0 (personal Kindle library)"})
    with urllib.request.urlopen(request, timeout=12) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Cover response is too large.")
    return data


def lookup(title, author, target):
    params = {"title": title, "limit": 5, "fields": "title,author_name,cover_i,key"}
    if author:
        params["author"] = author
    try:
        data = json.loads(_request("https://openlibrary.org/search.json?" + urllib.parse.urlencode(params), 500_000))
    except (OSError, ValueError):
        return None
    requested = _tokens(title) - {"the", "a", "an", "and", "of"}
    author_tokens = _tokens(author)
    for book in data.get("docs", []):
        cover_id = book.get("cover_i")
        if not isinstance(cover_id, int) or cover_id <= 0:
            continue
        matched = _tokens(book.get("title", ""))
        if len(requested & matched) / max(1, len(requested)) < 0.8:
            continue
        if author_tokens and not author_tokens.intersection(_tokens(" ".join(book.get("author_name", [])))):
            continue
        url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false"
        try:
            content = _request(url, 8 * 1024 * 1024)
            with Image.open(io.BytesIO(content)) as im:
                im.convert("RGB").save(target, "JPEG", quality=94)
            if usable(target):
                return url
        except (OSError, ValueError, Image.DecompressionBombError):
            continue
    return None


@lru_cache(maxsize=2)
def _font_path(bold):
    family = "serif:style=Bold" if bold else "serif"
    return subprocess.check_output(["fc-match", "-f", "%{file}", family], text=True).strip()


def _font(size, bold=False):
    return ImageFont.truetype(_font_path(bold), size)


def _wrap(draw, text, font, width):
    lines = []
    current = ""
    for word in text.split():
        attempt = (current + " " + word).strip()
        if draw.textlength(attempt, font=font) <= width or not current:
            current = attempt
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def compose(title, author, target):
    # The generated art is immutable; each book gets a new typeset cover.
    with Image.open(ASSET) as artwork:
        canvas = ImageOps.fit(artwork.convert("RGB"), (1200, 1800))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 1220, 1200, 1800), fill="#f2ead8")
    draw.line((95, 1260, 1105, 1260), fill="#282b2a", width=3)
    title = " ".join(title.split())[:200]
    for size in range(88, 35, -2):
        font = _font(size, bold=True)
        lines = _wrap(draw, title, font, 1010)
        if len(lines) <= 3 and len(lines) * (size + 12) <= 330:
            break
    top = 1300 + max(0, (310 - len(lines) * (size + 12)) // 2)
    for line in lines[:3]:
        draw.text((600, top), line, font=font, fill="#202724", anchor="mt")
        top += size + 12
    author_font = _font(40)
    for i, line in enumerate(_wrap(draw, author[:150], author_font, 1010)[:2]):
        draw.text((600, 1660 + i * 48), line, font=author_font, fill="#34453a", anchor="mt")
    canvas.save(target, "JPEG", quality=95)


def ensure(source, title, author, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((str(source) + "\0" + title + "\0" + author).encode()).hexdigest()[:24]
    target = folder / (key + ".jpg")
    provenance = target.with_suffix(".json")
    if usable(target):
        return target
    result = subprocess.run(["ebook-meta", str(source), "--get-cover", str(target)],
                            capture_output=True, text=True, timeout=45)
    if result.returncode == 0 and usable(target):
        provenance.write_text(json.dumps({"source": "embedded"}))
        return target
    url = lookup(title, author, target)
    if url:
        provenance.write_text(json.dumps({"source": "Open Library", "url": url}))
        return target
    compose(title, author, target)
    if not usable(target):
        raise RuntimeError("Could not create a usable book cover.")
    provenance.write_text(json.dumps({"source": "custom cover", "artwork": ASSET.name}))
    return target
