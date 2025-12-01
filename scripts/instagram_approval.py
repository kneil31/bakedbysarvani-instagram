#!/usr/bin/env python3
"""
Instagram Approval Workflow
===========================
1. Sends preview to Slack with photo
2. You react with ✅ to approve or ❌ to skip
3. Script checks for reaction and posts if approved

Usage:
    python instagram_approval.py --preview   # Send preview to Slack
    python instagram_approval.py --check     # Check for approval and post
    python instagram_approval.py --auto      # Preview + check in one go (for LaunchAgent)
"""

import json
import sys
import os
import time
import requests
import logging
import logging.handlers
import traceback
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from instagram_poster import InstagramPoster
from smugmug_uploader import upload_normalized_carousel
from story_generator import generate_story_for_post
from carousel_cover_generator import create_and_upload_carousel_cover

load_dotenv(Path(__file__).parent / '.env')

# Setup logging with rotation
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Log format
log_format = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Create logger
logger = logging.getLogger('instagram_approval')
logger.setLevel(logging.INFO)

# Rotating file handler - max 1MB per file, keep 5 backups
file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'instagram_approval.log',
    maxBytes=1024 * 1024,  # 1MB
    backupCount=5
)
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# Separate error log with rotation - for easy monitoring
error_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'instagram_errors.log',
    maxBytes=512 * 1024,  # 512KB
    backupCount=3
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_format)
logger.addHandler(error_handler)

# Config
SMUGMUG_API_KEY = os.getenv('SMUGMUG_API_KEY')
SMUGMUG_API_SECRET = os.getenv('SMUGMUG_API_SECRET')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

# Album configuration - BakedBySarvani
INSTAGRAM_QUEUE_ALBUM = "Sarvani Queue"    # Raw cake photos - auto-caption
CLAUDE_POSTS_ALBUM = "Sarvani-Posts"       # Edited covers with text
CLAUDE_STORIES_ALBUM = "Sarvani-Stories"   # Story templates

# Files (LOG_DIR already defined above)
PENDING_FILE = LOG_DIR / "pending_post.json"
PENDING_QUEUE_FILE = LOG_DIR / "pending_queue.json"  # For multi-item queue mode
POST_LOG = LOG_DIR / "post_history.json"
ANALYTICS_FILE = LOG_DIR / "analytics.json"

# Video extensions for Reels
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v'}

# Hashtag sets - BakedBySarvani (Cakes & Desserts)
HASHTAGS = {
    'birthday': '#BirthdayCake #DallasBakery #CustomCakes #DallasCakes #BirthdayTreats #CakeArt #DFWBakery #CakesOfInstagram #BakedBySarvani',
    'wedding': '#WeddingCake #DallasWeddingCake #DFWWedding #BridalCake #WeddingDessert #DallasBride #CakeDesign #BakedBySarvani',
    'custom': '#CustomCakes #DallasBakery #CakeArtist #DFWCakes #DesignerCakes #CakesOfDallas #EdibleArt #BakedBySarvani',
    'cupcakes': '#DallasCupcakes #Cupcakes #DFWBakery #MiniCakes #CupcakeLove #DallasDesserts #SweetTreats #BakedBySarvani',
    'babyshower': '#BabyShowerCake #DallasBakery #BabyShowerDesserts #CustomCakes #DFWBakery #PartyTreats #CakesOfInstagram #BakedBySarvani',
    'gender_reveal': '#GenderRevealCake #PinkOrBlue #RevealCake #DallasBakery #CustomCakes #DFWBakery #PartyDesserts #BakedBySarvani',
    'anniversary': '#AnniversaryCake #CelebrationCake #DallasBakery #CustomCakes #DFWBakery #LoveCake #CakesOfInstagram #BakedBySarvani',
    'graduation': '#GraduationCake #GradCake #ClassOf2025 #DallasBakery #CustomCakes #DFWBakery #CelebrationCake #BakedBySarvani',
    'christmas': '#ChristmasCake #HolidayCakes #DallasBakery #FestiveDesserts #ChristmasTreats #DFWBakery #HolidayBaking #BakedBySarvani',
    'diwali': '#DiwaliSweets #IndianDesserts #DallasBakery #FestiveTreats #DiwaliCakes #DFWIndian #IndianBakery #BakedBySarvani',
    'thanksgiving': '#ThanksgivingDesserts #FallBaking #PumpkinCake #DallasBakery #HolidayTreats #DFWBakery #FallDesserts #BakedBySarvani',
    'valentines': '#ValentinesCake #ValentinesDesserts #LoveCake #DallasBakery #HeartCake #DFWBakery #RomanticDesserts #BakedBySarvani',
    'kids': '#KidsCake #CharacterCake #DallasBakery #KidsParty #FunCakes #DFWBakery #CartoonCake #BakedBySarvani',
    'default': '#DallasBakery #BakedBySarvani #DallasCakes #HomeBaked #DFWDesserts #CakesOfInstagram #DallasFood #CustomCakes'
}

# Captions - Professional & Elegant style
import random

CAPTIONS = {
    'family': [
        "Timeless moments, beautifully preserved.",
        "The art of togetherness.",
        "Where love lives.",
        "Family. The greatest story ever told.",
        "Moments worth holding onto.",
        "Creating heirlooms, one frame at a time.",
    ],
    'newborn': [
        "The beginning of everything beautiful.",
        "Fresh beginnings. Pure love.",
        "Ten tiny fingers. One perfect moment.",
        "Welcome to the world.",
        "Life's most precious chapter.",
        "Where every detail tells a story.",
    ],
    'maternity': [
        "The beauty of becoming.",
        "Carrying the future.",
        "Grace in every moment.",
        "Before we were four, we were two.",
        "The quiet before the joy.",
        "Motherhood, beautifully anticipated.",
    ],
    'birthday': [
        "Another chapter begins.",
        "Celebrating you.",
        "A year of beautiful memories.",
        "Marking milestones, creating memories.",
        "The art of celebration.",
        "Every year more beautiful than the last.",
    ],
    'sweet16': [
        "Sixteen. Elegant. Timeless.",
        "The art of growing up beautifully.",
        "A milestone worth celebrating.",
        "Sweet sixteen, beautifully captured.",
        "Celebrating this beautiful chapter.",
        "Grace at sixteen.",
    ],
    'halloween': [
        "The art of dress-up.",
        "Little ones, big imaginations.",
        "Spooky season, captured beautifully.",
        "Creating Halloween memories.",
        "The magic of make-believe.",
        "Costumes and memories.",
    ],
    'cradle': [
        "Welcoming new life.",
        "Blessings received.",
        "A name. A blessing. A beginning.",
        "Celebrating life's newest gift.",
        "Where traditions meet new beginnings.",
        "The cradle of love.",
    ],
    'babyshower': [
        "Celebrating the journey to motherhood.",
        "Showered with love and blessings.",
        "The sweetest anticipation.",
        "Before baby arrives, we celebrate.",
        "Love multiplies.",
        "Honoring the mama-to-be.",
    ],
    'housewarming': [
        "New doors. New beginnings.",
        "Where new memories will be made.",
        "Home is where your story begins.",
        "Blessing new beginnings.",
        "The first chapter in a new home.",
        "Celebrating this beautiful milestone.",
    ],
    'gender_reveal': [
        "The moment of truth.",
        "Pink or blue, dreams come true.",
        "Life's sweetest surprise.",
        "Anticipation, beautifully captured.",
        "The reveal of a lifetime.",
        "And the secret is...",
    ],
    'cultural': [
        "Honoring tradition.",
        "Where heritage meets heart.",
        "Celebrating our roots.",
        "The beauty of tradition.",
        "Culture. Family. Legacy.",
        "Traditions worth preserving.",
    ],
    'wedding': [
        "Forever begins here.",
        "Two hearts. One beautiful story.",
        "The art of love.",
        "Where promises are made.",
        "A love story, beautifully told.",
        "Timeless elegance. Endless love.",
    ],
    'engagement': [
        "The beginning of forever.",
        "She said yes.",
        "Love, beautifully promised.",
        "Where forever begins.",
        "A love worth celebrating.",
        "The start of something beautiful.",
    ],
    'anniversary': [
        "Still choosing each other.",
        "Love that stands the test of time.",
        "Another year of beautiful memories.",
        "Celebrating lasting love.",
        "Together, still.",
        "Love, year after year.",
    ],
    'graduation': [
        "Achievement, beautifully captured.",
        "The next chapter awaits.",
        "Celebrating hard work and dedication.",
        "A milestone worth remembering.",
        "Dreams realized.",
        "The art of accomplishment.",
    ],
    'default': [
        "Moments, beautifully preserved.",
        "The art of capturing life.",
        "Timeless. Elegant. Yours.",
        "Creating memories that last.",
        "Where moments become memories.",
        "Beautifully captured.",
    ]
}

