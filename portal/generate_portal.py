#!/usr/bin/env python3
"""
BAKEDBYSARVANI PORTFOLIO PORTAL GENERATOR
Generates a public, SEO-friendly single-page portfolio site.

Tabs: Gallery | Reviews | Order
Static HTML content generated at build time (crawlable, no JS required for content).
JS used only for tab switching and category filtering.

Usage:
    python3 generate_portal.py            # Generate + open in browser
    python3 generate_portal.py --no-open  # Generate only

Data sources:
    gallery_manifest.json  — gallery card data (title, category, url, cover)
    ../reviews.json        — customer reviews (auto-deduplicated)
    .secret                — optional WhatsApp number (line 1)

Security (public site):
    - No encryption (public business portfolio)
    - CSP with nonce-based script-src
    - URL allowlist validation
    - html.escape() on all untrusted text
    - rel="noreferrer noopener" on external links
    - No secrets in generated HTML (except opted-in WhatsApp number)
"""

import html
import json
import os
import sys
import base64
import webbrowser
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "index.html"
MANIFEST_FILE = SCRIPT_DIR / "gallery_manifest.json"
GALLERY_IMAGES_FILE = SCRIPT_DIR / "gallery_images_curated.json"
REVIEWS_FILE = SCRIPT_DIR.parent / "reviews.json"
SECRET_FILE = SCRIPT_DIR / ".secret"

# Allowed URL hosts for external links
ALLOWED_HOSTS = [
    "www.rsquarestudios.com",
    "rsquarestudios.com",
    "photos.smugmug.com",
    "www.instagram.com",
    "instagram.com",
    "wa.me",
    "bakedbysarvani-reviews.netlify.app",
    "lambent-melomakarona-126439.netlify.app",
    "kneil31.github.io",
    "bakedbysarvani.rsquarestudios.com",
]

REVIEW_FORM_URL = "https://bakedbysarvani-reviews.netlify.app"
INSTAGRAM_URL = "https://www.instagram.com/bakedbysarvani/"


def is_allowed_url(url: str) -> bool:
    """Validate URL against allowed hosts."""
    if not url:
        return False
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        return any(
            parsed.hostname == h or (parsed.hostname and parsed.hostname.endswith("." + h))
            for h in ALLOWED_HOSTS
        )
    except Exception:
        return False


def safe_url(url: str) -> str:
    """Return URL if allowed, else '#'."""
    return html.escape(url, quote=True) if is_allowed_url(url) else "#"


def load_gallery_manifest() -> list:
    """Load gallery entries from manifest. Only include entries with a URL."""
    if not MANIFEST_FILE.exists():
        print(f"  WARNING: {MANIFEST_FILE} not found — Gallery tab will be empty")
        return []
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)
    # Only include entries that have a valid URL
    valid = [e for e in entries if e.get("url")]
    skipped = len(entries) - len(valid)
    if skipped:
        print(f"  Skipped {skipped} entries without URLs")
    return valid


def load_gallery_images() -> list:
    """Load inline gallery images from gallery_images.json."""
    if not GALLERY_IMAGES_FILE.exists():
        print(f"  WARNING: {GALLERY_IMAGES_FILE} not found — no inline photos")
        return []
    with open(GALLERY_IMAGES_FILE, "r", encoding="utf-8") as f:
        images = json.load(f)
    valid = [img for img in images if img.get("thumb") and is_allowed_url(img["thumb"])]
    return valid


def load_reviews() -> list:
    """Load and deduplicate reviews from reviews.json."""
    if not REVIEWS_FILE.exists():
        print(f"  WARNING: {REVIEWS_FILE} not found — Reviews tab will be empty")
        return []
    with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Deduplicate by normalized (customer_name, review_text)
    seen = set()
    unique = []
    for r in raw:
        name = r.get("customer_name", "").strip()
        text = r.get("review_text", "").strip()
        # Normalize: remove escaped characters for dedup comparison
        norm_text = text.replace("\\!", "!").replace("\\?", "?").replace("\n", " ").strip()
        key = (name.lower(), norm_text.lower())
        if key not in seen:
            seen.add(key)
            unique.append({
                "name": name,
                "rating": r.get("rating", 5),
                "text": text.replace("\\!", "!").replace("\\?", "?"),
                "date": r.get("date", ""),
            })
    # Sort by date descending (newest first)
    unique.sort(key=lambda x: x.get("date", ""), reverse=True)
    return unique


