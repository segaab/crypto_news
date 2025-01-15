import asyncio
import aiohttp
import feedparser
import json
import uuid
from datetime import datetime
import redis
from loguru import logger
from typing import Dict, Any, List
from dataclasses import dataclass
from aiohttp import web
from aiohttp.web import middleware
import email.utils
import re
import os

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
ARTICLES_BUFFER_SIZE = 15
POLLING_INTERVAL = 60
RSS_FEEDS = [
    'https://cointelegraph.com/rss',
    'https://news.bitcoin.com/feed/'
]

# Redis Client
class SimpleRedisClient:
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

    async def is_article_exists(self, article_link: str) -> bool:
        key = f"article:{article_link}"
        return bool(self.redis.exists(key))

    async def save_article(self, article_link: str, article_data: dict) -> None:
        key = f"article:{article_link}"
        self.redis.set(key, json.dumps(article_data), ex=86400)

    async def get_recent_articles(self, count: int = 15) -> List[Dict[str, Any]]:
        keys = self.redis.keys("article:*")
        articles = []
        for key in keys:
            value = self.redis.get(key)
            try:
                article_data = json.loads(value)
                articles.append(article_data)
            except json.JSONDecodeError:
                continue
        articles.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return articles[:count]

    async def clear_cache(self):
        keys = self.redis.keys("article:*")
        if keys:
            self.redis.delete(*keys)
        logger.info("Cache cleared")

# Client Management
@dataclass(frozen=True)
class Client:
    id: str
    queue: asyncio.Queue

connected_clients = {}

# Feed Poller
class SimpleFeedPoller:
    def __init__(self, send_to_clients):
        self.redis_client = SimpleRedisClient()
        self.article_buffer = []
        self.send_to_clients = send_to_clients
        self.is_ready = False

    def _parse_date(self, entry: Dict[str, Any]) -> str:
        date_fields = ['published', 'pubDate', 'updated', 'created']
        for field in date_fields:
            date_str = entry.get(field)
            if date_str:
                try:
                    parsed_date = email.utils.parsedate_to_datetime(date_str)
                    return parsed_date.isoformat()
                except:
                    continue
        return datetime.now().isoformat()

    def _extract_categories(self, entry: Dict[str, Any]) -> List[Dict[str, str]]:
        categories = []
        try:
            if 'tags' in entry:
                for tag in entry.tags:
                    if hasattr(tag, 'term'):
                        categories.append({"term": tag.term})
            elif 'category' in entry:
                if isinstance(entry.category, list):
                    for cat in entry.category:
                        categories.append({"term": str(cat)})
                else:
                    categories.append({"term": str(entry.category)})
        except Exception:
            pass
        if not categories:
            categories.append({"term": "Cryptocurrency"})
        return categories

    def _extract_image_url(self, entry: Dict[str, Any]) -> str:
        try:
            if 'media_content' in entry:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        return media['url']
            if 'content' in entry and entry.content:
                content = entry.content[0].value
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
                if img_match:
                    return img_match.group(1)
        except Exception:
            pass
        return ""

    async def process_feed(self, session: aiohttp.ClientSession, feed_url: str) -> None:
        try:
            async with session.get(feed_url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries:
                        if await self.redis_client.is_article_exists(entry.link):
                            continue

                        article = {
                            "id": str(uuid.uuid4()),
                            "title": entry.title,
                            "content": entry.get("summary", ""),
                            "source": feed_url.split('/')[2],
                            "timestamp": self._parse_date(entry),
                            "url": entry.link,
                            "imageUrl": self._extract_image_url(entry),
                            "categories": self._extract_categories(entry)
                        }

                        await self.redis_client.save_article(entry.link, article)
                        self.article_buffer.append(article)
                        self.article_buffer.sort(
                            key=lambda x: x["timestamp"],
                            reverse=True
                        )
                        self.article_buffer = self.article_buffer[:ARTICLES_BUFFER_SIZE]
                        
                        if len(self.article_buffer) >= ARTICLES_BUFFER_SIZE:
                            self.is_ready = True
                        
                        await self.send_to_clients({"articles": [article]})
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")

# Web Server Routes
async def get_articles(request):
    poller = request.app['poller']
    if not poller.is_ready:
        return web.json_response({
            "articles": [],
            "status": "initializing",
            "message": "Service is collecting initial articles"
        }, status=503)
    return web.json_response({
        "articles": poller.article_buffer,
        "status": "ready"
    })

async def stream(request):
    client_id = str(uuid.uuid4())[:8]
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    
    await response.prepare(request)
    
    queue = asyncio.Queue()
    client = Client(id=client_id, queue=queue)
    connected_clients[client_id] = client
    
    try:
        while True:
            data = await queue.get()
            await response.write(f'data: {json.dumps(data)}\n\n'.encode('utf-8'))
    finally:
        connected_clients.pop(client_id, None)
    
    return response

async def clear_cache(request):
    poller = request.app['poller']
    await poller.redis_client.clear_cache()
    poller.article_buffer = []
    poller.is_ready = False
    return web.json_response({"status": "success"})

# Main Application
async def start_polling(app):
    async def send_to_clients(data):
        for client_id, client in list(connected_clients.items()):
            try:
                await client.queue.put(data)
            except Exception:
                connected_clients.pop(client_id, None)

    app['poller'] = SimpleFeedPoller(send_to_clients)
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = [app['poller'].process_feed(session, feed) for feed in RSS_FEEDS]
            await asyncio.gather(*tasks)
        await asyncio.sleep(POLLING_INTERVAL)

async def start_background_tasks(app):
    app['polling_task'] = asyncio.create_task(start_polling(app))

async def cleanup_background_tasks(app):
    app['polling_task'].cancel()
    await app['polling_task']

def main():
    app = web.Application()
    app.router.add_get('/articles', get_articles)
    app.router.add_get('/stream', stream)
    app.router.add_post('/clear-cache', clear_cache)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    web.run_app(app, host='0.0.0.0', port=8000)

if __name__ == "__main__":
    main() 