def get_caption(event_type):
    """Get a random caption for the event type."""
    captions = CAPTIONS.get(event_type, CAPTIONS['default'])
    return random.choice(captions)


def is_video_file(filename):
    """Check if file is a video (for Reels)."""
    ext = Path(filename).suffix.lower()
    return ext in VIDEO_EXTENSIONS


def check_image_size_url(image_url):
    """Check if image URL meets Instagram requirements by checking headers.

    Instagram requirements:
    - Min: 320x320 pixels
    - Max: 1440x1800 (1440 width max, aspect ratio 4:5 to 1.91:1)
    - JPEG format preferred

    Returns: dict with 'valid' bool and 'warning' message if any
    """
    try:
        # Get image info from URL headers (without downloading full image)
        response = requests.head(image_url, timeout=5)
        content_type = response.headers.get('Content-Type', '')
        content_length = int(response.headers.get('Content-Length', 0))

        warnings = []

        # Check file size (Instagram max is ~8MB for images)
        max_size_mb = 8
        if content_length > max_size_mb * 1024 * 1024:
            warnings.append(f"File size ({content_length / (1024*1024):.1f}MB) exceeds {max_size_mb}MB limit")

        # Check content type
        if 'jpeg' not in content_type.lower() and 'jpg' not in content_type.lower():
            if 'png' in content_type.lower():
                warnings.append("PNG format - JPEG recommended for better quality")

        return {
            'valid': len(warnings) == 0,
            'warnings': warnings,
            'size_mb': content_length / (1024 * 1024)
        }
    except Exception as e:
        return {'valid': True, 'warnings': [f"Could not verify: {e}"]}


def get_image_orientation(session, image_key):
    """Get image orientation (portrait, landscape, square) from SmugMug metadata.

    Returns: 'portrait', 'landscape', or 'square'
    """
    try:
        response = session.get(
            f'https://api.smugmug.com/api/v2/image/{image_key}',
            headers={'Accept': 'application/json'}
        )

        data = response.json().get('Response', {}).get('Image', {})
        width = data.get('OriginalWidth', 0)
        height = data.get('OriginalHeight', 0)

        if width == 0 or height == 0:
            return 'unknown'

        ratio = width / height

        if ratio > 1.1:  # Wider than tall
            return 'landscape'
        elif ratio < 0.9:  # Taller than wide
            return 'portrait'
        else:
            return 'square'
    except:
        return 'unknown'


def analyze_carousel_orientations(session, photos):
    """Analyze orientations of photos for carousel posting.

    Instagram carousel behavior:
    - All images use the FIRST image's aspect ratio
    - Mixed orientations = some images get cropped/padded

    Returns: dict with analysis and recommendation
    """
    orientations = []

    for photo in photos:
        image_key = photo.get('ImageKey')
        orientation = get_image_orientation(session, image_key)
        orientations.append({
            'filename': photo.get('FileName', 'unknown'),
            'orientation': orientation
        })

    # Count orientations
    portrait_count = sum(1 for o in orientations if o['orientation'] == 'portrait')
    landscape_count = sum(1 for o in orientations if o['orientation'] == 'landscape')
    square_count = sum(1 for o in orientations if o['orientation'] == 'square')

    total = len(orientations)

    # Determine if mixed
    is_mixed = (portrait_count > 0 and landscape_count > 0)

    # Recommendation
    if is_mixed:
        # Find dominant orientation
        if portrait_count >= landscape_count:
            dominant = 'portrait'
            recommendation = 'Consider posting portraits separately, or put portrait first (landscape will be cropped)'
        else:
            dominant = 'landscape'
            recommendation = 'Consider posting landscapes separately, or put landscape first (portraits will have bars)'
    else:
        dominant = 'portrait' if portrait_count > 0 else ('landscape' if landscape_count > 0 else 'square')
        recommendation = 'All same orientation - good for carousel!'

    return {
        'orientations': orientations,
        'portrait_count': portrait_count,
        'landscape_count': landscape_count,
        'square_count': square_count,
        'is_mixed': is_mixed,
        'dominant': dominant,
        'recommendation': recommendation
    }


def sort_photos_by_orientation(photos, orientations_analysis):
    """Sort photos to put dominant orientation first for better carousel display.

    Strategy: Put the dominant orientation photos first so Instagram uses
    that aspect ratio, then others follow (will be cropped/padded to match).
    """
    if not orientations_analysis.get('is_mixed'):
        return photos  # No sorting needed

    dominant = orientations_analysis.get('dominant', 'portrait')
    orientations = {o['filename']: o['orientation'] for o in orientations_analysis['orientations']}

    # Sort: dominant orientation first, then others
    def sort_key(photo):
        filename = photo.get('FileName', '')
        orientation = orientations.get(filename, 'unknown')
        if orientation == dominant:
            return 0  # First
        elif orientation == 'square':
            return 1  # Second (squares work with both)
        else:
            return 2  # Last

    return sorted(photos, key=sort_key)


def normalize_carousel_for_posting(image_urls, event_name, orientation_analysis):
    """Normalize mixed-orientation carousel photos to 4:5 canvas with padding.

    When carousel has mixed Portrait + Landscape photos, normalizing all to
    4:5 canvas ensures:
    - No cropping (full photos visible)
    - Consistent viewing experience
    - Professional photographer standard approach

    Args:
        image_urls: List of original SmugMug image URLs
        event_name: Event name for filename prefix
        orientation_analysis: Dict with is_mixed, portrait_count, landscape_count

    Returns:
        List of normalized image URLs (or original if not mixed/normalization fails)
    """
    # Only normalize if mixed orientations
    if not orientation_analysis.get('is_mixed'):
        logger.info(f"Carousel not mixed - no normalization needed")
        return image_urls

    logger.info(f"Mixed orientations detected - normalizing {len(image_urls)} photos to 4:5 canvas")
    print(f"   📐 Normalizing {len(image_urls)} photos to 4:5 canvas (auto-color padding)...")

    try:
        normalized_urls = upload_normalized_carousel(
            image_urls,
            event_name,
            use_blur=False  # Use auto-color padding (cleaner look)
        )

        if normalized_urls and len(normalized_urls) == len(image_urls):
            logger.info(f"Successfully normalized {len(normalized_urls)} photos")
            print(f"   ✅ Normalized! All photos now 4:5 aspect ratio")
            return normalized_urls
        else:
            logger.warning(f"Normalization incomplete - falling back to original URLs")
            print(f"   ⚠️ Normalization incomplete - using original photos")
            return image_urls

    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        print(f"   ⚠️ Normalization failed: {e} - using original photos")
        return image_urls


def split_by_orientation(session, event_name, photos):
    """Split mixed-orientation photos into separate Portrait and Landscape groups.

    Rule: Never mix Portrait and Landscape in same carousel.
    - Cropping portraits in landscape carousel = heads/feet cut off
    - Letterboxing landscapes in portrait carousel = acceptable but not ideal
    - Best solution: Split into 2 separate posts with 1+ day gap

    Returns: list of (new_event_name, photos, orientation_type) tuples
    """
    if len(photos) < 2:
        return [(event_name, photos, 'single')]

    # Analyze each photo's orientation
    portraits = []
    landscapes = []
    squares = []

    for photo in photos:
        image_key = photo.get('ImageKey')
        orientation = get_image_orientation(session, image_key)

        if orientation == 'portrait':
            portraits.append(photo)
        elif orientation == 'landscape':
            landscapes.append(photo)
        else:
            squares.append(photo)

    # If not mixed, return as-is
    if not (portraits and landscapes):
        if portraits:
            return [(event_name, portraits + squares, 'portrait')]
        elif landscapes:
            return [(event_name, landscapes + squares, 'landscape')]
        else:
            return [(event_name, squares, 'square')]

    # Mixed orientations - SPLIT into separate posts
    result = []

    # Portraits first (usually more important - full-length shots)
    if portraits:
        portrait_name = f"{event_name} (Portrait)"
        result.append((portrait_name, portraits + squares, 'portrait'))

    # Landscapes second (post with 1+ day gap)
    if landscapes:
        landscape_name = f"{event_name} (Landscape)"
        result.append((landscape_name, landscapes, 'landscape'))

    return result