def get_whatsapp_number() -> str:
    """Read WhatsApp number from .secret file (first line)."""
    if SECRET_FILE.exists():
        lines = SECRET_FILE.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            return lines[0].strip()
    return ""


def compute_review_stats(reviews: list) -> tuple:
    """Return (count, average_rating) from deduped reviews."""
    if not reviews:
        return 0, 0.0
    total = sum(r["rating"] for r in reviews)
    avg = total / len(reviews)
    return len(reviews), avg


def build_star_html(rating: int) -> str:
    """Build gold star rating HTML."""
    filled = min(rating, 5)
    empty = 5 - filled
    stars = '<span class="stars">'
    stars += '<span class="star-filled">' + ("&#9733;" * filled) + "</span>"
    if empty:
        stars += '<span class="star-empty">' + ("&#9734;" * empty) + "</span>"
    stars += "</span>"
    return stars


def build_gallery_card_html(entry: dict) -> str:
    """Build a single gallery tile as static HTML."""
    title = html.escape(entry.get("title", ""), quote=True)
    desc = html.escape(entry.get("description", ""), quote=True)
    category = html.escape(entry.get("category", ""), quote=True)
    icon = html.escape(entry.get("icon", ""), quote=True)
    url = safe_url(entry.get("url", ""))
    cover = entry.get("cover", "")

    has_cover = bool(cover and is_allowed_url(cover))
    cover_escaped = html.escape(cover, quote=True) if has_cover else ""

    if has_cover:
        style = f' style="background-image: url(\'{cover_escaped}\')"'
        cls = "tile"
    else:
        style = ""
        cls = "tile tile-no-image"

    icon_html = ""
    if not has_cover and icon:
        icon_html = f'<div class="tile-icon">{icon}</div>'

    return f"""<a href="{url}" class="{cls}" data-category="{category}" target="_blank" rel="noreferrer noopener"{style}>
      {icon_html}
      <div class="tile-content">
        <div class="tile-title">{title}</div>
        <div class="tile-meta">{desc}</div>
      </div>
    </a>"""


def build_review_card_html(review: dict) -> str:
    """Build a single review card as static HTML."""
    name = html.escape(review["name"], quote=True)
    text = html.escape(review["text"], quote=True)
    stars = build_star_html(review["rating"])
    return f"""<div class="review-card">
      <div class="review-text">&ldquo;{text}&rdquo;</div>
      {stars}
      <div class="review-author">&mdash; {name}</div>
    </div>"""


