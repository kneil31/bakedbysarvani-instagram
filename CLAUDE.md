# CLAUDE.md - BakedBySarvani Instagram

**Project**: Instagram automation for @bakedbysarvani (cakes & desserts in Dallas)

**Status**: ✅ COVERS + STORIES + REELS COMPLETE

---

## ⚠️ MANDATORY: Color Methodology (ALWAYS APPLY)

**This project shares the same professional color methodology as Instagram_AutoPoster.**

All cover generation, story templates, and visual content MUST use:

1. **Vibrant.js-style palette extraction** - 6 swatches from cake photos
2. **Temperature detection** - warm (chocolate/caramel) vs cool (pastels/berries)
3. **Shadow-matched gradients** - extracted from photo's actual shadows
4. **WCAG 4.5:1 contrast validation** - ensures text readability
5. **5K quality images** when available from SmugMug

**Import from shared module:**
```python
from carousel_cover_generator import (
    extract_vibrant_palette,
    get_color_temperature,
    get_contrast_ratio,
)
```

**Color decisions are automatic - never hardcode colors for new photos.**

See: `Instagram_AutoPoster/CLAUDE.md` → "Color System (Professional Colorist Approach)" for full documentation.

---

## What This Project Does

Same workflow as Rsquare Studios but for cake/dessert content:

1. Photos from local folder or SmugMug "Sarvani Queue" album
2. Generate carousel covers with VCLICKS-style frame design
3. Generate stories and reels
4. Post to Instagram via API

---

## Setup Checklist

- [ ] Convert @bakedbysarvani to Business Account
- [ ] Create Facebook Page "Baked by Sarvani"
- [ ] Link Instagram to Facebook Page
- [ ] Get Meta API Access Token
- [ ] Create SmugMug albums
- [ ] Add bakedbysarvani logo/watermark

---

## Carousel Cover Generator (VCLICKS Frame Style) ✅

### Design Specifications

| Element | Font | Size | Color |
|---------|------|------|-------|
| **Title** | Georgia | 50pt | Chocolate Brown (55, 35, 25) |
| **Subtitle** | Avenir | 28pt | Gold (150, 120, 80) |
| **Brand** | Avenir | 16pt | Warm Brown (130, 105, 75) |
| **Background** | - | - | Cream (250, 245, 238) |

### Layout

```
┌─────────────────────────────────┐
│         Ferrero Rocher          │  ← Title (Georgia 50pt, y=48)
│                                 │
│  ┌───────────────────────────┐  │
│  │                           │  │
│  │                           │  │
│  │      [CAKE PHOTO]         │  │  ← Photo with 40px side margins
│  │                           │  │     140px top, 180px bottom
│  │                           │  │
│  └───────────────────────────┘  │
│                                 │
│     chocolate indulgence        │  ← Subtitle (y = height - 140)
│  B  A  K  E  D    B  Y    S...  │  ← Brand (y = height - 95)
└─────────────────────────────────┘
     1080 x 1350 (Instagram 4:5)
```

### Brand Text Spacing

```python
# Wide letter spacing for elegant look
brand = "B    A    K    E    D        B    Y        S    A    R    V    A    N    I"
# 4 spaces between letters, 8 spaces between words
```

### Photo Centering (Shift Values)

| Photo | Shift | Notes |
|-------|-------|-------|
| Edits.jpg | 0 | Centered |
| Edits-2.jpg | +150 | Shift right (cake was left) |
| Edits-3.jpg | -350 | Shift left (cake was right) |
| Edits-4.jpg | 0 | Centered |

### Quick Command

```bash
cd "/Users/ram/Documents/2025 - Rsquare/Rsquare-Scripts/Photography/BakedBySarvani_Instagram/scripts"

# Uses Instagram AutoPoster venv (has PIL)
"/Users/ram/Documents/2025 - Rsquare/Rsquare-Scripts/Photography/Instagram_AutoPoster/venv/bin/python" cover_generator.py
```

### Output Location

```
output/covers/
├── FINAL_1.jpg  ← Ferrero Rocher
├── FINAL_2.jpg  ← Chocolate Dream
├── FINAL_3.jpg  ← Birthday Cake
└── FINAL_4.jpg  ← Sweet Delight
```

### Photo Source

```
/Users/ram/Documents/2025 - Rsquare/Monika /Cake Edits/Edits-1124/
├── Monika Cake --Edits.jpg
├── Monika Cake --Edits-2.jpg
├── Monika Cake --Edits-3.jpg
└── Monika Cake --Edits-4.jpg
```

---

## SmugMug Albums (To Create)

```
Sarvani-Queue/
├── Sarvani Queue      ← Raw cake photos
├── Sarvani-Posts      ← Edited covers with text
└── Sarvani-Stories    ← Story templates
```

---

## Content Types