def get_video_url(session, image_key):
    """Get video URL from SmugMug for Reels."""
    response = session.get(
        f'https://api.smugmug.com/api/v2/image/{image_key}',
        params={'_expand': 'ImageSizes'},
        headers={'Accept': 'application/json'}
    )

    data = response.json()
    sizes = data.get('Expansions', {}).get(f'/api/v2/image/{image_key}-0!sizes', {}).get('ImageSizes', {})

    # SmugMug stores video URLs differently
    return sizes.get('VideoURL') or sizes.get('X3LargeImageUrl') or sizes.get('LargeImageUrl')


def get_smugmug_session():
    """Get authenticated SmugMug session."""
    config_path = Path.home() / '.smugmug_config.json'
    with open(config_path) as f:
        config = json.load(f)

    return OAuth1Session(
        SMUGMUG_API_KEY,
        client_secret=SMUGMUG_API_SECRET,
        resource_owner_key=config['access_token'],
        resource_owner_secret=config['access_token_secret']
    ), config


def get_queue_photos():
    """Get all photos from both Claude_Posts and Instagram Queue albums.

    Returns photos from both albums with source marked:
    - Claude_Posts: edited covers with text (no caption needed)
    - Instagram Queue: raw photos (auto-caption)
    """
    session, config = get_smugmug_session()

    user_uri = config['user_uri']
    albums_url = f'https://api.smugmug.com{user_uri}!albums'
    response = session.get(albums_url, headers={'Accept': 'application/json'})
    albums = response.json().get('Response', {}).get('Album', [])

    all_images = []
    albums_found = {}

    # Check Claude_Posts first (edited covers - no caption)
    claude_posts = next((a for a in albums if a['Name'].lower() == CLAUDE_POSTS_ALBUM.lower()), None)
    if claude_posts:
        images_url = f"https://api.smugmug.com{claude_posts['Uri']}!images"
        img_response = session.get(images_url, headers={'Accept': 'application/json'})
        images = img_response.json().get('Response', {}).get('AlbumImage', [])
        # Mark source album for each image
        for img in images:
            img['_source_album'] = 'claude_posts'
            img['_album_key'] = claude_posts['AlbumKey']
            img['_skip_caption'] = True  # Already has text overlay
        all_images.extend(images)
        albums_found['claude_posts'] = claude_posts
        logger.info(f"Found {len(images)} photos in Claude_Posts album")

    # Check Instagram Queue (raw photos - auto-caption)
    queue_album = next((a for a in albums if a['Name'].lower() == INSTAGRAM_QUEUE_ALBUM.lower()), None)
    if queue_album:
        images_url = f"https://api.smugmug.com{queue_album['Uri']}!images"
        img_response = session.get(images_url, headers={'Accept': 'application/json'})
        images = img_response.json().get('Response', {}).get('AlbumImage', [])
        # Mark source album for each image
        for img in images:
            img['_source_album'] = 'instagram_queue'
            img['_album_key'] = queue_album['AlbumKey']
            img['_skip_caption'] = False  # Needs auto-caption
        all_images.extend(images)
        albums_found['instagram_queue'] = queue_album
        logger.info(f"Found {len(images)} photos in Instagram Queue album")

    # Return primary album for backward compatibility
    primary_album = albums_found.get('claude_posts') or albums_found.get('instagram_queue')

    return all_images, primary_album, session


def extract_event_name(filename):
    """Extract event name from filename for grouping carousel images.

    Examples:
        'Snithik_Birthday_001.jpg' -> 'snithik_birthday'
        'KAYU_Halloween_012.jpg' -> 'kayu_halloween'
        'Manas_Maternity_05.jpg' -> 'manas_maternity'
    """
    import re
    name_lower = filename.lower()

    # Remove file extension
    name_no_ext = name_lower.rsplit('.', 1)[0]

    # Remove trailing numbers (like _001, _12, -05, etc.)
    name_clean = re.sub(r'[-_]?\d+$', '', name_no_ext)

    # Remove common suffixes
    name_clean = re.sub(r'[-_]?(edit|final|web|export)$', '', name_clean)

    return name_clean.strip('_- ')


def group_photos_by_event(photos):
    """Group photos by event name for carousel posting.

    Returns: dict with event_name -> list of photos
    """
    from collections import defaultdict
    groups = defaultdict(list)

    for photo in photos:
        filename = photo.get('FileName', 'unknown')
        event_name = extract_event_name(filename)
        groups[event_name].append(photo)

    return dict(groups)


def get_image_url(session, image_key):
    """Get direct image URL from SmugMug."""
    response = session.get(
        f'https://api.smugmug.com/api/v2/image/{image_key}',
        params={'_expand': 'ImageSizes'},
        headers={'Accept': 'application/json'}
    )

    data = response.json()
    sizes = data.get('Expansions', {}).get(f'/api/v2/image/{image_key}-0!sizes', {}).get('ImageSizes', {})

    return sizes.get('X3LargeImageUrl') or sizes.get('LargeImageUrl') or sizes.get('MediumImageUrl')


def detect_event_type(filename):
    """Detect event type from filename.

    Event types: family, newborn, maternity, birthday, sweet16, halloween,
    cradle, babyshower, housewarming, gender_reveal, cultural, wedding,
    engagement, anniversary, graduation
    """
    name_lower = filename.lower()

    # Wedding & related events
    if 'wedding' in name_lower:
        return 'wedding'
    elif 'engagement' in name_lower or 'engaged' in name_lower:
        return 'engagement'
    elif 'anniversary' in name_lower:
        return 'anniversary'
    # Graduation
    elif 'graduation' in name_lower or 'grad ' in name_lower or 'convocation' in name_lower:
        return 'graduation'
    # Baby-related
    elif 'maternity' in name_lower or 'seemantham' in name_lower:
        return 'maternity'
    elif 'newborn' in name_lower or 'fresh48' in name_lower:
        return 'newborn'
    elif 'akarsh' in name_lower or 'fernandez' in name_lower or 'baby shower' in name_lower or 'babyshower' in name_lower:
        return 'babyshower'
    elif 'cradle' in name_lower or 'naming' in name_lower or 'vayu' in name_lower or 'skanda' in name_lower:
        return 'cradle'
    elif ' gr' in name_lower or 'gender' in name_lower or 'reveal' in name_lower:
        return 'gender_reveal'
    # Birthday & milestones
    elif 'sweet 16' in name_lower or 'sweet16' in name_lower:
        return 'sweet16'
    elif 'birthday' in name_lower or 'bday' in name_lower:
        return 'birthday'
    # Special occasions
    elif 'halloween' in name_lower or 'kayu' in name_lower:
        return 'halloween'
    elif ' hw' in name_lower or 'housewarming' in name_lower or 'house warming' in name_lower:
        return 'housewarming'
    # Cultural/Traditional
    elif 'sangeet' in name_lower or 'mehndi' in name_lower or 'haldi' in name_lower or 'pooja' in name_lower:
        return 'cultural'
    else:
        return 'family'


