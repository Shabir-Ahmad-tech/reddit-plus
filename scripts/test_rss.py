import sys
import html
import re
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_fetch_rss(sub="SaaS", query=None):
    if query:
        url = f"https://www.reddit.com/r/{sub}/search.rss?q={urllib.parse.quote(query)}&sort=new&restrict_sr=on&limit=10"
    else:
        url = f"https://www.reddit.com/r/{sub}/new.rss?limit=10"
    
    print(f"Fetching: {url}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            print(f"Response length: {len(data)}")
            entries = re.findall(r"<entry>(.*?)</entry>", data, re.DOTALL)
            print(f"Entries extracted: {len(entries)}")
            for e in entries[:3]:
                title_match = re.search(r"<title>(.*?)</title>", e)
                title = html.unescape(title_match.group(1)) if title_match else "No title"
                link_match = re.search(r'<link href="(.*?)"', e)
                link = link_match.group(1) if link_match else ""
                author_match = re.search(r"<name>(.*?)</name>", e)
                author = author_match.group(1) if author_match else "anonymous"
                
                # Extract post id from link or id tag
                # e.g. https://www.reddit.com/r/SaaS/comments/1ir234/...
                id_match = re.search(r"/comments/([a-z0-9]+)/", link)
                post_id = id_match.group(1) if id_match else ""
                
                # Extract content
                content_match = re.search(r"<content type=\"html\">(.*?)</content>", e, re.DOTALL)
                raw_html = html.unescape(content_match.group(1)) if content_match else ""
                # Strip HTML tags
                clean_body = re.sub(r"<[^>]+>", " ", raw_html).strip()
                clean_body = re.sub(r"\s+", " ", clean_body)
                
                print(" - Title:", title[:60])
                print("   Author:", author)
                print("   ID:", post_id)
                print("   Link:", link)
                print("   Body:", clean_body[:80])
    except Exception as err:
        print(f"Error fetching RSS: {err}")

if __name__ == "__main__":
    test_fetch_rss("SaaS")
    print("\n--- Testing Search ---")
    test_fetch_rss("all", query="looking for CRM")