def generate_html(galleries: list, reviews: list, whatsapp: str, gallery_images: list = None) -> str:
    """Generate the complete HTML page."""
    now = datetime.now().strftime("%B %d, %Y")
    csp_nonce = base64.b64encode(os.urandom(16)).decode("ascii")
    gallery_images = gallery_images or []

    # ── Build phone-feed gallery HTML ──
    # Pattern: featured (full-width) → pair (2-col) → pair → featured → ...
    # This creates visual rhythm on a phone screen
    photo_grid_html = ""
    if gallery_images:
        i = 0
        row_type = 0  # 0=featured, 1=pair, 2=pair
        while i < len(gallery_images):
            if row_type == 0:
                # Featured — single large image
                img = gallery_images[i]
                thumb = html.escape(img["thumb"], quote=True)
                full = html.escape(img.get("url", img["thumb"]), quote=True)
                photo_grid_html += f'<div class="feed-featured" data-full="{full}"><img src="{thumb}" alt="Cake by Sarvani" loading="lazy" referrerpolicy="no-referrer"></div>\n        '
                i += 1
                row_type = 1
            else:
                # Pair — two side by side
                pair_html = '<div class="feed-pair">\n'
                for _ in range(2):
                    if i < len(gallery_images):
                        img = gallery_images[i]
                        thumb = html.escape(img["thumb"], quote=True)
                        full = html.escape(img.get("url", img["thumb"]), quote=True)
                        pair_html += f'          <div class="feed-pair-item" data-full="{full}"><img src="{thumb}" alt="Cake by Sarvani" loading="lazy" referrerpolicy="no-referrer"></div>\n'
                        i += 1
                pair_html += '        </div>\n        '
                photo_grid_html += pair_html
                if row_type == 2:
                    row_type = 0  # back to featured
                else:
                    row_type = 2
    else:
        photo_grid_html = '<div class="empty-state">Gallery coming soon</div>'

    # ── Build gallery cards HTML (category tiles — only if no inline images) ──
    gallery_cards_html = ""
    filter_pills_html = ""

    # ── Build review cards HTML ──
    review_count, review_avg = compute_review_stats(reviews)
    review_avg_display = f"{review_avg:.1f}" if review_avg else "0"

    review_cards_html = ""
    if reviews:
        for r in reviews:
            review_cards_html += build_review_card_html(r) + "\n        "
    else:
        review_cards_html = '<div class="empty-state">No reviews yet</div>'

    # ── Build order section HTML ──
    whatsapp_btn = ""
    if whatsapp:
        wa_url = f"https://wa.me/{html.escape(whatsapp, quote=True)}"
        if is_allowed_url(wa_url):
            whatsapp_btn = f"""<a href="{wa_url}" class="order-btn order-btn-whatsapp" target="_blank" rel="noreferrer noopener">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.611.611l4.458-1.495A11.948 11.948 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.35 0-4.514-.81-6.228-2.164l-.435-.347-3.012 1.01 1.01-3.012-.348-.436A9.948 9.948 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z"/></svg>
          Message on WhatsApp
        </a>"""

    # ── Allowed hosts JS array for URL validation ──
    hosts_js = json.dumps(ALLOWED_HOSTS)

    # ── JS block (minimal — tab switching + category filter only) ──
    js_block = f"""
    // Frame-buster
    if (top !== self) {{ top.location = self.location; }}

    // Tab switching
    document.querySelectorAll('.tab-btn[data-tab]').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.tab-content').forEach(function(el) {{ el.classList.remove('active'); }});
        document.querySelectorAll('.tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
        document.getElementById('tab-' + btn.getAttribute('data-tab')).classList.add('active');
        btn.classList.add('active');
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }});
    }});

    // Lightbox
    var lbItems = document.querySelectorAll('[data-full]');
    var lbBox = document.getElementById('lightbox');
    var lbImg = document.getElementById('lb-img');
    var lbIdx = 0;
    var lbUrls = [];
    lbItems.forEach(function(item, i) {{
      lbUrls.push(item.getAttribute('data-full'));
      item.addEventListener('click', function() {{
        lbIdx = i;
        lbImg.src = lbUrls[lbIdx];
        lbBox.style.display = 'flex';
        document.body.style.overflow = 'hidden';
      }});
    }});
    document.querySelector('.lb-close').addEventListener('click', function() {{
      lbBox.style.display = 'none';
      document.body.style.overflow = '';
    }});
    document.querySelector('.lb-prev').addEventListener('click', function() {{
      lbIdx = (lbIdx - 1 + lbUrls.length) % lbUrls.length;
      lbImg.src = lbUrls[lbIdx];
    }});
    document.querySelector('.lb-next').addEventListener('click', function() {{
      lbIdx = (lbIdx + 1) % lbUrls.length;
      lbImg.src = lbUrls[lbIdx];
    }});
    lbBox.addEventListener('click', function(e) {{
      if (e.target === lbBox) {{ lbBox.style.display = 'none'; document.body.style.overflow = ''; }}
    }});
    document.addEventListener('keydown', function(e) {{
      if (lbBox.style.display === 'none') return;
      if (e.key === 'Escape') {{ lbBox.style.display = 'none'; document.body.style.overflow = ''; }}
      if (e.key === 'ArrowLeft') {{ lbIdx = (lbIdx - 1 + lbUrls.length) % lbUrls.length; lbImg.src = lbUrls[lbIdx]; }}
      if (e.key === 'ArrowRight') {{ lbIdx = (lbIdx + 1) % lbUrls.length; lbImg.src = lbUrls[lbIdx]; }}
    }});
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>Baked By Sarvani — Homemade Cakes in Dallas</title>
  <meta name="description" content="Homemade custom cakes in Dallas, TX. Freshly baked for birthdays, baby showers, weddings, and celebrations. Made with love by Sarvani.">
  <meta property="og:title" content="Baked By Sarvani">
  <meta property="og:description" content="Homemade custom cakes, freshly baked in Dallas with love.">
  <meta property="og:type" content="website">
  <meta name="theme-color" content="#FFF9F7">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Permissions-Policy" content="camera=(), microphone=(), geolocation=()">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-{csp_nonce}'; style-src 'unsafe-inline'; img-src 'self' https://*.smugmug.com data:; connect-src 'none'; font-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none';">
  <style>
    *, *::before, *::after {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    :root {{
      /* ── Home Baker Palette ── */
      /* Warm blush & rose — personal, cozy, handmade feel */
      --font-title: Georgia, 'Times New Roman', serif;
      --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      --bg: #FFF9F7;
      --bg-warm: #FFF1ED;
      --bg-card: #FFFFFF;
      --text: #3D2B2B;
      --text-secondary: #8C7373;
      --text-light: #B39E9E;
      --accent: #D4847C;
      --accent-soft: #F5DDD9;
      --accent-deep: #B86B63;
      --rose: #E8A5A0;
      --rose-soft: #FDE8E6;
      --warm-gold: #C9A96E;
      --shadow: 0 2px 16px rgba(61, 43, 43, 0.06);
      --shadow-hover: 0 6px 24px rgba(61, 43, 43, 0.12);
      --radius: 20px;
      --radius-sm: 12px;
      --star-color: #C9A96E;
      --whatsapp: #25D366;
    }}

    body {{
      font-family: var(--font-body);
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }}

    /* ── Header — Personal, warm intro ────────────── */
    .header {{
      text-align: center;
      padding: 56px 24px 28px;
      background: linear-gradient(180deg, var(--bg-warm) 0%, var(--bg) 100%);
    }}

    .header-icon {{
      font-size: 48px;
      margin-bottom: 12px;
      line-height: 1;
    }}

    .header h1 {{
      font-family: var(--font-title);
      font-size: 36px;
      font-weight: 400;
      font-style: italic;
      color: var(--text);
      margin-bottom: 8px;
      letter-spacing: 0.3px;
    }}

    .header .subtitle {{
      font-size: 15px;
      color: var(--text-secondary);
      font-weight: 400;
      line-height: 1.5;
      max-width: 300px;
      margin: 0 auto;
    }}

    .header .location-tag {{
      display: inline-block;
      margin-top: 14px;
      padding: 6px 14px;
      background: var(--bg-card);
      border-radius: 50px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-light);
      letter-spacing: 0.5px;
      box-shadow: var(--shadow);
    }}

    /* ── Tabs ──────────────────────────────────────── */
    .tabs {{
      display: flex;
      justify-content: center;
      gap: 6px;
      padding: 0 20px 20px;
      position: sticky;
      top: 0;
      z-index: 100;
      background: var(--bg);
      padding-top: 12px;
    }}

    .tab-btn {{
      padding: 10px 22px;
      border: 1.5px solid transparent;
      border-radius: 50px;
      font-family: var(--font-body);
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.25s ease;
      background: var(--bg-card);
      color: var(--text-secondary);
      box-shadow: var(--shadow);
    }}

    .tab-btn.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
      box-shadow: 0 4px 16px rgba(212, 132, 124, 0.3);
    }}

    .tab-btn:not(.active):hover {{
      border-color: var(--accent-soft);
      color: var(--text);
    }}

    /* ── Tab Content ──────────────────────────────── */
    .tab-content {{
      display: none;
      padding: 0 16px 100px;
      max-width: 600px;
      margin: 0 auto;
      animation: fadeIn 0.35s ease;
    }}

    .tab-content.active {{
      display: block;
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── Filter Pills ─────────────────────────────── */
    .filter-bar {{
      display: flex;
      gap: 6px;
      padding: 4px 0 16px;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }}

    .filter-bar::-webkit-scrollbar {{
      display: none;
    }}

    .filter-pill {{
      padding: 7px 14px;
      border: 1.5px solid var(--accent-soft);
      border-radius: 50px;
      background: var(--bg-card);
      color: var(--text-secondary);
      font-family: var(--font-body);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }}

    .filter-pill.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}

    .filter-pill:not(.active):hover {{
      border-color: var(--rose);
      color: var(--text);
    }}

    /* ── Gallery Grid ─────────────────────────────── */
    .gallery-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 14px;
    }}

    .tile {{
      position: relative;
      border-radius: var(--radius);
      overflow: hidden;
      aspect-ratio: 4/5;
      display: flex;
      align-items: flex-end;
      background-size: cover;
      background-position: center;
      text-decoration: none;
      color: #fff;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}

    .tile::before {{
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, transparent 50%, rgba(0,0,0,0.65) 100%);
      z-index: 0;
    }}

    .tile:hover {{
      transform: translateY(-4px);
      box-shadow: var(--shadow-hover);
    }}

    .tile-content {{
      position: relative;
      z-index: 1;
      padding: 16px;
      width: 100%;
    }}

    .tile-title {{
      font-family: var(--font-title);
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      text-shadow: 0 1px 6px rgba(0,0,0,0.5);
      line-height: 1.3;
      margin-bottom: 2px;
    }}

    .tile-meta {{
      font-size: 12px;
      color: rgba(255,255,255,0.8);
      text-shadow: 0 1px 3px rgba(0,0,0,0.4);
    }}

    .tile-icon {{
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -60%);
      font-size: 44px;
      z-index: 1;
    }}

    .tile-no-image {{
      background: linear-gradient(145deg, var(--bg-warm) 0%, var(--accent-soft) 100%);
    }}

    .tile-no-image::before {{
      background: none;
    }}

    .tile-no-image .tile-title {{
      color: var(--text);
      text-shadow: none;
    }}

    .tile-no-image .tile-meta {{
      color: var(--text-secondary);
      text-shadow: none;
    }}

    .empty-state {{
      text-align: center;
      padding: 60px 20px;
      color: var(--text-light);
      font-size: 16px;
      font-style: italic;
    }}

    /* ── Feed Layout — alternating featured + pair ── */
    .feed {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding-top: 8px;
    }}

    .feed-featured {{
      width: 100%;
      aspect-ratio: 4/5;
      border-radius: var(--radius);
      overflow: hidden;
      cursor: pointer;
      box-shadow: var(--shadow);
    }}

    .feed-featured img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.4s ease;
    }}

    .feed-featured:hover img {{
      transform: scale(1.03);
    }}

    .feed-pair {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}

    .feed-pair-item {{
      aspect-ratio: 1/1;
      border-radius: var(--radius);
      overflow: hidden;
      cursor: pointer;
      box-shadow: var(--shadow);
    }}

    .feed-pair-item img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.4s ease;
    }}

    .feed-pair-item:hover img {{
      transform: scale(1.03);
    }}

    /* ── Lightbox ──────────────────────────────────── */
    .lightbox {{
      position: fixed;
      inset: 0;
      z-index: 1000;
      background: rgba(0, 0, 0, 0.95);
      display: flex;
      align-items: center;
      justify-content: center;
      animation: lbFadeIn 0.2s ease;
    }}

    @keyframes lbFadeIn {{
      from {{ opacity: 0; }}
      to {{ opacity: 1; }}
    }}

    .lb-img {{
      max-width: 92vw;
      max-height: 88vh;
      object-fit: contain;
      border-radius: 4px;
      user-select: none;
    }}

    .lb-close {{
      position: absolute;
      top: 16px;
      right: 20px;
      background: none;
      border: none;
      color: #fff;
      font-size: 36px;
      cursor: pointer;
      z-index: 1001;
      padding: 8px;
      line-height: 1;
      opacity: 0.7;
      transition: opacity 0.2s;
    }}

    .lb-close:hover {{ opacity: 1; }}

    .lb-prev, .lb-next {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      background: rgba(255,255,255,0.1);
      border: none;
      color: #fff;
      font-size: 32px;
      cursor: pointer;
      z-index: 1001;
      padding: 16px 12px;
      border-radius: 50%;
      line-height: 1;
      opacity: 0.6;
      transition: opacity 0.2s, background 0.2s;
    }}

    .lb-prev {{ left: 12px; }}
    .lb-next {{ right: 12px; }}
    .lb-prev:hover, .lb-next:hover {{ opacity: 1; background: rgba(255,255,255,0.2); }}

    @media (max-width: 480px) {{
      .lb-prev, .lb-next {{ padding: 12px 8px; font-size: 24px; }}
      .lb-close {{ font-size: 28px; top: 10px; right: 14px; }}
    }}

    /* ── Review Cards — like a friend's recommendation ── */
    .reviews-header {{
      text-align: center;
      padding: 20px 0 28px;
    }}

    .reviews-header h2 {{
      font-family: var(--font-title);
      font-size: 24px;
      font-weight: 400;
      font-style: italic;
      color: var(--text);
      margin-bottom: 8px;
    }}

    .reviews-summary {{
      font-size: 14px;
      color: var(--text-secondary);
      font-weight: 500;
    }}

    .reviews-summary .stars {{
      color: var(--star-color);
      font-size: 18px;
    }}

    .review-card {{
      background: var(--bg-card);
      border-radius: var(--radius);
      padding: 24px 24px 20px;
      margin-bottom: 14px;
      border-left: 3px solid var(--rose);
      box-shadow: var(--shadow);
      transition: box-shadow 0.2s;
    }}

    .review-card:hover {{
      box-shadow: var(--shadow-hover);
    }}

    .review-text {{
      font-family: var(--font-title);
      font-style: italic;
      font-size: 15px;
      line-height: 1.7;
      color: var(--text);
      margin-bottom: 14px;
    }}

    .review-card .stars {{
      color: var(--star-color);
      font-size: 15px;
    }}

    .star-filled {{
      color: var(--star-color);
    }}

    .star-empty {{
      color: var(--accent-soft);
    }}

    .review-author {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text-light);
      margin-top: 4px;
    }}

    .review-cta {{
      text-align: center;
      padding: 28px 0 0;
    }}

    .review-cta a {{
      display: inline-block;
      padding: 12px 28px;
      border: 2px solid var(--accent);
      border-radius: 50px;
      color: var(--accent);
      font-family: var(--font-body);
      font-size: 14px;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s;
    }}

    .review-cta a:hover {{
      background: var(--accent);
      color: #fff;
    }}

    /* ── Order Section — personal, friendly ────────── */
    .order-intro {{
      text-align: center;
      padding: 24px 16px 8px;
    }}

    .order-intro h2 {{
      font-family: var(--font-title);
      font-size: 26px;
      font-weight: 400;
      font-style: italic;
      color: var(--text);
      margin-bottom: 10px;
    }}

    .order-intro p {{
      font-size: 15px;
      color: var(--text-secondary);
      line-height: 1.6;
      max-width: 340px;
      margin: 0 auto;
    }}

    .order-steps {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      padding: 24px 0;
    }}

    .order-step {{
      background: var(--bg-card);
      border-radius: var(--radius);
      padding: 22px 16px 18px;
      text-align: center;
      box-shadow: var(--shadow);
    }}

    .order-step-num {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--rose-soft);
      color: var(--accent-deep);
      font-weight: 700;
      font-size: 15px;
      margin-bottom: 10px;
    }}

    .order-step-title {{
      font-weight: 700;
      font-size: 14px;
      color: var(--text);
      margin-bottom: 4px;
    }}

    .order-step-desc {{
      font-size: 12px;
      color: var(--text-secondary);
      line-height: 1.5;
    }}

    .order-buttons {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 8px 0 24px;
    }}

    .order-btn {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 16px 24px;
      border-radius: 50px;
      font-family: var(--font-body);
      font-size: 15px;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.2s;
      color: #fff;
    }}

    .order-btn:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    }}

    .order-btn-instagram {{
      background: linear-gradient(135deg, #833AB4 0%, #E1306C 50%, #F77737 100%);
    }}

    .order-btn-whatsapp {{
      background: var(--whatsapp);
    }}

    .order-note {{
      text-align: center;
      padding: 12px 20px 0;
      font-size: 13px;
      color: var(--text-light);
      line-height: 1.5;
    }}

    .order-location {{
      text-align: center;
      padding: 20px 0 0;
      font-size: 13px;
      color: var(--text-light);
      font-weight: 500;
    }}

    /* ── Footer ────────────────────────────────────── */
    .footer {{
      text-align: center;
      padding: 36px 20px 40px;
      color: var(--text-light);
      font-size: 13px;
      font-weight: 400;
    }}

    .footer a {{
      color: var(--accent);
      text-decoration: none;
    }}

    .footer a:hover {{
      text-decoration: underline;
    }}

    .footer .tagline {{
      font-family: var(--font-title);
      font-style: italic;
      font-size: 15px;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }}

    .footer .credit {{
      font-size: 11px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: var(--text-light);
      font-weight: 500;
    }}

    .footer .gen-date {{
      margin-top: 8px;
      font-size: 10px;
      opacity: 0.4;
    }}

    /* ── Small mobile ──────────────────────────────── */
    @media (max-width: 374px) {{
      .gallery-grid {{
        grid-template-columns: 1fr;
      }}
      .tile {{
        aspect-ratio: 4/3;
      }}
      .order-steps {{
        grid-template-columns: 1fr;
      }}
      .header h1 {{
        font-size: 28px;
      }}
    }}

    /* ── Desktop ───────────────────────────────────── */
    @media (min-width: 768px) {{
      .header {{
        padding: 72px 24px 36px;
      }}
      .header h1 {{
        font-size: 44px;
      }}
      .tab-btn {{
        padding: 12px 28px;
        font-size: 15px;
      }}
      .gallery-grid {{
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
      }}
      .tile-title {{
        font-size: 17px;
      }}
      .tab-content {{
        max-width: 700px;
      }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="header-icon">\U0001f382</div>
    <h1>Baked by Sarvani</h1>
    <p class="subtitle">We bake cakes for events and parties! Homemade with love in Dallas.</p>
    <span class="location-tag">Dallas, TX</span>
  </div>

  <div class="tabs">
    <button class="tab-btn active" data-tab="gallery">Gallery</button>
    <button class="tab-btn" data-tab="reviews">Reviews</button>
    <button class="tab-btn" data-tab="order">Order</button>
  </div>

  <!-- ── Gallery Tab ── -->
  <div id="tab-gallery" class="tab-content active">
    <div class="feed">
      {photo_grid_html}
    </div>
  </div>

  <!-- Lightbox -->
  <div id="lightbox" class="lightbox" style="display:none">
    <button class="lb-close" aria-label="Close">&times;</button>
    <button class="lb-prev" aria-label="Previous">&#8249;</button>
    <button class="lb-next" aria-label="Next">&#8250;</button>
    <img id="lb-img" class="lb-img" alt="Cake by Sarvani">
  </div>

  <!-- ── Reviews Tab ── -->
  <div id="tab-reviews" class="tab-content">
    <div class="reviews-header">
      <h2>Kind words from happy customers</h2>
      <p class="reviews-summary">
        {build_star_html(round(review_avg))} {review_avg_display}/5 from {review_count} reviews
      </p>
    </div>
    <div class="reviews-list">
      {review_cards_html}
    </div>
    <div class="review-cta">
      <a href="{html.escape(REVIEW_FORM_URL, quote=True)}" target="_blank" rel="noreferrer noopener">Loved your cake? Leave a review</a>
    </div>
  </div>

  <!-- ── Order Tab ── -->
  <div id="tab-order" class="tab-content">
    <div class="order-intro">
      <h2>Let's make your cake</h2>
      <p>Every cake is baked fresh to order. Just tell me what you're celebrating and I'll take it from there.</p>
    </div>

    <div class="order-steps">
      <div class="order-step">
        <div class="order-step-num">1</div>
        <div class="order-step-title">Send a message</div>
        <div class="order-step-desc">DM me on Instagram or WhatsApp</div>
      </div>
      <div class="order-step">
        <div class="order-step-num">2</div>
        <div class="order-step-title">Share your idea</div>
        <div class="order-step-desc">Theme, flavors, size, and when you need it</div>
      </div>
      <div class="order-step">
        <div class="order-step-num">3</div>
        <div class="order-step-title">Get a quote</div>
        <div class="order-step-desc">I'll share pricing and confirm details</div>
      </div>
      <div class="order-step">
        <div class="order-step-num">4</div>
        <div class="order-step-title">Pick up &amp; enjoy</div>
        <div class="order-step-desc">Fresh, beautiful, and ready to celebrate</div>
      </div>
    </div>

    <div class="order-buttons">
      <a href="{html.escape(INSTAGRAM_URL, quote=True)}" class="order-btn order-btn-instagram" target="_blank" rel="noreferrer noopener">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
        DM me on Instagram
      </a>
      {whatsapp_btn}
    </div>

    <p class="order-note">Pickup in Dallas. I typically need 2-3 days notice for custom designs.</p>

    <div class="order-location">
      Serving Dallas-Fort Worth, TX
    </div>
  </div>

  <div class="footer">
    <p class="tagline">Baked with love, one cake at a time</p>
    <p class="credit">@bakedbysarvani &middot; @rsquare_studios</p>
    <p class="gen-date">Generated {now}</p>
  </div>

  <script nonce="{csp_nonce}">{js_block}</script>
</body>
</html>"""


def main():
    print("Generating BakedBySarvani Portal")
    print("=" * 40)

    print("\nLoading gallery manifest...")
    galleries = load_gallery_manifest()
    print(f"  {len(galleries)} gallery entries with URLs")

    print("\nLoading gallery images...")
    gallery_images = load_gallery_images()
    print(f"  {len(gallery_images)} inline photos")

    print("\nLoading reviews...")
    reviews = load_reviews()
    review_count, review_avg = compute_review_stats(reviews)
    print(f"  {review_count} unique reviews (avg {review_avg:.2f})")

    whatsapp = get_whatsapp_number()
    if whatsapp:
        print(f"\nWhatsApp number loaded from .secret")
    else:
        print(f"\nNo WhatsApp number — Order tab will use Instagram DM only")

    print("\nGenerating HTML...")
    page_html = generate_html(galleries, reviews, whatsapp, gallery_images)

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"  Written to {OUTPUT_FILE}")
    print(f"  File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")

    if "--no-open" not in sys.argv:
        webbrowser.open(f"file://{OUTPUT_FILE.resolve()}")
        print("\nDone! Opening in browser...")
    else:
        print("\nDone!")


if __name__ == "__main__":
    main()