def send_slack_preview(photo_data):
    """Send preview to Slack and return message timestamp."""
    client = WebClient(token=SLACK_BOT_TOKEN)

    is_carousel = photo_data.get('is_carousel', False)
    is_reel = photo_data.get('is_reel', False)
    image_count = photo_data.get('image_count', 1)

    # Build header text
    if is_carousel:
        header_text = f"📸 Carousel Ready ({image_count} photos)"
        photo_info = f"*Event:* {photo_data['event_name']}\n*Photos:* {image_count} images\n*Type:* {photo_data['event_type'].upper()}\n*Queue:* {photo_data['queue_count']} photos remaining"
    elif is_reel:
        header_text = "🎬 Reel Ready for Approval"
        photo_info = f"*Video:* {photo_data['filename']}\n*Type:* {photo_data['event_type'].upper()}\n*Queue:* {photo_data['queue_count']} items remaining"
    else:
        header_text = "📸 Instagram Post Ready for Approval"
        photo_info = f"*Photo:* {photo_data['filename']}\n*Type:* {photo_data['event_type'].upper()}\n*Queue:* {photo_data['queue_count']} photos remaining"

    try:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": photo_info
                }
            },
            {
                "type": "image",
                "image_url": photo_data['image_url'],  # First image as preview
                "alt_text": photo_data.get('event_name', photo_data.get('filename', 'photo'))
            }
        ]

        # For carousels, show thumbnails of other images
        if is_carousel and image_count > 1:
            other_files = photo_data.get('all_filenames', [])[1:4]  # Show up to 3 more
            if other_files:
                more_text = f"+ {', '.join(other_files)}"
                if image_count > 4:
                    more_text += f" + {image_count - 4} more"
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": more_text}]
                })

            # Show orientation info if mixed (will be normalized)
            orientation_analysis = photo_data.get('orientation_analysis', {})
            if orientation_analysis.get('is_mixed'):
                portrait_count = orientation_analysis.get('portrait_count', 0)
                landscape_count = orientation_analysis.get('landscape_count', 0)
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"📐 *Mixed orientations:* {portrait_count} portrait, {landscape_count} landscape\n✅ Will be *auto-normalized* to 4:5 canvas with padding (no cropping!)"
                    }]
                })

        blocks.extend([
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Caption:*\n{photo_data['caption']}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Hashtags:*\n`{photo_data['hashtags'][:80]}...`"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "React with:\n• ✅ to *approve* and post\n• ❌ to *skip* this photo"
                }
            }
        ])

        result = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"📸 Instagram Post Ready: {photo_data.get('event_name', photo_data.get('filename', 'photo'))}",
            blocks=blocks
        )

        return result['ts']  # Message timestamp (used to check reactions)

    except SlackApiError as e:
        print(f"❌ Slack API error: {e.response['error']}")
        return None


def check_slack_reaction(message_ts):
    """Check if message has approval reaction."""
    client = WebClient(token=SLACK_BOT_TOKEN)

    try:
        result = client.reactions_get(
            channel=SLACK_CHANNEL_ID,
            timestamp=message_ts
        )

        reactions = result.get('message', {}).get('reactions', [])

        for reaction in reactions:
            name = reaction.get('name', '')
            # Check for approval reactions
            if name in ['white_check_mark', 'heavy_check_mark', 'ballot_box_with_check', '+1', 'thumbsup']:
                return 'approve'
            # Check for skip reactions
            elif name in ['x', 'negative_squared_cross_mark', '-1', 'thumbsdown']:
                return 'skip'

        return None  # No reaction yet

    except SlackApiError as e:
        print(f"❌ Slack API error: {e.response['error']}")
        return None


def remove_from_queue(image_key, album_key):
    """Remove image from queue album after posting."""
    session, _ = get_smugmug_session()

    image_uri = f"/api/v2/album/{album_key}/image/{image_key}"

    try:
        response = session.delete(
            f'https://api.smugmug.com{image_uri}',
            headers={'Accept': 'application/json'}
        )
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"⚠️ Could not remove from queue: {e}")
        return False


def send_slack_result(success, filename, post_id=None, error=None):
    """Send result notification to Slack."""
    client = WebClient(token=SLACK_BOT_TOKEN)

    if success:
        text = f"✅ *Posted to Instagram!*\n📷 {filename}\n🔗 Post ID: {post_id}"
    else:
        text = f"❌ *Post failed*\n📷 {filename}\n⚠️ Error: {error}"

    try:
        client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=text)
    except:
        pass


def log_post(entry):
    """Log post to history file."""
    logs = []
    if POST_LOG.exists():
        with open(POST_LOG) as f:
            logs = json.load(f)

    logs.append(entry)

    with open(POST_LOG, 'w') as f:
        json.dump(logs, f, indent=2)


def fetch_post_insights(post_id):
    """Fetch engagement metrics for a post using Instagram Graph API."""
    access_token = os.getenv('IG_ACCESS_TOKEN')
    if not access_token or not post_id:
        return None

    try:
        # Fetch media insights
        url = f"https://graph.facebook.com/v18.0/{post_id}/insights"
        params = {
            'metric': 'impressions,reach,saved,likes,comments,shares',
            'access_token': access_token
        }
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json().get('data', [])
            insights = {}
            for item in data:
                insights[item['name']] = item['values'][0]['value']
            return insights
    except Exception as e:
        print(f"⚠️ Could not fetch insights: {e}")

    return None


def update_analytics():
    """Update analytics for all tracked posts (run weekly)."""
    if not POST_LOG.exists():
        print("No posts to analyze")
        return

    with open(POST_LOG) as f:
        posts = json.load(f)

    # Load existing analytics
    analytics = {}
    if ANALYTICS_FILE.exists():
        with open(ANALYTICS_FILE) as f:
            analytics = json.load(f)

    updated_count = 0
    for post in posts:
        post_id = post.get('post_id')
        if not post_id:
            continue

        # Fetch latest insights
        insights = fetch_post_insights(post_id)
        if insights:
            analytics[post_id] = {
                'post_date': post.get('date'),
                'event_type': post.get('event_type'),
                'is_carousel': post.get('is_carousel', False),
                'is_reel': post.get('is_reel', False),
                'insights': insights,
                'last_updated': datetime.now().isoformat()
            }
            updated_count += 1

    # Save analytics
    with open(ANALYTICS_FILE, 'w') as f:
        json.dump(analytics, f, indent=2)

    print(f"📊 Updated analytics for {updated_count} posts")
    return analytics


def get_analytics_summary():
    """Get summary of posting performance."""
    if not ANALYTICS_FILE.exists():
        return "No analytics data yet. Run --analytics after posting some content."

    with open(ANALYTICS_FILE) as f:
        analytics = json.load(f)

    if not analytics:
        return "No analytics data yet."

    # Calculate averages by type
    totals = {
        'single': {'count': 0, 'impressions': 0, 'reach': 0, 'likes': 0, 'saves': 0},
        'carousel': {'count': 0, 'impressions': 0, 'reach': 0, 'likes': 0, 'saves': 0},
        'reel': {'count': 0, 'impressions': 0, 'reach': 0, 'likes': 0, 'saves': 0}
    }

    for post_id, data in analytics.items():
        insights = data.get('insights', {})

        if data.get('is_reel'):
            key = 'reel'
        elif data.get('is_carousel'):
            key = 'carousel'
        else:
            key = 'single'

        totals[key]['count'] += 1
        totals[key]['impressions'] += insights.get('impressions', 0)
        totals[key]['reach'] += insights.get('reach', 0)
        totals[key]['likes'] += insights.get('likes', 0)
        totals[key]['saves'] += insights.get('saved', 0)

    # Build summary
    summary = ["\n📊 INSTAGRAM ANALYTICS SUMMARY", "=" * 40]

    for post_type, stats in totals.items():
        if stats['count'] > 0:
            avg_impressions = stats['impressions'] / stats['count']
            avg_reach = stats['reach'] / stats['count']
            avg_likes = stats['likes'] / stats['count']
            avg_saves = stats['saves'] / stats['count']

            summary.append(f"\n{post_type.upper()} ({stats['count']} posts):")
            summary.append(f"  Avg Impressions: {avg_impressions:.0f}")
            summary.append(f"  Avg Reach: {avg_reach:.0f}")
            summary.append(f"  Avg Likes: {avg_likes:.1f}")
            summary.append(f"  Avg Saves: {avg_saves:.1f}")

    return "\n".join(summary)


