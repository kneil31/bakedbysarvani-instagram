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

    # Deduplicate by normalized review text (catches same text with different names)
    import re
    seen_texts = set()
    unique = []
    for r in raw:
        name = r.get("customer_name", "").strip()
        text = r.get("review_text", "").strip()
        # Normalize: remove escaped chars, emoji codes, extra spaces
        norm_text = text.replace("\\!", "!").replace("\\?", "?").replace("\n", " ")
        norm_text = re.sub(r":[a-z_]+:", "", norm_text)  # remove :blush: etc
        norm_text = re.sub(r"\s+", " ", norm_text).strip().lower()
        if norm_text in seen_texts:
            continue
        seen_texts.add(norm_text)
        # Skip generic placeholder names
        if name.lower() in ("happy customer",):
            continue
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
  <meta name="theme-color" content="#FFFFFF">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Permissions-Policy" content="camera=(), microphone=(), geolocation=()">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-{csp_nonce}'; style-src 'unsafe-inline'; img-src 'self' https://*.smugmug.com data:; connect-src 'none'; font-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none';">
  <style>
    *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

    :root {{
      /* ── Honeybear-inspired: clean white, coral pink, bright & joyful ── */
      --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      --bg: #FFFFFF;
      --bg-soft: #FFF5F3;
      --text: #1A1A1A;
      --text-mid: #555555;
      --text-light: #999999;
      --pink: #E8636B;
      --pink-soft: #FDE8E9;
      --pink-deep: #D14B53;
      --coral: #F4978E;
      --gold: #D4A853;
      --green: #25D366;
      --shadow: 0 1px 8px rgba(0,0,0,0.06);
      --shadow-md: 0 4px 20px rgba(0,0,0,0.08);
      --radius: 12px;
    }}

    body {{ font-family: var(--font); background: var(--bg); color: var(--text); -webkit-font-smoothing: antialiased; }}

    /* ── Header — clean, bright, Honeybear style ──── */
    .header {{ text-align: center; padding: 60px 24px 32px; }}
    .header h1 {{ font-size: 32px; font-weight: 800; color: var(--text); letter-spacing: -0.5px; margin-bottom: 12px; }}
    .header h1 span {{ color: var(--pink); }}
    .header .tagline {{ font-size: 16px; color: var(--text-mid); font-weight: 400; line-height: 1.5; max-width: 320px; margin: 0 auto 16px; }}
    .header .loc {{ font-size: 12px; color: var(--text-light); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; }}

    /* ── Nav tabs — Honeybear-style clean pills ──── */
    .tabs {{ display: flex; justify-content: center; gap: 0; padding: 0 20px 24px; position: sticky; top: 0; z-index: 100; background: var(--bg); padding-top: 12px; }}
    .tab-btn {{
      padding: 12px 28px; border: none; background: none;
      font-family: var(--font); font-size: 15px; font-weight: 600;
      color: var(--text-light); cursor: pointer; transition: all 0.2s;
      border-bottom: 3px solid transparent; border-radius: 0;
    }}
    .tab-btn.active {{ color: var(--pink); border-bottom-color: var(--pink); }}
    .tab-btn:not(.active):hover {{ color: var(--text-mid); }}

    /* ── Content ──────────────────────────────────── */
    .tab-content {{ display: none; padding: 0 20px 80px; max-width: 560px; margin: 0 auto; animation: fadeIn 0.3s ease; }}
    .tab-content.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .empty-state {{ text-align: center; padding: 60px 20px; color: var(--text-light); font-size: 16px; }}

    /* ── Photo Feed — clean, airy, generous spacing ── */
    .feed {{ display: flex; flex-direction: column; gap: 16px; }}
    .feed-featured {{ width: 100%; aspect-ratio: 4/5; border-radius: var(--radius); overflow: hidden; cursor: pointer; }}
    .feed-featured img {{ width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.5s ease; }}
    .feed-featured:hover img {{ transform: scale(1.02); }}
    .feed-pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .feed-pair-item {{ aspect-ratio: 1/1; border-radius: var(--radius); overflow: hidden; cursor: pointer; }}
    .feed-pair-item img {{ width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.5s ease; }}
    .feed-pair-item:hover img {{ transform: scale(1.02); }}

    /* ── Lightbox ──────────────────────────────────── */
    .lightbox {{ position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; animation: lbIn 0.2s; }}
    @keyframes lbIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .lb-img {{ max-width: 94vw; max-height: 90vh; object-fit: contain; border-radius: 6px; user-select: none; }}
    .lb-close {{ position: absolute; top: 16px; right: 20px; background: none; border: none; color: #fff; font-size: 32px; cursor: pointer; z-index: 1001; opacity: 0.7; padding: 8px; }}
    .lb-close:hover {{ opacity: 1; }}
    .lb-prev, .lb-next {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.15); backdrop-filter: blur(4px); border: none; color: #fff; font-size: 28px; cursor: pointer; z-index: 1001; padding: 14px 10px; border-radius: 50%; opacity: 0.7; transition: all 0.2s; }}
    .lb-prev {{ left: 12px; }}
    .lb-next {{ right: 12px; }}
    .lb-prev:hover, .lb-next:hover {{ opacity: 1; background: rgba(255,255,255,0.25); }}

    /* ── Reviews — clean cards, pink accent ─────── */
    .section-title {{ font-size: 24px; font-weight: 800; color: var(--text); text-align: center; margin-bottom: 4px; }}
    .section-subtitle {{ font-size: 14px; color: var(--text-light); text-align: center; margin-bottom: 28px; }}
    .section-subtitle .stars {{ color: var(--gold); font-size: 16px; }}
    .star-filled {{ color: var(--gold); }}
    .star-empty {{ color: #E5E5E5; }}

    .review-card {{
      background: var(--bg-soft); border-radius: var(--radius);
      padding: 24px; margin-bottom: 12px; position: relative;
      transition: transform 0.2s;
    }}
    .review-card:hover {{ transform: translateY(-2px); }}
    .review-text {{ font-size: 15px; line-height: 1.7; color: var(--text); margin-bottom: 12px; }}
    .review-text::before {{ content: '\\201C'; font-size: 36px; color: var(--pink); font-weight: 700; line-height: 0; position: relative; top: 12px; margin-right: 4px; }}
    .review-card .stars {{ font-size: 14px; }}
    .review-author {{ font-size: 13px; font-weight: 700; color: var(--text-mid); margin-top: 4px; }}
    .review-cta {{ text-align: center; padding: 24px 0 0; }}
    .review-cta a {{
      display: inline-block; padding: 14px 32px;
      background: var(--pink); color: #fff; border: none; border-radius: 50px;
      font-size: 14px; font-weight: 700; text-decoration: none; transition: all 0.2s;
    }}
    .review-cta a:hover {{ background: var(--pink-deep); transform: translateY(-2px); box-shadow: 0 4px 16px rgba(232,99,107,0.3); }}

    /* ── Order — bright, action-oriented ──────────── */
    .order-header {{ text-align: center; padding: 8px 0 24px; }}
    .order-header h2 {{ font-size: 24px; font-weight: 800; color: var(--text); margin-bottom: 8px; }}
    .order-header p {{ font-size: 15px; color: var(--text-mid); line-height: 1.6; max-width: 320px; margin: 0 auto; }}

    .order-steps {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 24px; }}
    .order-step {{ background: var(--bg-soft); border-radius: var(--radius); padding: 20px 14px; text-align: center; }}
    .order-step-num {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 36px; height: 36px; border-radius: 50%;
      background: var(--pink); color: #fff; font-weight: 800; font-size: 14px; margin-bottom: 10px;
    }}
    .order-step-title {{ font-weight: 700; font-size: 14px; color: var(--text); margin-bottom: 4px; }}
    .order-step-desc {{ font-size: 12px; color: var(--text-light); line-height: 1.5; }}

    .order-buttons {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }}
    .order-btn {{
      display: flex; align-items: center; justify-content: center; gap: 10px;
      padding: 16px 24px; border-radius: 50px; font-family: var(--font);
      font-size: 15px; font-weight: 700; text-decoration: none; color: #fff; transition: all 0.2s;
    }}
    .order-btn:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.15); }}
    .order-btn-instagram {{ background: linear-gradient(135deg, #833AB4 0%, #E1306C 50%, #F77737 100%); }}
    .order-btn-whatsapp {{ background: var(--green); }}
    .order-note {{ text-align: center; font-size: 13px; color: var(--text-light); line-height: 1.5; padding: 8px 0; }}
    .order-location {{ text-align: center; font-size: 12px; color: var(--text-light); text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; padding: 12px 0; }}

    /* ── Footer ────────────────────────────────────── */
    .footer {{ text-align: center; padding: 40px 20px; border-top: 1px solid #F0F0F0; }}
    .footer .brand {{ font-size: 18px; font-weight: 800; color: var(--text); margin-bottom: 8px; }}
    .footer .brand span {{ color: var(--pink); }}
    .footer .links {{ font-size: 13px; color: var(--text-light); margin-bottom: 8px; }}
    .footer .links a {{ color: var(--pink); text-decoration: none; }}
    .footer .links a:hover {{ text-decoration: underline; }}
    .footer .copy {{ font-size: 11px; color: #CCC; }}

    /* ── Responsive ────────────────────────────────── */
    @media (max-width: 374px) {{
      .header h1 {{ font-size: 26px; }}
      .order-steps {{ grid-template-columns: 1fr; }}
      .feed-pair {{ gap: 8px; }}
    }}
    @media (min-width: 768px) {{
      .header {{ padding: 80px 24px 40px; }}
      .header h1 {{ font-size: 42px; }}
      .tab-content {{ max-width: 680px; }}
      .feed-pair {{ gap: 16px; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>We're <span>Baked by Sarvani</span></h1>
    <p class="tagline">Homemade custom cakes for birthdays, baby showers, weddings, and all your sweetest celebrations.</p>
    <p class="loc">Dallas, TX</p>
  </div>

  <div class="tabs">
    <button class="tab-btn active" data-tab="gallery">Our Cakes</button>
    <button class="tab-btn" data-tab="reviews">Reviews</button>
    <button class="tab-btn" data-tab="order">How to Order</button>
  </div>

  <div id="tab-gallery" class="tab-content active">
    <div class="feed">
      {photo_grid_html}
    </div>
  </div>

  <div id="lightbox" class="lightbox" style="display:none">
    <button class="lb-close" aria-label="Close">&times;</button>
    <button class="lb-prev" aria-label="Previous">&#8249;</button>
    <button class="lb-next" aria-label="Next">&#8250;</button>
    <img id="lb-img" class="lb-img" alt="Cake by Sarvani">
  </div>

  <div id="tab-reviews" class="tab-content">
    <h2 class="section-title">Cake Lovers</h2>
    <p class="section-subtitle">
      {build_star_html(round(review_avg))} {review_avg_display}/5 from {review_count} happy customers
    </p>
    <div class="reviews-list">
      {review_cards_html}
    </div>
    <div class="review-cta">
      <a href="{html.escape(REVIEW_FORM_URL, quote=True)}" target="_blank" rel="noreferrer noopener">Leave a Review</a>
    </div>
  </div>

  <div id="tab-order" class="tab-content">
    <div class="order-header">
      <h2>Let's make your cake</h2>
      <p>Every cake is baked fresh to order. Tell me what you're celebrating and I'll take it from there.</p>
    </div>

    <div class="order-steps">
      <div class="order-step"><div class="order-step-num">1</div><div class="order-step-title">Message me</div><div class="order-step-desc">DM on Instagram or WhatsApp</div></div>
      <div class="order-step"><div class="order-step-num">2</div><div class="order-step-title">Share your idea</div><div class="order-step-desc">Theme, flavors, size &amp; date</div></div>
      <div class="order-step"><div class="order-step-num">3</div><div class="order-step-title">Get a quote</div><div class="order-step-desc">I'll confirm pricing &amp; details</div></div>
      <div class="order-step"><div class="order-step-num">4</div><div class="order-step-title">Pick up &amp; enjoy</div><div class="order-step-desc">Fresh and ready to celebrate</div></div>
    </div>

    <div class="order-buttons">
      <a href="{html.escape(INSTAGRAM_URL, quote=True)}" class="order-btn order-btn-instagram" target="_blank" rel="noreferrer noopener">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
        DM on Instagram
      </a>
      {whatsapp_btn}
    </div>

    <p class="order-note">Pickup in Dallas &middot; 2-3 days notice for custom designs</p>
    <p class="order-location">Serving Dallas-Fort Worth, TX</p>
  </div>

  <div class="footer">
    <p class="brand">Baked by <span>Sarvani</span></p>
    <p class="links"><a href="{html.escape(INSTAGRAM_URL, quote=True)}" target="_blank" rel="noreferrer noopener">@bakedbysarvani</a> &middot; @rsquare_studios</p>
    <p class="copy">Baked with love in Dallas, TX</p>
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