| Type | Detection Keywords | Example |
|------|-------------------|---------|
| birthday_cake | birthday, bday | "Sweeter than the wish you made" |
| wedding_cake | wedding, bridal | "Love, layered in sweetness" |
| custom_cake | custom, order | "Made with love, just for you" |
| cupcakes | cupcake, mini | "Little treats, big smiles" |
| baby_shower | baby, shower | "Something sweet is on the way" |
| anniversary | anniversary | "Another year of sweetness" |
| graduation | graduation, grad | "The sweetest achievement" |
| default | - | "Baked with love" |

---

## Captions (Cake/Dessert Style)

```python
CAPTIONS = {
    'birthday_cake': [
        "Sweeter than the wish you made.",
        "Another year, another layer of sweetness.",
        "Birthday calories don't count.",
        "Making wishes come true, one slice at a time.",
    ],
    'wedding_cake': [
        "Love, layered in sweetness.",
        "The sweetest part of forever.",
        "A love story, in cake form.",
        "Tiers of joy.",
    ],
    'custom_cake': [
        "Made with love, just for you.",
        "Your vision, our creation.",
        "Every cake tells a story.",
        "Crafted to perfection.",
    ],
    'cupcakes': [
        "Little treats, big smiles.",
        "Happiness in every bite.",
        "Small but mighty delicious.",
        "Bite-sized bliss.",
    ],
    'default': [
        "Baked with love.",
        "Fresh from the oven.",
        "Sweetness delivered.",
        "Every bite is a celebration.",
    ],
}
```

---

## Hashtags (Dallas Bakery)

```python
HASHTAGS = {
    'birthday_cake': '#DallasBakery #BirthdayCake #CustomCakes #DallasCakes #CakeArt #DFWBakery #BirthdayTreats #CakesOfInstagram',
    'wedding_cake': '#DallasWeddingCake #WeddingCake #DFWWedding #BridalCake #WeddingDessert #DallasBride #CakeDesign',
    'custom_cake': '#CustomCakes #DallasBakery #CakeArtist #DFWCakes #DesignerCakes #CakesOfDallas #EdibleArt',
    'cupcakes': '#DallasCupcakes #Cupcakes #DFWBakery #MiniCakes #CupcakeLove #DallasDesserts #SweetTreats',
    'default': '#DallasBakery #BakedBySarvani #DallasCakes #HomeBaked #DFWDesserts #CakesOfInstagram #DallasFood',
}
```

---

## Quick Commands

```bash
cd "/Users/ram/Documents/2025 - Rsquare/Rsquare-Scripts/Photography/BakedBySarvani_Instagram/scripts"

# Send queue to Slack
../venv/bin/python instagram_approval.py --queue

# Check approvals and post
../venv/bin/python instagram_approval.py --check-queue

# Generate story
../venv/bin/python story_generator.py --photo cake.jpg --all --caption "Birthday Cake"
```

---

## Configuration

```
scripts/.env
├── IG_ACCESS_TOKEN     # Page Access Token (after setup)
├── IG_PAGE_ID          # Facebook Page ID
├── SMUGMUG_API_KEY     # Same as rsquare
├── SMUGMUG_API_SECRET  # Same as rsquare
├── SLACK_BOT_TOKEN     # New channel for bakedbysarvani
├── SLACK_CHANNEL_ID    # #sarvani-instagram
└── SLACK_WEBHOOK_URL
```

---

## Posting Schedule (Recommended)

| Day | Time | Content |
|-----|------|---------|
| Mon | 11 AM | Cake of the week |
| Wed | 12 PM | Process/BTS video |
| Fri | 11 AM | Customer order showcase |
| Sat | 10 AM | Weekend special |

---

## Logo/Watermark

Add logo files:
- `assets/watermarks/sarvani_white.png`
- `assets/watermarks/sarvani_black.png`

---

---

## Stories Generated ✅

| Type | Count | Description |
|------|-------|-------------|
| Magazine | 4 | Full photo with blurred bg, brand at bottom |
| Duo | 2 | 2 photos stacked vertically |
| Trio | 2 | 3 photos stacked vertically |

**Output:** `output/stories/STORY_*.jpg`

---

## Video Reel ✅

**Source:** 14 cake videos from Akshaya-Randy Seemantham event
```
Cake/RSMI9738.MP4 - RSMI9751.MP4 (14 files)
```

**Processing:**
- Center crop (9:16 from 16:9 source)
- Cinematic color grade
- 2 seconds per clip
- 24 seconds total

**Output:** `output/reels/CAKE_REEL_FRESH.mp4`

---

## Session History

**2025-11-29 (Morning)**: Created 4 carousel covers with VCLICKS frame design
- Font: Georgia for titles, Avenir for subtitles
- Colors: Cream bg, chocolate brown/gold text
- Photo centering with shift adjustments
- Output: FINAL_1.jpg through FINAL_4.jpg

**2025-11-29 (Afternoon)**: Created stories and video reel
- 8 Instagram stories (Magazine, Duo, Trio templates)
- Video reel from 14 cake clips with color grading
- Output: output/stories/ and output/reels/

---

**Last Updated**: 2025-11-29
**Account**: @bakedbysarvani
**Status**: All content generated - ready for posting
**Color System**: Synced with Instagram_AutoPoster (v2.0)