def do_preview():
    """Send preview to Slack."""
    logger.info("=" * 60)
    logger.info("INSTAGRAM PREVIEW START")
    logger.info("=" * 60)

    # Check if there's already a pending post
    if PENDING_FILE.exists():
        with open(PENDING_FILE) as f:
            pending = json.load(f)
        pending_name = pending.get('event_name', pending.get('filename', 'unknown'))
        logger.info(f"Already pending: {pending_name} - skipping preview")
        print(f"⏳ Already pending: {pending_name}")
        print("   React in Slack or run --check")
        return

    # Get photos from queue
    try:
        logger.info("Fetching photos from SmugMug queue...")
        photos, queue_album, session = get_queue_photos()
    except Exception as e:
        logger.error(f"Failed to fetch SmugMug queue: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ SmugMug error: {e}")
        return

    if not photos:
        logger.info("Queue is empty - no photos to preview")
        print("📭 Queue is empty - no photos to preview")
        return

    logger.info(f"Found {len(photos)} photo(s) in queue")
    print(f"📸 Found {len(photos)} photo(s) in queue")

    # Group photos by event to detect carousels
    groups = group_photos_by_event(photos)
    print(f"   Grouped into {len(groups)} event(s)")

    # Get the first group (could be single or carousel)
    first_event = list(groups.keys())[0]
    event_photos = groups[first_event]

    # Check if photos are from Claude_Posts (edited covers - skip caption)
    skip_caption = any(photo.get('_skip_caption', False) for photo in event_photos)
    source_album = event_photos[0].get('_source_album', 'instagram_queue')
    photo_album_key = event_photos[0].get('_album_key', queue_album['AlbumKey'] if queue_album else None)

    if skip_caption:
        print(f"   📝 Source: Claude_Posts (edited cover - no caption)")
    else:
        print(f"   📝 Source: Instagram Queue (auto-caption)")

    is_carousel = len(event_photos) >= 2 and len(event_photos) <= 10

    if is_carousel:
        print(f"🎠 Carousel detected: {first_event} ({len(event_photos)} photos)")

        # Analyze orientations for mixed portrait/landscape
        print("   Analyzing orientations...")
        orientation_analysis = analyze_carousel_orientations(session, event_photos)

        if orientation_analysis['is_mixed']:
            print(f"   ⚠️  MIXED ORIENTATIONS: {orientation_analysis['portrait_count']} portrait, {orientation_analysis['landscape_count']} landscape")
            print(f"   💡 {orientation_analysis['recommendation']}")

            # Sort photos to put dominant orientation first
            event_photos = sort_photos_by_orientation(event_photos, orientation_analysis)
            print(f"   📐 Sorted: {orientation_analysis['dominant']} images first")
        else:
            print(f"   ✅ All {orientation_analysis['dominant']} - good alignment!")

        # Get URLs for all photos in carousel (now sorted)
        image_urls = []
        image_keys = []
        all_filenames = []

        for photo in event_photos:
            filename = photo.get('FileName', 'unknown')
            image_key = photo.get('ImageKey')
            url = get_image_url(session, image_key)

            if url:
                image_urls.append(url)
                image_keys.append(image_key)
                all_filenames.append(filename)
                print(f"   ✓ {filename}")

        if len(image_urls) < 2:
            print("❌ Could not get enough image URLs for carousel")
            return

        # Detect event type from first filename
        event_type = detect_event_type(all_filenames[0])
        print(f"   Type: {event_type}")

        # Get caption and hashtags (always generate based on event type)
        caption = get_caption(event_type)
        hashtags = HASHTAGS.get(event_type, HASHTAGS['default'])

        # Prepare carousel data
        photo_data = {
            'is_carousel': True,
            'event_name': first_event,
            'image_count': len(image_urls),
            'image_urls': image_urls,
            'image_keys': image_keys,
            'image_url': image_urls[0],  # First image for Slack preview
            'all_filenames': all_filenames,
            'event_type': event_type,
            'caption': caption,
            'hashtags': hashtags,
            'queue_count': len(photos),
            'album_key': photo_album_key,  # Use correct album key from photo
            'source_album': source_album,  # Track source for reference
            'skip_caption': skip_caption,  # Track if caption was skipped
            'orientation_analysis': orientation_analysis,  # Store for Slack warning
            'created': datetime.now().isoformat()
        }
    else:
        # Single photo or video (Reel)
        photo = event_photos[0]
        filename = photo.get('FileName', 'unknown')
        image_key = photo.get('ImageKey')

        # Check if this is a video (Reel)
        is_reel = is_video_file(filename)

        if is_reel:
            print(f"🎬 Reel detected: {filename}")
            # Get video URL for Reel
            media_url = get_video_url(session, image_key)
        else:
            print(f"📷 Single photo: {filename}")
            # Get image URL
            media_url = get_image_url(session, image_key)

        if not media_url:
            print("❌ Could not get media URL")
            return

        # Detect event type
        event_type = detect_event_type(filename)
        print(f"   Type: {event_type}")

        # Get caption and hashtags (always generate based on event type)
        caption = get_caption(event_type)
        hashtags = HASHTAGS.get(event_type, HASHTAGS['default'])

        # Prepare photo/reel data
        photo_data = {
            'is_carousel': False,
            'is_reel': is_reel,
            'filename': filename,
            'image_key': image_key,
            'image_url': media_url,  # Works for both image and video
            'event_type': event_type,
            'caption': caption,
            'hashtags': hashtags,
            'queue_count': len(photos),
            'album_key': photo_album_key,  # Use correct album key from photo
            'source_album': source_album,  # Track source for reference
            'skip_caption': skip_caption,  # Track if caption was skipped
            'created': datetime.now().isoformat()
        }

    # Send to Slack
    print("\n📱 Sending to Slack...")
    try:
        message_ts = send_slack_preview(photo_data)
    except Exception as e:
        logger.error(f"Failed to send Slack preview: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ Slack error: {e}")
        return

    if message_ts:
        photo_data['slack_ts'] = message_ts

        # Save pending post
        with open(PENDING_FILE, 'w') as f:
            json.dump(photo_data, f, indent=2)

        content_type = "carousel" if is_carousel else ("reel" if photo_data.get('is_reel') else "single")
        content_name = photo_data.get('event_name', photo_data.get('filename', 'unknown'))
        logger.info(f"Preview sent: {content_type} - {content_name}")
        logger.info(f"Event type: {photo_data.get('event_type')}")
        logger.info(f"Slack message_ts: {message_ts}")

        if is_carousel:
            print(f"✅ Carousel preview sent! ({len(image_urls)} photos)")
        elif photo_data.get('is_reel'):
            print(f"✅ Reel preview sent!")
        else:
            print(f"✅ Preview sent!")
        print("   React with ✅ to approve or ❌ to skip")
    else:
        logger.error("Slack preview returned no message_ts")
        print("❌ Failed to send Slack preview")


