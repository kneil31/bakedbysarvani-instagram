#!/usr/bin/env python3
"""
Instagram Auto-Poster via Official Meta Graph API
==================================================

Posts to Instagram automatically using the official API.
Supports: Single images, Carousels, Hashtags in caption.

Usage:
    # Test connection
    python instagram_poster.py --test

    # Post single image
    python instagram_poster.py --post --url "https://smugmug.com/photo.jpg" --caption "My caption"

    # Post carousel
    python instagram_poster.py --carousel --urls "url1,url2,url3" --caption "My caption"

    # Post with hashtags in caption
    python instagram_poster.py --post --url "..." --caption "..." --hashtags "#tag1 #tag2"
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time
import argparse

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


class InstagramPoster:
    """Instagram Graph API wrapper for automated posting."""

    def __init__(self):
        self.access_token = os.getenv('IG_ACCESS_TOKEN')
        self.page_id = os.getenv('IG_PAGE_ID')  # Facebook Page ID
        self.ig_account_id = None
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

        if not self.access_token:
            raise ValueError("IG_ACCESS_TOKEN not found in environment")

    def get_instagram_account_id(self):
        """Get the Instagram Business Account ID from Facebook Page."""
        if self.ig_account_id:
            return self.ig_account_id

        print("🔍 Finding Instagram Business Account ID...")

        # If we have Page ID, query directly (Page Access Token approach)
        if self.page_id:
            url = f"{self.base_url}/{self.page_id}"
            params = {
                'fields': 'instagram_business_account,name',
                'access_token': self.access_token
            }
            response = requests.get(url, params=params)

            if response.status_code != 200:
                error = response.json().get('error', {})
                print(f"❌ Error: {error.get('message', 'Unknown error')}")
                return None

            data = response.json()
            page_name = data.get('name', 'Unknown')
            print(f"   Facebook Page: {page_name}")

            if 'instagram_business_account' in data:
                self.ig_account_id = data['instagram_business_account']['id']
                print(f"✅ Found Instagram Account ID: {self.ig_account_id}")
                return self.ig_account_id
            else:
                print("❌ No Instagram Business Account linked to this Page")
                print("   Link Instagram to Facebook Page:")
                print("   Instagram App → Profile → Edit Profile → Page → Select your Page")
                return None

        # Fallback: User Access Token approach (queries me/accounts)
        url = f"{self.base_url}/me/accounts"
        params = {'access_token': self.access_token}
        response = requests.get(url, params=params)

        if response.status_code != 200:
            error = response.json().get('error', {})
            print(f"❌ Error: {error.get('message', 'Unknown error')}")
            return None

        pages = response.json().get('data', [])

        if not pages:
            print("❌ No Facebook Pages found")
            return None

        # For each page, check if it has an Instagram account
        for page in pages:
            page_id = page['id']
            page_token = page['access_token']

            ig_url = f"{self.base_url}/{page_id}"
            ig_params = {
                'fields': 'instagram_business_account',
                'access_token': page_token
            }

            ig_response = requests.get(ig_url, params=ig_params)
            ig_data = ig_response.json()

            if 'instagram_business_account' in ig_data:
                self.ig_account_id = ig_data['instagram_business_account']['id']
                print(f"✅ Found Instagram Account ID: {self.ig_account_id}")
                return self.ig_account_id

        print("❌ No Instagram Business Account found")
        print("   Make sure your Instagram is connected to a Facebook Page")
        print("   Go to: Instagram App → Settings → Account → Linked Accounts → Facebook")
        return None

    def get_account_info(self):
        """Get Instagram account information."""
        if not self.ig_account_id:
            self.get_instagram_account_id()

        if not self.ig_account_id:
            return None

        url = f"{self.base_url}/{self.ig_account_id}"
        params = {
            'fields': 'id,username,name,profile_picture_url,followers_count,media_count',
            'access_token': self.access_token
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None

    def post_single_image(self, image_url, caption, hashtags=None):
        """
        Post a single image to Instagram.

        Args:
            image_url: Publicly accessible URL to the image (must be JPEG)
            caption: Caption for the post
            hashtags: Optional hashtags to append to caption

        Returns:
            dict with post_id and success status
        """
        if not self.ig_account_id:
            self.get_instagram_account_id()

        if not self.ig_account_id:
            return {'success': False, 'error': 'No Instagram account found'}

        # Append hashtags to caption if provided
        full_caption = caption
        if hashtags:
            full_caption = f"{caption}\n\n.\n.\n.\n{hashtags}"

        print(f"\n📸 Posting single image to Instagram...")
        print(f"   Image: {image_url[:60]}...")
        print(f"   Caption: {caption[:50]}...")
        if hashtags:
            print(f"   Hashtags: {hashtags[:50]}...")

        # Step 1: Create media container
        container_url = f"{self.base_url}/{self.ig_account_id}/media"
        container_params = {
            'image_url': image_url,
            'caption': full_caption,
            'access_token': self.access_token
        }

        container_response = requests.post(container_url, data=container_params)

        if container_response.status_code != 200:
            error = container_response.json().get('error', {})
            print(f"❌ Failed to create media container: {error.get('message')}")
            return {'success': False, 'error': error.get('message')}

        container_id = container_response.json()['id']
        print(f"✅ Media container created: {container_id}")

        # Step 2: Wait for media to be ready
        time.sleep(3)

        # Step 3: Publish the container
        publish_url = f"{self.base_url}/{self.ig_account_id}/media_publish"
        publish_params = {
            'creation_id': container_id,
            'access_token': self.access_token
        }

        publish_response = requests.post(publish_url, data=publish_params)

        if publish_response.status_code != 200:
            error = publish_response.json().get('error', {})
            print(f"❌ Failed to publish: {error.get('message')}")
            return {'success': False, 'error': error.get('message')}

        post_id = publish_response.json()['id']
        print(f"🎉 SUCCESS! Post published!")
        print(f"   Post ID: {post_id}")

        return {
            'success': True,
            'post_id': post_id,
            'timestamp': datetime.now().isoformat()
        }

    def post_reel(self, video_url, caption, hashtags=None, cover_url=None):
        """
        Post a Reel (short video) to Instagram.

        Args:
            video_url: Publicly accessible URL to the video (MP4, max 15 min)
            caption: Caption for the reel
            hashtags: Optional hashtags to append to caption
            cover_url: Optional thumbnail image URL

        Returns:
            dict with post_id and success status
        """
        if not self.ig_account_id:
            self.get_instagram_account_id()

        if not self.ig_account_id:
            return {'success': False, 'error': 'No Instagram account found'}

        # Append hashtags to caption if provided
        full_caption = caption
        if hashtags:
            full_caption = f"{caption}\n\n.\n.\n.\n{hashtags}"

        print(f"\n🎬 Posting Reel to Instagram...")
        print(f"   Video: {video_url[:60]}...")
        print(f"   Caption: {caption[:50]}...")
        if hashtags:
            print(f"   Hashtags: {hashtags[:50]}...")

        # Step 1: Create media container for reel
        container_url = f"{self.base_url}/{self.ig_account_id}/media"
        container_params = {
            'video_url': video_url,
            'caption': full_caption,
            'media_type': 'REELS',
            'access_token': self.access_token
        }

        # Add cover image if provided
        if cover_url:
            container_params['cover_url'] = cover_url

        container_response = requests.post(container_url, data=container_params)

        if container_response.status_code != 200:
            error = container_response.json().get('error', {})
            print(f"❌ Failed to create reel container: {error.get('message')}")
            return {'success': False, 'error': error.get('message')}

        container_id = container_response.json()['id']
        print(f"✅ Reel container created: {container_id}")

        # Step 2: Wait for video to be processed (reels take longer)
        print("⏳ Processing video...")
        max_attempts = 30  # Wait up to 5 minutes
        for attempt in range(max_attempts):
            time.sleep(10)

            # Check status
            status_url = f"{self.base_url}/{container_id}"
            status_params = {
                'fields': 'status_code,status',
                'access_token': self.access_token
            }
            status_response = requests.get(status_url, params=status_params)
            status_data = status_response.json()

            status_code = status_data.get('status_code')
            print(f"   Status: {status_code} (attempt {attempt + 1}/{max_attempts})")

            if status_code == 'FINISHED':
                break
            elif status_code == 'ERROR':
                error_msg = status_data.get('status', 'Video processing failed')
                print(f"❌ Video processing error: {error_msg}")
                return {'success': False, 'error': error_msg}
        else:
            print("❌ Video processing timed out")
            return {'success': False, 'error': 'Video processing timed out'}

        # Step 3: Publish the reel
        publish_url = f"{self.base_url}/{self.ig_account_id}/media_publish"
        publish_params = {
            'creation_id': container_id,
            'access_token': self.access_token
        }

        publish_response = requests.post(publish_url, data=publish_params)

        if publish_response.status_code != 200:
            error = publish_response.json().get('error', {})
            print(f"❌ Failed to publish reel: {error.get('message')}")
            return {'success': False, 'error': error.get('message')}

        post_id = publish_response.json()['id']
        print(f"🎉 SUCCESS! Reel published!")
        print(f"   Post ID: {post_id}")

        return {
            'success': True,
            'post_id': post_id,
            'timestamp': datetime.now().isoformat()
        }

    def post_carousel(self, image_urls, caption, hashtags=None):
        """
        Post a carousel (multiple images) to Instagram.

        Args:
            image_urls: List of publicly accessible image URLs
            caption: Caption for the carousel
            hashtags: Optional hashtags to append to caption

        Returns:
            dict with post_id and success status
        """
        if not self.ig_account_id:
            self.get_instagram_account_id()

        if not self.ig_account_id:
            return {'success': False, 'error': 'No Instagram account found'}

        if len(image_urls) < 2:
            return {'success': False, 'error': 'Carousel needs at least 2 images'}

        if len(image_urls) > 10:
            return {'success': False, 'error': 'Carousel max is 10 images'}

        # Append hashtags to caption if provided
        full_caption = caption
        if hashtags:
            full_caption = f"{caption}\n\n.\n.\n.\n{hashtags}"

        print(f"\n📸 Posting carousel ({len(image_urls)} images) to Instagram...")
        if hashtags:
            print(f"   Hashtags: {hashtags[:50]}...")

        # Step 1: Create individual media containers for each image
        children_ids = []
        for i, url in enumerate(image_urls, 1):
            print(f"   Creating container {i}/{len(image_urls)}...")

            container_url = f"{self.base_url}/{self.ig_account_id}/media"
            container_params = {
                'image_url': url,
                'is_carousel_item': 'true',
                'access_token': self.access_token
            }

            response = requests.post(container_url, data=container_params)

            if response.status_code != 200:
                error = response.json().get('error', {})
                print(f"❌ Failed to create container for image {i}: {error.get('message')}")
                return {'success': False, 'error': error.get('message')}

            children_ids.append(response.json()['id'])
            time.sleep(1)  # Rate limiting

        print(f"✅ Created {len(children_ids)} media containers")

        # Step 2: Create carousel container
        time.sleep(2)
        carousel_url = f"{self.base_url}/{self.ig_account_id}/media"
        carousel_params = {
            'caption': full_caption,
            'media_type': 'CAROUSEL',
            'children': ','.join(children_ids),
            'access_token': self.access_token
        }

        carousel_response = requests.post(carousel_url, data=carousel_params)

        if carousel_response.status_code != 200:
            error = carousel_response.json().get('error', {})
            print(f"❌ Failed to create carousel: {error.get('message')}")
            return {'success': False, 'error': error.get('message')}

        carousel_id = carousel_response.json()['id']
        print(f"✅ Carousel container created: {carousel_id}")

        # Step 3: Publish carousel
        time.sleep(3)
        publish_url = f"{self.base_url}/{self.ig_account_id}/media_publish"
        publish_params = {
            'creation_id': carousel_id,
            'access_token': self.access_token
        }

        publish_response = requests.post(publish_url, data=publish_params)

        if publish_response.status_code != 200:
            error = publish_response.json().get('error', {})
            print(f"❌ Failed to publish carousel: {error.get('message')}")
            return {'success': False, 'error': error.get('message')}

        post_id = publish_response.json()['id']
        print(f"🎉 SUCCESS! Carousel published!")
        print(f"   Post ID: {post_id}")

        return {
            'success': True,
            'post_id': post_id,
            'timestamp': datetime.now().isoformat()
        }

    def add_comment(self, media_id, text):
        """Add a comment to a post (used for hashtags)."""
        print(f"   Adding comment with hashtags...")

        url = f"{self.base_url}/{media_id}/comments"
        params = {
            'message': text,
            'access_token': self.access_token
        }

        response = requests.post(url, data=params)

        if response.status_code == 200:
            print(f"   ✅ Hashtags added as first comment")
            return True
        else:
            error = response.json().get('error', {})
            print(f"   ⚠️  Failed to add comment: {error.get('message')}")
            return False

    def check_token_validity(self):
        """Check if the access token is still valid."""
        url = f"{self.base_url}/debug_token"
        params = {
            'input_token': self.access_token,
            'access_token': self.access_token
        }

        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json().get('data', {})
            is_valid = data.get('is_valid', False)
            expires_at = data.get('expires_at', 0)

            # Page Access Tokens from long-lived User tokens don't expire
            # The debug endpoint may show misleading expiration info
            if self.page_id and expires_at:
                print("🔑 Page Access Token (never expires)")
            elif expires_at:
                expiry_date = datetime.fromtimestamp(expires_at)
                days_left = (expiry_date - datetime.now()).days
                print(f"🔑 Token expires: {expiry_date.strftime('%Y-%m-%d')} ({days_left} days)")

                if days_left < 7:
                    print(f"⚠️  WARNING: Token expires in {days_left} days! Refresh soon.")
            else:
                print("🔑 Token does not expire (long-lived)")

            return is_valid
        return False


def send_slack_notification(message, webhook_url=None):
    """Send notification to Slack."""
    webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        return

    try:
        requests.post(webhook_url, json={'text': message}, timeout=5)
    except Exception as e:
        print(f"⚠️  Slack notification failed: {e}")


def main():
    parser = argparse.ArgumentParser(description='Post to Instagram via Meta Graph API')

    parser.add_argument('--test', action='store_true', help='Test connection and show account info')
    parser.add_argument('--post', action='store_true', help='Post a single image')
    parser.add_argument('--carousel', action='store_true', help='Post a carousel')
    parser.add_argument('--reel', action='store_true', help='Post a reel (video)')
    parser.add_argument('--url', type=str, help='Image/video URL for single post or reel')
    parser.add_argument('--urls', type=str, help='Comma-separated image URLs for carousel')
    parser.add_argument('--cover', type=str, help='Cover image URL for reel')
    parser.add_argument('--caption', type=str, help='Caption for the post')
    parser.add_argument('--hashtags', type=str, help='Hashtags to append to caption')
    parser.add_argument('--check-token', action='store_true', help='Check token validity')

    args = parser.parse_args()

    try:
        poster = InstagramPoster()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    if args.check_token:
        print("\n🔍 Checking token validity...")
        poster.check_token_validity()
        return

    if args.test:
        print("\n" + "=" * 60)
        print("   INSTAGRAM API CONNECTION TEST")
        print("=" * 60)

        info = poster.get_account_info()
        if info:
            print(f"\n✅ Connected to Instagram!")
            print(f"   Username: @{info.get('username', 'N/A')}")
            print(f"   Followers: {info.get('followers_count', 'N/A')}")
            print(f"   Posts: {info.get('media_count', 'N/A')}")
            poster.check_token_validity()
        else:
            print("\n❌ Connection failed")
            print("   Make sure Instagram is linked to your Facebook Page")
        return

    if args.post:
        if not args.url or not args.caption:
            print("❌ --post requires --url and --caption")
            sys.exit(1)

        result = poster.post_single_image(args.url, args.caption, args.hashtags)

        if result['success']:
            send_slack_notification(f"✅ Instagram post published!\nPost ID: {result['post_id']}")
        else:
            send_slack_notification(f"❌ Instagram post failed: {result['error']}")

        return

    if args.carousel:
        if not args.urls or not args.caption:
            print("❌ --carousel requires --urls and --caption")
            sys.exit(1)

        urls = [u.strip() for u in args.urls.split(',')]
        result = poster.post_carousel(urls, args.caption, args.hashtags)

        if result['success']:
            send_slack_notification(f"✅ Instagram carousel published!\nPost ID: {result['post_id']}")
        else:
            send_slack_notification(f"❌ Instagram carousel failed: {result['error']}")

        return

    if args.reel:
        if not args.url or not args.caption:
            print("❌ --reel requires --url (video) and --caption")
            sys.exit(1)

        result = poster.post_reel(args.url, args.caption, args.hashtags, args.cover)

        if result['success']:
            send_slack_notification(f"✅ Instagram Reel published!\nPost ID: {result['post_id']}")
        else:
            send_slack_notification(f"❌ Instagram Reel failed: {result['error']}")

        return

    # Default: show help
    parser.print_help()


if __name__ == '__main__':
    main()
