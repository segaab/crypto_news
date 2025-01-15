import asyncio
import aiohttp
import feedparser
import json
import uuid
from datetime import datetime, timedelta
from loguru import logger
from typing import Dict, Any, List, Optional
import os
import email.utils  # Add this import at the top
import re  # Make sure this is at the top with other imports
import math
import time

from config import (
    RSS_FEEDS,
    POLLING_INTERVAL,
    INITIAL_RETRY_DELAY,
    MAX_RETRY_DELAY,
    LOG_LEVEL,
    ARTICLES_BUFFER_SIZE,
    CLOUDFLARE_POLLING_INTERVAL,
    is_cloudflare_feed,
    VLLM_HOST
)
from redis_client import RedisClient
from article_analyzer import ArticleAnalyzer
from memory_monitor import MemoryMonitor

class FeedPoller:
    def __init__(self, send_to_clients):
        self.send_to_clients = send_to_clients
        self.article_buffer = []
        self.is_ready = False
        self.redis_client = None  # Will be initialized in setup
        self.feed_urls = RSS_FEEDS  # Add this line to initialize feed_urls
        self.max_buffer_size = min(ARTICLES_BUFFER_SIZE, 15)  # Limit buffer size
        self.batch_size = 3  # Process feeds in smaller batches
        self.cleanup_interval = 300  # Clean old articles every 5 minutes
        self.last_cleanup = time.time()
        
        # Create logs directory
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        logger.add(
            os.path.join(logs_dir, "feed_poller_{time}.log"),
            rotation="24h",
            level=LOG_LEVEL
        )
        
        logger.info(f"Feed Poller initialized with {len(self.feed_urls)} feeds")

        self.analyzer = ArticleAnalyzer(VLLM_HOST)
        logger.info(f"Article analyzer initialized with vLLM at {VLLM_HOST}")

        self.memory_monitor = MemoryMonitor()

    async def setup(self):
        """Async initialization"""
        self.redis_client = RedisClient()
        await self.redis_client.setup()
        
        # Initialize buffer from Redis
        if os.getenv('REDIS_CLEAR_ON_START', '').lower() == 'true':
            logger.info("Clearing Redis cache on startup...")
            await self.redis_client.clear_cache()
        else:
            # Load existing articles from Redis
            await self.initialize_buffer()
        
        logger.info("Feed Poller setup completed")

    async def fetch_feed(self, session: aiohttp.ClientSession, feed_url: str, retry_count: int = 0) -> Optional[Dict]:
        """Fetch a feed with exponential backoff retry logic"""
        MAX_RETRIES = 3
        BASE_DELAY = 90  # Base delay in seconds
        
        try:
            # Add brotli support to the session
            async with session.get(feed_url, headers={'Accept-Encoding': 'gzip, deflate, br'}) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    return self.process_feed(feed, feed_url)
                else:
                    logger.error(f"❌ Error fetching {feed_url}: {response.status}, {await response.text()}")
        except Exception as e:
            logger.error(f"❌ Error fetching {feed_url}: {str(e)}")
        
        # Handle retry logic
        if retry_count < MAX_RETRIES:
            # Calculate delay with exponential backoff: BASE_DELAY * (2^retry_count)
            delay = BASE_DELAY * math.pow(2, retry_count)
            logger.info(f"Retrying {feed_url} after {delay:.0f} seconds... (Attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(delay)
            return await self.fetch_feed(session, feed_url, retry_count + 1)
        else:
            logger.error(f"❌ Max retries reached for {feed_url}")
            return None

    async def initialize_buffer(self):
        """Initialize article buffer from Redis"""
        print("\n📦 Initializing article buffer from Redis...")
        try:
            # Get existing articles from Redis
            existing_articles = await self.redis_client.get_recent_articles(ARTICLES_BUFFER_SIZE)
            if existing_articles:
                print(f"📦 Found latest article in Redis")
                self.article_buffer = existing_articles
                self.is_ready = True
                print(f"✅ Buffer initialized with latest article from Redis")
                return
            else:
                print("📭 No existing articles found in Redis")
                self.article_buffer = []
        except Exception as e:
            print(f"❌ Error initializing buffer: {str(e)}")
            self.article_buffer = []

    def _parse_date(self, entry: Dict[str, Any]) -> str:
        """Convert various date formats to ISO format"""
        # Try different date fields in order of preference
        date_fields = ['published', 'pubDate', 'updated', 'created']
        
        for field in date_fields:
            date_str = entry.get(field)
            if date_str:
                try:
                    # Try parsing as RFC 2822 (common in RSS feeds)
                    parsed_date = email.utils.parsedate_to_datetime(date_str)
                    # Ensure timezone info is preserved
                    if parsed_date.tzinfo is None:
                        # If no timezone info, assume UTC
                        parsed_date = parsed_date.replace(tzinfo=datetime.timezone.utc)
                    # Format with timezone info
                    return parsed_date.isoformat()
                except Exception as e:
                    logger.debug(f"Failed to parse date '{date_str}' from field '{field}': {str(e)}")
                    try:
                        # Try direct ISO format parsing
                        parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        return parsed_date.isoformat()
                    except Exception as e:
                        logger.debug(f"Failed ISO parsing for date '{date_str}': {str(e)}")
                        continue
        
        # If no valid date found, use current time in UTC
        current_time = datetime.now(datetime.timezone.utc)
        logger.warning(f"No valid date found in entry, using current UTC time: {current_time.isoformat()}")
        return current_time.isoformat()

    def _extract_categories(self, entry: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract categories from RSS entry"""
        categories = []
        
        try:
            # Try RSS tags/categories
            if 'tags' in entry:
                for tag in entry.tags:
                    if hasattr(tag, 'term'):
                        categories.append({"term": tag.term})
            elif 'category' in entry:
                if isinstance(entry.category, list):
                    for cat in entry.category:
                        if isinstance(cat, str):
                            categories.append({"term": cat})
                        elif hasattr(cat, 'term'):
                            categories.append({"term": cat.term})
                else:
                    categories.append({"term": entry.category})
                    
        except Exception as e:
            logger.debug(f"Error extracting categories: {str(e)}")
        
        # Always ensure at least one category
        if not categories:
            categories.append({"term": "Cryptocurrency"})
            
        return categories

    def _clean_content(self, content: str) -> str:
        """Clean the content by removing alt attributes from img tags"""
        try:
            # Remove alt attributes from img tags
            cleaned = re.sub(r'<img([^>]*?)alt="[^"]*"([^>]*?)>', r'<img\1\2>', content)
            # Also handle single quotes
            cleaned = re.sub(r"<img([^>]*?)alt='[^']*'([^>]*?)>", r'<img\1\2>', cleaned)
            return cleaned
        except Exception as e:
            logger.debug(f"Error cleaning content: {str(e)}")
            return content

    async def process_feed(self, session: aiohttp.ClientSession, feed_url: str) -> None:
        """Process a single RSS feed with memory optimization"""
        feed_data = await self.fetch_feed(session, feed_url)
        if not feed_data or not feed_data.entries:
            return

        # Process only the most recent entries
        new_articles = []
        for entry in feed_data.entries[:3]:  # Limit to 3 most recent entries
            article_link = entry.link
            
            # Skip if article exists
            if await self.redis_client.is_article_exists(article_link):
                continue

            # Create article data without analysis
            article = {
                "id": str(uuid.uuid4()),
                "title": entry.title[:200],  # Limit title length
                "content": self._clean_content(entry.get("summary", ""))[:500],  # Limit content length
                "source": feed_url.split('/')[2],
                "timestamp": self._parse_date(entry),
                "url": article_link
            }

            # Optional fields only if present
            if hasattr(entry, 'media_content'):
                article["imageUrl"] = self._extract_image_url(entry)
            if hasattr(entry, 'tags'):
                article["categories"] = self._extract_categories(entry)

            # Get analysis separately
            analysis = await self.analyzer.analyze_article(article)
            
            # Store article and analysis separately in Redis
            await self.redis_client.save_article(article_link, {
                "article": article,
                "analysis": analysis
            })

            # Keep only article data in buffer
            new_articles.append(article)

        if new_articles:
            # Update buffer with memory constraints
            self.article_buffer.extend(new_articles)
            self.article_buffer.sort(
                key=lambda x: datetime.fromisoformat(x["timestamp"]), 
                reverse=True
            )
            self.article_buffer = self.article_buffer[:self.max_buffer_size]
            
            # Notify clients with separate article and analysis data
            for article in new_articles:
                await self.send_to_clients({
                    "type": "article",
                    "data": article
                })
                
                # Send analysis separately if available
                analysis = await self.redis_client.get_analysis(article["id"])
                if analysis:
                    await self.send_to_clients({
                        "type": "analysis",
                        "articleId": article["id"],
                        "data": analysis
                    })

    def _extract_image_url(self, entry: Dict[str, Any]) -> str:
        """Extract image URL from RSS entry"""
        # Try different common RSS image locations
        try:
            # Try media:content
            if 'media_content' in entry:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        return media['url']
            
            # Try media:thumbnail
            if 'media_thumbnail' in entry and entry.media_thumbnail:
                return entry.media_thumbnail[0]['url']
            
            # Try enclosures
            if 'enclosures' in entry and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.get('type', '').startswith('image/'):
                        return enclosure.get('href', '')
            
            # Try to find image in content
            if 'content' in entry and entry.content:
                import re
                content = entry.content[0].value
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
                if img_match:
                    return img_match.group(1)
                    
        except Exception as e:
            logger.debug(f"Error extracting image URL: {str(e)}")
        
        # Return empty string if no image found
        return ""

    async def get_initial_articles(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get the buffered articles"""
        if not self.is_ready:
            print("⏳ Service not ready - still collecting initial articles")
            return {"articles": [], "status": "initializing"}
            
        logger.info(f"Returning {len(self.article_buffer)} initial articles")
        return {
            "articles": self.article_buffer,
            "status": "ready"
        }

    async def poll_feeds(self) -> None:
        """Poll RSS feeds at regular intervals with resource optimization"""
        logger.info(f"Starting optimized feed polling with {len(self.feed_urls)} feeds")
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # Check memory before processing
                    if not self.memory_monitor.check_memory():
                        logger.warning("Memory threshold exceeded, skipping polling cycle")
                        await asyncio.sleep(POLLING_INTERVAL)
                        continue
                    
                    # Process feeds in smaller batches
                    for i in range(0, len(self.feed_urls), self.batch_size):
                        batch = self.feed_urls[i:i + self.batch_size]
                        tasks = []
                        
                        for feed_url in batch:
                            logger.debug(f"Processing feed: {feed_url}")
                            task = asyncio.create_task(self.fetch_feed(session, feed_url))
                            tasks.append(task)
                        
                        # Process batch results
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Clean up memory after each batch
                        del tasks
                        
                        # Small delay between batches to prevent CPU spikes
                        await asyncio.sleep(2)
                    
                    # Periodic cleanup of old articles
                    current_time = time.time()
                    if current_time - self.last_cleanup >= self.cleanup_interval:
                        self.cleanup_old_articles()
                        self.last_cleanup = current_time
                    
                except Exception as e:
                    logger.error(f"Error in poll_feeds: {str(e)}")
                
                # Log memory usage
                logger.info(f"Memory usage: {self.memory_monitor.get_usage():.1f}MB")
                await asyncio.sleep(POLLING_INTERVAL)

    def cleanup_old_articles(self):
        """Remove articles older than X days"""
        cutoff = datetime.now() - timedelta(days=7)
        self.article_buffer = [
            article for article in self.article_buffer
            if datetime.fromisoformat(article['timestamp']) > cutoff
        ]

def main():
    """Main entry point"""
    poller = FeedPoller()
    
    try:
        asyncio.run(poller.poll_feeds())
    except KeyboardInterrupt:
        logger.info("RSS Feed polling service stopped")

if __name__ == "__main__":
    main() 