def do_check(dry_run=False):
    """Check for approval and post if approved."""
    logger.info("=" * 60)
    logger.info(f"CHECK APPROVAL START {'(DRY RUN)' if dry_run else ''}")
    logger.info("=" * 60)

    if not PENDING_FILE.exists():
        logger.info("No pending post to check")
        print("📭 No pending post to check")
        return

    # Load pending post
    with open(PENDING_FILE) as f:
        pending = json.load(f)

    is_carousel = pending.get('is_carousel', False)
    is_reel = pending.get('is_reel', False)
    post_name = pending.get('event_name', pending.get('filename', 'unknown'))
    message_ts = pending.get('slack_ts')

    content_type = "carousel" if is_carousel else ("reel" if is_reel else "single")
    logger.info(f"Checking: {content_type} - {post_name}")

    if is_carousel:
        print(f"🎠 Pending carousel: {post_name} ({pending.get('image_count', 0)} photos)")
    elif is_reel:
        print(f"🎬 Pending reel: {post_name}")
    else:
        print(f"📷 Pending: {post_name}")

    if not message_ts:
        logger.error("No Slack message_ts found in pending file")
        print("❌ No Slack message timestamp found")
        return

    # Check for reaction
    print("🔍 Checking Slack reaction...")
    try:
        reaction = check_slack_reaction(message_ts)
        logger.info(f"Slack reaction: {reaction}")
    except Exception as e:
        logger.error(f"Failed to check Slack reaction: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ Slack error: {e}")
        return

    if reaction == 'approve':
        logger.info(f"APPROVED - {'DRY RUN' if dry_run else 'Posting'} {content_type}: {post_name}")

        if dry_run:
            print("✅ Approved! [DRY RUN - NOT posting to Instagram]")
            print(f"   📝 Would post: {content_type}")
            print(f"   📸 Event: {post_name}")
            print(f"   📄 Caption: {pending.get('caption', '')[:50]}...")
            if is_carousel:
                print(f"   🎠 Images: {len(pending.get('image_urls', []))} photos")
            result = {'success': True, 'post_id': 'DRY_RUN_NO_POST'}
        else:
            print("✅ Approved! Posting to Instagram...")
            try:
                poster = InstagramPoster()

                if is_carousel:
                    # Check if mixed orientations - normalize if needed
                    orientation_analysis = pending.get('orientation_analysis', {})
                    image_urls = pending['image_urls']

                    if orientation_analysis.get('is_mixed'):
                        # Normalize to 4:5 canvas with auto-color padding
                        print("   📐 Normalizing mixed orientations to 4:5 canvas...")
                        image_urls = normalize_carousel_for_posting(
                            image_urls,
                            pending.get('event_name', 'carousel'),
                            orientation_analysis
                        )

                    # Generate carousel cover with text overlay (Instagram Best Practice)
                    print("   📸 Generating text cover...")
                    try:
                        cover_url = create_and_upload_carousel_cover(
                            first_image_url=image_urls[0],
                            event_name=pending.get('event_name', 'carousel'),
                            event_type=pending.get('event_type', 'default')
                        )
                        if cover_url:
                            image_urls = [cover_url] + image_urls
                            logger.info(f"Cover generated and added as first slide")
                            print("   ✅ Cover added as slide 1")
                        else:
                            logger.warning(f"Cover generation failed - using photos only")
                            print("   ⚠️ Cover failed - using photos only")
                    except Exception as cover_err:
                        logger.warning(f"Cover generation error: {cover_err}")
                        print(f"   ⚠️ Cover error: {cover_err}")

                    # Post carousel
                    result = poster.post_carousel(
                        image_urls,
                        pending['caption'],
                        pending['hashtags']
                    )
                elif is_reel:
                    # Post reel
                    result = poster.post_reel(
                        pending['image_url'],
                        pending['caption'],
                        pending['hashtags']
                    )
                else:
                    # Post single image
                    result = poster.post_single_image(
                        pending['image_url'],
                        pending['caption'],
                        pending['hashtags']
                    )
            except Exception as e:
                logger.error(f"Instagram API error: {e}")
                logger.error(traceback.format_exc())
                print(f"❌ Instagram API error: {e}")
                send_slack_result(False, post_name, error=str(e))
                return

        if result.get('success'):
            post_id = result.get('post_id')
            logger.info(f"SUCCESS - Posted to Instagram: {post_id}")
            logger.info(f"Content: {post_name} | Type: {content_type} | Event: {pending.get('event_type')}")
            print(f"\n🎉 SUCCESS! Post ID: {post_id}")

            # Generate Story templates for this post
            try:
                # Get all photo URLs (for duo/trio templates)
                if is_carousel:
                    photo_urls = pending.get('image_urls', [])
                else:
                    photo_urls = [pending.get('image_url')] if pending.get('image_url') else []

                if photo_urls:
                    print(f"📱 Generating Story templates (v1.0)...")
                    story_paths = generate_story_for_post(
                        photo_urls=photo_urls,
                        event_name=pending.get('event_name', post_name),
                        event_type=pending.get('event_type', 'default')
                    )
                    if story_paths:
                        logger.info(f"Stories generated: {len(story_paths)} templates")
                        print(f"📁 Stories saved to: output/stories/")
            except Exception as story_err:
                logger.warning(f"Story generation failed: {story_err}")
                print(f"⚠️ Story generation failed: {story_err}")

            if dry_run:
                print(f"\n🧪 DRY RUN complete - would have posted successfully")
                print(f"   📱 Stories generated: {len(story_paths) if 'story_paths' in dir() else 0}")
                print(f"   ⏳ Pending file NOT deleted (dry run)")
                print(f"   📋 Queue NOT modified (dry run)")
            else:
                # Remove from queue
                if is_carousel:
                    # Remove all images in carousel
                    for image_key in pending.get('image_keys', []):
                        remove_from_queue(image_key, pending['album_key'])
                    print(f"🗑️ Removed {len(pending.get('image_keys', []))} images from queue")
                else:
                    remove_from_queue(pending['image_key'], pending['album_key'])
                    print("🗑️ Removed from queue")

                # Delete pending file
                PENDING_FILE.unlink()

                # Log and notify
                log_entry = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'time': datetime.now().isoformat(),
                    'success': True,
                    'post_id': post_id,
                    'event_type': pending['event_type'],
                    'is_carousel': is_carousel,
                    'is_reel': is_reel
                }

                if is_carousel:
                    log_entry['event_name'] = post_name
                    log_entry['image_count'] = pending.get('image_count', 0)
                    log_entry['filenames'] = pending.get('all_filenames', [])
                else:
                    log_entry['filename'] = post_name

                log_post(log_entry)
                send_slack_result(True, post_name, post_id)
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"Instagram post FAILED: {error}")
            logger.error(f"Content: {post_name} | Type: {content_type}")
            print(f"❌ Post failed: {error}")
            send_slack_result(False, post_name, error=error)

    elif reaction == 'skip':
        logger.info(f"SKIPPED by user: {post_name}")
        print("⏭️ Skipped!")

        # Remove all images if carousel
        if is_carousel:
            for image_key in pending.get('image_keys', []):
                remove_from_queue(image_key, pending['album_key'])
            print(f"🗑️ Removed {len(pending.get('image_keys', []))} images from queue")
        else:
            remove_from_queue(pending.get('image_key'), pending['album_key'])
            print("🗑️ Removed from queue")

        PENDING_FILE.unlink()
        send_slack_result(False, post_name, error="Skipped by user")

    else:
        print("⏳ No reaction yet - waiting for approval")


