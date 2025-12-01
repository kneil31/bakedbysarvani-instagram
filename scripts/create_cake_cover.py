#!/usr/bin/env python3
"""
Create carousel cover for BakedBySarvani cakes.

VERSION: 2.0 (2025-11-29)
UPDATES:
- Added professional color methodology (Vibrant.js palette extraction)
- Smart text color detection based on cake photo
- WCAG 4.5:1 contrast ratio validation
- Shadow-matched gradient colors from photo
- Synced with Instagram_AutoPoster color system
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import sys
import numpy as np

# Import professional color methodology from Instagram_AutoPoster
INSTAGRAM_SCRIPTS = Path("/Users/ram/Documents/2025 - Rsquare/Rsquare-Scripts/Photography/Instagram_AutoPoster/scripts")
sys.path.insert(0, str(INSTAGRAM_SCRIPTS))

try:
    from carousel_cover_generator import (
        extract_vibrant_palette,
        get_color_temperature,
        get_contrast_ratio,
        get_luminance,
        analyze_image_palette,
    )
    COLOR_METHODOLOGY_AVAILABLE = True
except ImportError:
    COLOR_METHODOLOGY_AVAILABLE = False
    print("Warning: Color methodology not available. Using fallback colors.")

# Paths
CAKE_FOLDER = Path("/Users/ram/Documents/2025 - Rsquare/Monika /Cake Edits/Edits-1124")
OUTPUT_FOLDER = Path(__file__).parent.parent / "output" / "covers"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# Fonts (macOS system fonts)
SCRIPT_FONT = '/System/Library/Fonts/Supplemental/SnellRoundhand.ttc'
DISPLAY_FONT = '/System/Library/Fonts/Supplemental/Futura.ttc'
SANS_FONT = '/System/Library/Fonts/Avenir.ttc'

# Fallback Colors (used when methodology unavailable)
WARM_GOLD = (255, 215, 180)
CHOCOLATE_BROWN = (60, 30, 20)


def get_smart_cake_colors(img):
    """
    Get optimal text and gradient colors for cake photos.

    Uses professional colorist methodology:
    - Vibrant.js-style palette extraction
    - Temperature detection (warm chocolates, cool pastels)
    - WCAG contrast validation
    - Shadow-matched gradients

    Returns:
        tuple: (text_color, accent_color, gradient_color)
    """
    if not COLOR_METHODOLOGY_AVAILABLE:
        # Fallback to preset colors
        return WARM_GOLD, (255, 255, 255), CHOCOLATE_BROWN

    # Extract palette from cake photo
    palette = extract_vibrant_palette(img)
    temperature = get_color_temperature(palette.get('vibrant', (180, 120, 80)))

    # Get the bottom area where text will be
    width, height = img.size
    bottom_area = img.crop((0, int(height * 0.7), width, height))
    arr = np.array(bottom_area)
    brightness = np.mean(arr)

    # Choose colors based on cake photo
    if temperature == 'warm':
        # Chocolate, caramel, golden cakes
        text_color = (255, 235, 210)  # Warm cream
        accent_color = (255, 255, 255)  # White for contrast
        gradient_base = palette.get('dark_muted', (60, 30, 20))
    elif temperature == 'cool':
        # Pastel, blueberry, strawberry cakes
        text_color = (255, 240, 245)  # Soft pink-white
        accent_color = (255, 255, 255)
        gradient_base = palette.get('dark_muted', (40, 30, 50))
    else:
        # Neutral (vanilla, white cakes)
        text_color = (255, 245, 235)
        accent_color = (255, 255, 255)
        gradient_base = palette.get('dark_muted', (50, 40, 35))

    # Validate contrast for text readability
    bg_color = tuple(np.mean(arr, axis=(0, 1)).astype(int))

    if get_contrast_ratio(text_color, gradient_base) < 4.5:
        # Boost if contrast is too low
        text_color = (255, 255, 255)

    return text_color, accent_color, gradient_base

def create_cover(photo_path, tagline="chocolate heaven", cake_type="FERRERO ROCHER", output_name="cover"):
    """
    Create a carousel cover with text overlay.

    Uses professional color methodology:
    - Smart text colors based on cake photo
    - Shadow-matched gradient from photo
    - WCAG contrast validation
    """

    # Open image
    img = Image.open(photo_path).convert('RGB')
    width, height = img.size

    # Resize to Instagram 4:5 (1080x1350)
    target_w, target_h = 1080, 1350

    # Calculate crop to fit 4:5
    ratio = target_w / target_h
    img_ratio = width / height

    if img_ratio > ratio:
        # Image is wider - crop sides
        new_w = int(height * ratio)
        left = (width - new_w) // 2
        img = img.crop((left, 0, left + new_w, height))
    else:
        # Image is taller - crop top/bottom (keep upper 40% for cake top)
        new_h = int(width / ratio)
        top = int((height - new_h) * 0.3)  # Keep upper portion
        img = img.crop((0, top, width, top + new_h))

    img = img.resize((target_w, target_h), Image.LANCZOS)

    # Get smart colors from photo using professional methodology
    text_color, accent_color, gradient_base = get_smart_cake_colors(img)
    print(f"   Color analysis: text={text_color}, gradient={gradient_base}")

    # Create draw object
    draw = ImageDraw.Draw(img)

    # Add gradient at bottom using shadow-matched color from photo
    gradient = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)

    gradient_height = 500
    for y in range(target_h - gradient_height, target_h):
        progress = (y - (target_h - gradient_height)) / gradient_height
        alpha = int(200 * progress)
        # Use shadow-matched gradient color from photo
        gradient_draw.line([(0, y), (target_w, y)], fill=(*gradient_base[:3], alpha))

    img = img.convert('RGBA')
    img = Image.alpha_composite(img, gradient)
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        script_font = ImageFont.truetype(SCRIPT_FONT, 55)
        display_font = ImageFont.truetype(DISPLAY_FONT, 48)
        brand_font = ImageFont.truetype(SANS_FONT, 18)
    except:
        script_font = ImageFont.load_default()
        display_font = ImageFont.load_default()
        brand_font = ImageFont.load_default()

    # Draw tagline (script font) - using smart text color
    tagline_bbox = draw.textbbox((0, 0), tagline, font=script_font)
    tagline_w = tagline_bbox[2] - tagline_bbox[0]
    tagline_x = (target_w - tagline_w) // 2
    tagline_y = target_h - 280
    draw.text((tagline_x, tagline_y), tagline, font=script_font, fill=text_color)

    # Draw cake type (display font) - using accent color
    cake_bbox = draw.textbbox((0, 0), cake_type, font=display_font)
    cake_w = cake_bbox[2] - cake_bbox[0]
    cake_x = (target_w - cake_w) // 2
    cake_y = target_h - 200
    draw.text((cake_x, cake_y), cake_type, font=display_font, fill=accent_color)

    # Draw brand name (spaced letters) - using smart text color
    brand = "B A K E D   B Y   S A R V A N I"
    brand_bbox = draw.textbbox((0, 0), brand, font=brand_font)
    brand_w = brand_bbox[2] - brand_bbox[0]
    brand_x = (target_w - brand_w) // 2
    brand_y = target_h - 40
    draw.text((brand_x, brand_y), brand, font=brand_font, fill=text_color)

    # Save
    output_path = OUTPUT_FOLDER / f"{output_name}.jpg"
    img = img.convert('RGB')
    img.save(output_path, 'JPEG', quality=95)
    print(f"✅ Created: {output_path}")
    return output_path


if __name__ == '__main__':
    # Get first cake photo
    photos = list(CAKE_FOLDER.glob("*.jpg"))
    if not photos:
        print("No photos found!")
        sys.exit(1)
    
    # Create covers with different taglines
    taglines = [
        ("chocolate heaven", "cover_1"),
        ("sweet celebrations", "cover_2"),
        ("layers of love", "cover_3"),
    ]
    
    for i, photo in enumerate(photos[:3]):
        tagline, name = taglines[i] if i < len(taglines) else ("baked with love", f"cover_{i+1}")
        create_cover(photo, tagline, name)
    
    print(f"\n🎂 Created {min(len(photos), 3)} covers in: {OUTPUT_FOLDER}")
