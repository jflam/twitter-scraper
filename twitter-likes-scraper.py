import os
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import re
from tqdm import tqdm

def scrape_likes(username, cookies, output_path, max_likes=100):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # Set the cookies
        context.add_cookies(cookies)
        
        page = context.new_page()
        page.goto(f'https://x.com/{username}/likes')
        
        likes = []
        last_height = page.evaluate('document.body.scrollHeight')
        
        # Create a directory for screenshots
        screenshots_dir = output_path.parent / 'screenshots'
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize progress bar
        pbar = tqdm(total=max_likes, desc="Scraping likes")
        
        while len(likes) < max_likes:
            # Extract liked posts
            posts = page.query_selector_all('article[role="article"]')
            for post in posts:
                # Find the analytics link and extract the tweet ID and username
                analytics_link = post.query_selector('a[href*="/analytics"]')
                if analytics_link:
                    href = analytics_link.get_attribute('href')
                    match = re.search(r'/(.+)/status/(\d+)/analytics', href)
                    if match:
                        tweet_username, tweet_id = match.groups()
                    else:
                        continue  # Skip if we can't extract the tweet ID and username
                else:
                    continue  # Skip if we can't find the analytics link

                if tweet_id not in [like['id'] for like in likes]:
                    text_element = post.query_selector('div[data-testid="tweetText"]')
                    timestamp_element = post.query_selector('time')
                    
                    # Capture high-resolution screenshot of the article
                    screenshot_path = screenshots_dir / f"{tweet_id}.png"
                    post.screenshot(path=str(screenshot_path), scale=2)  # Double the resolution
                    
                    likes.append({
                        'id': tweet_id,
                        'username': tweet_username,
                        'text': text_element.inner_text() if text_element else "",
                        'timestamp': timestamp_element.get_attribute('datetime') if timestamp_element else "",
                        'screenshot': str(screenshot_path.relative_to(output_path.parent)),
                        'permalink': f"https://x.com/{tweet_username}/status/{tweet_id}"
                    })
                    pbar.update(1)  # Update progress bar
                    if len(likes) >= max_likes:
                        break
            
            if len(likes) >= max_likes:
                break
            
            # Scroll down
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(2000)  # Wait for new content to load
            
            new_height = page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                break
            last_height = new_height
        
        browser.close()
        pbar.close()  # Close progress bar
    
    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save likes to JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(likes, f, indent=2, ensure_ascii=False)
    
    # Create markdown file
    markdown_path = output_path.with_suffix('.md')
    with open(markdown_path, 'w', encoding='utf-8') as f:
        for like in likes:
            f.write(f"![Tweet by {like['username']}]({like['screenshot']})\n\n")
            f.write(f"[Permalink to tweet]({like['permalink']})\n\n")
            f.write("---\n\n")
    
    # Update environment variable with most recent tweet id/timestamp
    if likes:
        os.environ['MOST_RECENT_TWEET'] = likes[0]['id']

def parse_cookies(cookie_string):
    cookies = []
    for cookie in cookie_string.split(';'):
        name, value = cookie.strip().split('=', 1)
        cookies.append({
            'name': name,
            'value': value,
            'domain': '.x.com',
            'path': '/'
        })
    return cookies

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Scrape X (Twitter) likes')
    parser.add_argument('--username', default='john_lam', help='X (Twitter) username')
    parser.add_argument('--output', type=Path, default=Path('data/likes.json'), help='Output file path')
    parser.add_argument('--max-likes', type=int, default=100, help='Maximum number of likes to scrape')
    args = parser.parse_args()
    
    cookie_string = os.getenv('X_COOKIES')
    if not cookie_string:
        raise ValueError("X_COOKIES environment variable is not set")
    
    cookies = parse_cookies(cookie_string)
    
    scrape_likes(args.username, cookies, args.output, args.max_likes)

if __name__ == '__main__':
    main()