def do_auto(dry_run=False):
    """Full auto mode: preview if needed, then check for approval."""
    print(f"\n{'='*60}")
    print(f"  INSTAGRAM AUTO - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if dry_run:
        print(f"  🧪 DRY RUN MODE")
    print(f"{'='*60}\n")

    # If no pending, send preview
    if not PENDING_FILE.exists():
        photos, _, _ = get_queue_photos()
        if photos:
            print("📤 Sending preview...")
            do_preview()
            print("\n⏳ Waiting 30 seconds for reaction...")
            time.sleep(30)
        else:
            print("📭 Queue is empty")
            return

    # Check for approval
    do_check(dry_run=dry_run)


def do_queue():
    """Show all queue items in Slack - you pick what to post.

    NEW WORKFLOW:
    1. Sends ALL events in queue as separate Slack messages
    2. React with ✅ to any item(s) you want to post
    3. Run --check-queue to post all approved items
    """
    logger.info("=" * 60)
    logger.info("QUEUE BROWSER START")
    logger.info("=" * 60)

    # Check if there's already a pending queue
    if PENDING_QUEUE_FILE.exists():
        with open(PENDING_QUEUE_FILE) as f:
            pending = json.load(f)
        logger.info(f"Queue already sent with {len(pending)} items - use --check-queue")
        print(f"⏳ Queue already sent with {len(pending)} items")
        print("   React to items in Slack, then run --check-queue")
        return

    # Get photos from SmugMug queue
    try:
        logger.info("Fetching photos from SmugMug queue...")
        photos, queue_album, session = get_queue_photos()
    except Exception as e:
        logger.error(f"Failed to fetch SmugMug queue: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ SmugMug error: {e}")
        return

    if not photos:
        logger.info("Queue is empty")
        print("📭 Queue is empty - no photos to show")
        return

    # Group photos by event
    raw_groups = group_photos_by_event(photos)
    logger.info(f"Found {len(photos)} photos in {len(raw_groups)} events")

    # Split mixed-orientation events into Portrait/Landscape carousels
    print(f"\n📸 Queue: {len(photos)} photos in {len(raw_groups)} events")
    print("   Splitting by orientation (Portrait carousel + Landscape carousel)...")
    print("=" * 50)

    split_groups = []
    for event_name, event_photos in raw_groups.items():
        splits = split_by_orientation(session, event_name, event_photos)
        for split_name, split_photos, orientation_type in splits:
            split_groups.append((split_name, split_photos, orientation_type))
        if len(splits) > 1:
            print(f"   ✂️  {event_name} → Portrait + Landscape carousels")

    print(f"\n   📝 Total: {len(split_groups)} carousels")
    print("=" * 50)

    # Send header message to Slack
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        header_text = f"*{len(photos)} photos* → *{len(split_groups)} carousels*"
        header_text += "\n\n📐 Split by orientation: Portrait carousel + Landscape carousel"
        header_text += "\n\nReact with ✅ to items you want to post."

        header_result = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"📋 *Instagram Queue* - {len(split_groups)} carousels ready",
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"📋 Instagram Queue - {len(split_groups)} carousels"}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": header_text
                    }
                },
                {"type": "divider"}
            ]
        )
    except SlackApiError as e:
        logger.error(f"Failed to send Slack header: {e}")
        print(f"❌ Slack error: {e}")
        return

    # Prepare all events and send to Slack
    pending_items = []

    for idx, (event_name, event_photos, orientation_type) in enumerate(split_groups, 1):
        is_carousel = len(event_photos) >= 2 and len(event_photos) <= 10
        first_photo = event_photos[0]
        filename = first_photo.get('FileName', 'unknown')
        image_key = first_photo.get('ImageKey')

        # Check if video (Reel)
        is_reel = is_video_file(filename) and len(event_photos) == 1

        # Get image URL for preview
        if is_reel:
            media_url = get_video_url(session, image_key)
        else:
            media_url = get_image_url(session, image_key)

        if not media_url:
            print(f"   ⚠️ Skipping {event_name} - no URL")
            continue

        # Detect event type
        event_type = detect_event_type(filename)

        # Check if photos are from Claude_Posts (skip caption)
        skip_caption = first_photo.get('_skip_caption', False)
        source_album = first_photo.get('_source_album', 'instagram_queue')
        photo_album_key = first_photo.get('_album_key', queue_album['AlbumKey'] if queue_album else None)

        # Get caption and hashtags (always generate based on event type)
        caption = get_caption(event_type)
        hashtags = HASHTAGS.get(event_type, HASHTAGS['default'])

        # Build content type string with orientation
        orientation_emoji = "📐" if orientation_type in ('portrait', 'landscape') else ""
        orientation_label = orientation_type.upper() if orientation_type in ('portrait', 'landscape') else ""

        if is_carousel:
            content_type = f"🎠 Carousel ({len(event_photos)} photos)"
            if orientation_label:
                content_type += f" | {orientation_emoji} {orientation_label}"
            content_icon = "🎠"
            single_warning = ""
        elif is_reel:
            content_type = "🎬 Reel"
            content_icon = "🎬"
            single_warning = ""
        else:
            content_type = "📷 Single"
            if orientation_label:
                content_type += f" | {orientation_emoji} {orientation_label}"
            content_icon = "📷"
            # WARNING: Single photos get less reach than carousels!
            single_warning = "\n⚠️ *SINGLE PHOTO* - Carousels get 2x reach! Add more photos if possible."

        print(f"   {idx}. {content_icon} {event_name} - {orientation_label or event_type}")

        # Send individual message for this event
        try:
            # Caption hooks for first 3 seconds (Instagram Best Practice)
            caption_hooks = {
                'wedding': "✨ This couple's first look had us in tears...",
                'family': "✨ This family session was pure magic...",
                'newborn': "✨ 10 days new and already stealing hearts...",
                'birthday': "✨ This birthday party was unforgettable...",
                'sweet16': "✨ Sweet 16 perfection...",
                'maternity': "✨ Glowing and gorgeous...",
                'default': "✨ Another beautiful moment captured..."
            }
            hook = caption_hooks.get(event_type, caption_hooks['default'])

            # Source album indicator
            source_label = "📝 *EDITED COVER*" if source_album == 'claude_posts' else "📷 *Raw Photo*"
            caption_preview = f"_{caption[:80]}..._"

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{idx}. {event_name}*\n{content_type} | Type: {event_type.upper()}\n{source_label}{single_warning}"
                    }
                },
                {
                    "type": "image",
                    "image_url": media_url,
                    "alt_text": event_name
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"*Hook:* {hook}\n*Caption:* {caption_preview}"}]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "React ✅ to post this"}
                }
            ]

            result = client.chat_postMessage(
                channel=SLACK_CHANNEL_ID,
                text=f"{content_icon} {idx}. {event_name}",
                blocks=blocks
            )

            # Prepare item data
            item_data = {
                'index': idx,
                'event_name': event_name,
                'event_type': event_type,
                'is_carousel': is_carousel,
                'is_reel': is_reel,
                'caption': caption,
                'hashtags': hashtags,
                'image_url': media_url,
                'slack_ts': result['ts'],
                'album_key': photo_album_key,  # Use correct album key from photo
                'source_album': source_album,  # Track source for reference
                'skip_caption': skip_caption,  # Track if caption was skipped
                'orientation_type': orientation_type
            }

            if is_carousel:
                # Get all image URLs and keys for carousel
                # Photos already split by orientation, no further sorting needed

                image_urls = []
                image_keys = []
                all_filenames = []

                for photo in event_photos:
                    pk = photo.get('ImageKey')
                    url = get_image_url(session, pk)
                    if url:
                        image_urls.append(url)
                        image_keys.append(pk)
                        all_filenames.append(photo.get('FileName', 'unknown'))

                item_data['image_urls'] = image_urls
                item_data['image_keys'] = image_keys
                item_data['all_filenames'] = all_filenames
                item_data['image_count'] = len(image_urls)
            else:
                item_data['image_key'] = image_key
                item_data['filename'] = filename

            pending_items.append(item_data)

        except SlackApiError as e:
            logger.error(f"Failed to send {event_name}: {e}")
            print(f"   ❌ Failed to send {event_name}")

    # Save pending queue
    with open(PENDING_QUEUE_FILE, 'w') as f:
        json.dump(pending_items, f, indent=2)

    logger.info(f"Queue sent: {len(pending_items)} items")
    print(f"\n✅ Sent {len(pending_items)} items to Slack")
    print("   React with ✅ to items you want to post")
    print("   Then run: python instagram_approval.py --check-queue")


