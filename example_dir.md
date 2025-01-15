# simple_rss_poller.py
import asyncio
import aiohttp
import feedparser
import json
from datetime import datetime
from aiohttp import web
from dataclasses import dataclass
from typing import Dict, Any, Set

# Mock RSS feeds
RSS_FEEDS = [
    'https://www.reddit.com/r/freelance/.rss',
    'https://www.reddit.com/r/technology/.rss',
    'https://www.reddit.com/r/Entrepreneur/.rss',
    'https://www.reddit.com/r/smallbusiness/.rss'
]

@dataclass
class Client:
    id: str
    queue: asyncio.Queue
    
    def __hash__(self):
        return hash(self.id)

class SimpleRSSPoller:
    def __init__(self):
        self.article_buffer = []
        self.connected_clients: Set[Client] = set()
        self.is_ready = False
        
    async def fetch_feed(self, session: aiohttp.ClientSession, feed_url: str):
        try:
            async with session.get(feed_url) as response:
                if response.status == 200:
                    content = await response.text()
                    return feedparser.parse(content)
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
        return None

    async def process_feeds(self):
        async with aiohttp.ClientSession() as session:
            while True:
                for feed_url in RSS_FEEDS:
                    feed = await self.fetch_feed(session, feed_url)
                    if feed and feed.entries:
                        for entry in feed.entries[:1]:  # Only process latest entry
                            article = {
                                "type": "new",
                                "source": {
                                    "base_url": "reddit.com",
                                    "url_id": "ff4400"  # Reddit orange
                                },
                                "metadata": {
                                    "title": entry.get('title', ''),
                                    "link": entry.get('link', ''),
                                    "pubDate": datetime.now().isoformat()
                                }
                            }
                            await self.broadcast_update(article)
                await asyncio.sleep(300)  # Poll every 5 minutes

    async def broadcast_update(self, article):
        disconnected = set()
        for client in self.connected_clients:
            try:
                await client.queue.put(article)
            except Exception:
                disconnected.add(client)
        self.connected_clients -= disconnected

async def stream_handler(request):
    """SSE endpoint for real-time updates"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    await response.prepare(request)

    # Create new client
    client = Client(id=str(len(request.app['poller'].connected_clients)), queue=asyncio.Queue())
    request.app['poller'].connected_clients.add(client)

    try:
        while True:
            data = await client.queue.get()
            await response.write(
                f'event: update\ndata: {json.dumps(data)}\n\n'.encode('utf-8')
            )
    finally:
        request.app['poller'].connected_clients.remove(client)

    return response

async def start_background_tasks(app):
    """Start the feed polling"""
    app['poller'] = SimpleRSSPoller()
    app['polling_task'] = asyncio.create_task(app['poller'].process_feeds())

async def cleanup_background_tasks(app):
    """Cleanup the background tasks"""
    app['polling_task'].cancel()
    await app['polling_task']

def main():
    app = web.Application()
    app.router.add_get('/stream', stream_handler)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    web.run_app(app, host='0.0.0.0', port=8000)

if __name__ == "__main__":
    main()