def do_check_queue(dry_run=False):
    """Check queue items for reactions and post approved ones."""
    logger.info("=" * 60)
    logger.info(f"CHECK QUEUE START {'(DRY RUN)' if dry_run else ''}")
    logger.info("=" * 60)

    if not PENDING_QUEUE_FILE.exists():
        logger.info("No pending queue")
        print("📭 No pending queue - run --queue first")
        return

    # Load pending queue
    with open(PENDING_QUEUE_FILE) as f:
        pending_items = json.load(f)

    logger.info(f"Checking {len(pending_items)} queue items")
    print(f"\n🔍 Checking {len(pending_items)} queue items...")

    approved = []
    skipped = []
    waiting = []

    for item in pending_items:
        event_name = item.get('event_name', 'unknown')
        message_ts = item.get('slack_ts')

        if not message_ts:
            continue

        try:
            reaction = check_slack_reaction(message_ts)

            if reaction == 'approve':
                approved.append(item)
                print(f"   ✅ {event_name} - APPROVED")
            elif reaction == 'skip':
                skipped.append(item)
                print(f"   ❌ {event_name} - SKIPPED")
            else:
                waiting.append(item)
                print(f"   ⏳ {event_name} - waiting")
        except Exception as e:
            logger.error(f"Error checking {event_name}: {e}")
            waiting.append(item)

    print(f"\n📊 Results: {len(approved)} approved, {len(skipped)} skipped, {len(waiting)} waiting")

    # Post approved items
    if approved:
        if dry_run:
            print(f"\n🧪 DRY RUN - Would post {len(approved)} items:")
            for item in approved:
                event_name = item.get('event_name', 'unknown')
                content_type = "carousel" if item.get('is_carousel') else ("reel" if item.get('is_reel') else "single")
                print(f"   📤 {event_name} ({content_type})")
                print(f"      Caption: {item.get('caption', '')[:40]}...")
            print(f"\n✅ DRY RUN complete - no posts made, queue unchanged")
            return

        print(f"\n🚀 Posting {len(approved)} approved items...")
        post_delay = 30  # Seconds between posts (safe for Instagram, looks natural)

        for i, item in enumerate(approved):
            event_name = item.get('event_name', item.get('filename', 'unknown'))
            is_carousel = item.get('is_carousel', False)
            is_reel = item.get('is_reel', False)

            content_type = "carousel" if is_carousel else ("reel" if is_reel else "single")
            logger.info(f"Posting {content_type}: {event_name}")
            print(f"\n   📤 Posting: {event_name}")

            try:
                poster = InstagramPoster()

                if is_carousel:
                    # Check if mixed orientations - normalize if needed
                    orientation_analysis = item.get('orientation_analysis', {})
                    image_urls = item['image_urls']

                    if orientation_analysis.get('is_mixed'):
                        # Normalize to 4:5 canvas with auto-color padding
                        image_urls = normalize_carousel_for_posting(
                            image_urls,
                            event_name,
                            orientation_analysis
                        )

                    # Generate carousel cover with text overlay (Instagram Best Practice)
                    # Cover has: RSQUARE STUDIOS branding + hook text + SWIPE prompt
                    print(f"      Generating text cover...")
                    try:
                        cover_url = create_and_upload_carousel_cover(
                            first_image_url=image_urls[0],
                            event_name=event_name,
                            event_type=item.get('event_type', 'default')
                        )
                        if cover_url:
                            # Insert cover as first image
                            image_urls = [cover_url] + image_urls
                            logger.info(f"Cover generated and added as first slide")
                            print(f"      Cover added as slide 1")
                        else:
                            logger.warning(f"Cover generation failed - using photos only")
                            print(f"      Cover failed - using photos only")
                    except Exception as cover_err:
                        logger.warning(f"Cover generation error: {cover_err}")
                        print(f"      Cover error: {cover_err} - using photos only")

                    result = poster.post_carousel(
                        image_urls,
                        item['caption'],
                        item['hashtags']
                    )
                elif is_reel:
                    result = poster.post_reel(
                        item['image_url'],
                        item['caption'],
                        item['hashtags']
                    )
                else:
                    result = poster.post_single_image(
                        item['image_url'],
                        item['caption'],
                        item['hashtags']
                    )

                if result.get('success'):
                    post_id = result.get('post_id')
                    logger.info(f"SUCCESS: {event_name} -> {post_id}")
                    print(f"      🎉 Posted! ID: {post_id}")

                    # Generate Story templates for this post (v1.0: magazine, duo, trio)
                    try:
                        # Get all photo URLs (for duo/trio templates)
                        if is_carousel:
                            photo_urls = item.get('image_urls', [])
                        else:
                            photo_urls = [item.get('image_url')] if item.get('image_url') else []

                        if photo_urls:
                            print(f"      📱 Generating Story templates (v1.0)...")
                            story_paths = generate_story_for_post(
                                photo_urls=photo_urls,
                                event_name=event_name,
                                event_type=item.get('event_type', 'default')
                            )
                            if story_paths:
                                logger.info(f"Stories generated: {len(story_paths)} templates")
                    except Exception as story_err:
                        logger.warning(f"Story generation failed: {story_err}")
                        print(f"      ⚠️ Story generation failed: {story_err}")

                    # Remove from SmugMug queue
                    if is_carousel:
                        for image_key in item.get('image_keys', []):
                            remove_from_queue(image_key, item['album_key'])
                    else:
                        remove_from_queue(item.get('image_key'), item['album_key'])

                    # Log post
                    log_entry = {
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'time': datetime.now().isoformat(),
                        'success': True,
                        'post_id': post_id,
                        'event_type': item['event_type'],
                        'is_carousel': is_carousel,
                        'is_reel': is_reel
                    }
                    if is_carousel:
                        log_entry['event_name'] = event_name
                        log_entry['image_count'] = item.get('image_count', 0)
                    else:
                        log_entry['filename'] = event_name
                    log_post(log_entry)

                    send_slack_result(True, event_name, post_id)
                else:
                    error = result.get('error', 'Unknown error')
                    logger.error(f"FAILED: {event_name} - {error}")
                    print(f"      ❌ Failed: {error}")
                    send_slack_result(False, event_name, error=error)

            except Exception as e:
                logger.error(f"Error posting {event_name}: {e}")
                logger.error(traceback.format_exc())
                print(f"      ❌ Error: {e}")
                send_slack_result(False, event_name, error=str(e))

            # Delay between posts (skip delay after last post)
            if i < len(approved) - 1:
                print(f"      ⏱️  Waiting {post_delay}s before next post...")
                time.sleep(post_delay)

    # Remove skipped items from SmugMug queue
    if skipped:
        print(f"\n🗑️ Removing {len(skipped)} skipped items from queue...")
        for item in skipped:
            event_name = item.get('event_name', item.get('filename', 'unknown'))
            if item.get('is_carousel'):
                for image_key in item.get('image_keys', []):
                    remove_from_queue(image_key, item['album_key'])
            else:
                remove_from_queue(item.get('image_key'), item['album_key'])
            logger.info(f"Removed skipped: {event_name}")

    # Update pending queue (keep only waiting items)
    if waiting:
        with open(PENDING_QUEUE_FILE, 'w') as f:
            json.dump(waiting, f, indent=2)
        print(f"\n⏳ {len(waiting)} items still waiting for reaction")
    else:
        # All items processed - clean up
        PENDING_QUEUE_FILE.unlink()
        print("\n✅ All queue items processed!")


def do_clear_queue():
    """Clear pending queue file (reset)."""
    if PENDING_QUEUE_FILE.exists():
        PENDING_QUEUE_FILE.unlink()
        print("✅ Pending queue cleared")
    else:
        print("📭 No pending queue to clear")

    if PENDING_FILE.exists():
        PENDING_FILE.unlink()
        print("✅ Pending post cleared")


def main():
    if '--preview' in sys.argv:
        do_preview()
    elif '--queue' in sys.argv:
        do_queue()
    # ===== DRY RUN (TEST) COMMANDS =====
    elif '--test-queue' in sys.argv:
        print("🧪 TEST MODE - Checking reactions (will NOT post to Instagram)")
        print("=" * 60)
        do_check_queue(dry_run=True)
    elif '--test' in sys.argv:
        print("🧪 TEST MODE - Checking reaction (will NOT post to Instagram)")
        print("=" * 60)
        do_check(dry_run=True)
    # ===== REGULAR POST COMMANDS =====
    elif '--post-queue' in sys.argv:
        print("📤 POST MODE - Will post approved items to Instagram")
        print("=" * 60)
        do_check_queue(dry_run=False)
    elif '--post' in sys.argv and '--preview' not in sys.argv:
        print("📤 POST MODE - Will post if approved")
        print("=" * 60)
        do_check(dry_run=False)
    # ===== LEGACY COMMANDS (with --dry-run flag support) =====
    elif '--check' in sys.argv:
        dry_run = '--dry-run' in sys.argv
        if dry_run:
            print("🧪 DRY RUN MODE - Will NOT post to Instagram")
            print("=" * 50)
        do_check(dry_run=dry_run)
    elif '--auto' in sys.argv:
        dry_run = '--dry-run' in sys.argv
        if dry_run:
            print("🧪 DRY RUN MODE - Will NOT post to Instagram")
            print("=" * 50)
        do_auto(dry_run=dry_run)
    elif '--check-queue' in sys.argv:
        dry_run = '--dry-run' in sys.argv
        if dry_run:
            print("🧪 DRY RUN MODE - Will NOT post to Instagram")
            print("=" * 50)
        do_check_queue(dry_run=dry_run)
    elif '--clear' in sys.argv:
        do_clear_queue()
    elif '--analytics' in sys.argv:
        update_analytics()
        print(get_analytics_summary())
    elif '--summary' in sys.argv:
        print(get_analytics_summary())
    else:
        print("Usage:")
        print("")
        print("  QUEUE MODE (recommended):")
        print("  --queue         Send ALL items to Slack for review")
        print("  --test-queue    🧪 Check reactions (DRY RUN - no posting)")
        print("  --post-queue    📤 Post all approved items to Instagram")
        print("  --clear         Clear pending queue (reset)")
        print("")
        print("  SINGLE MODE:")
        print("  --preview       Send next item preview to Slack")
        print("  --test          🧪 Check reaction (DRY RUN - no posting)")
        print("  --post          📤 Post if approved")
        print("")
        print("  ANALYTICS:")
        print("  --analytics     Update & show engagement stats")
        print("  --summary       Show existing analytics")
        print("")
        print("  WORKFLOW:")
        print("  1. --queue        → Send previews to Slack")
        print("  2. React in Slack → ✅ to approve, ❌ to skip")
        print("  3. --test-queue   → Verify reactions (safe)")
        print("  4. --post-queue   → Actually post to Instagram")


if __name__ == '__main__':
    main()
