import redis.asyncio as aioredis
from loguru import logger
from config import REDIS_HOST, REDIS_PORT, REDIS_DB
import json
from typing import List, Dict, Any, Optional

class RedisClient:
    def __init__(self):
        self.redis = None

    async def setup(self):
        """Async initialization"""
        self.redis = await aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        await self.redis.ping()
        logger.info(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    async def is_article_exists(self, article_link: str) -> bool:
        """Check if article link hash exists in Redis"""
        try:
            key = f"article:{article_link}"
            return bool(await self.redis.exists(key))
        except Exception as e:
            logger.error(f"Redis error while checking article: {str(e)}")
            return False

    async def save_article(self, article_link: str, data: dict) -> None:
        """Save article and analysis separately"""
        article_key = f"article:{article_link}"
        analysis_key = f"analysis:{data['article']['id']}"
        
        # Save article data
        await self.redis.set(
            article_key,
            json.dumps(data['article']),
            ex=86400  # 24 hours
        )
        
        # Save analysis if available
        if data.get('analysis'):
            await self.redis.set(
                analysis_key,
                json.dumps(data['analysis']),
                ex=86400  # 24 hours
            )

    async def get_recent_articles(self, count: int = 15) -> List[Dict[str, Any]]:
        """Get recent articles from Redis"""
        try:
            # Get all article keys
            keys = await self.redis.keys("article:*")
            articles = []
            
            for key in keys:
                value = await self.redis.get(key)
                try:
                    # Try to parse as JSON (for full article data)
                    article_data = json.loads(value)
                    articles.append(article_data)
                except json.JSONDecodeError:
                    # Skip articles that only have link stored
                    continue
            
            # Sort by timestamp and return most recent
            articles.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return articles[:count]
            
        except Exception as e:
            logger.error(f"Redis error while getting recent articles: {str(e)}")
            return []

    async def clear_cache(self):
        """Clear all articles from Redis"""
        try:
            # Delete all article keys
            keys = await self.redis.keys("article:*")
            if keys:
                await self.redis.delete(*keys)
            logger.info("Redis cache cleared successfully")
        except Exception as e:
            logger.error(f"Redis error while clearing cache: {str(e)}")

    async def get_analysis(self, article_id: str) -> Optional[Dict]:
        """Get analysis for specific article"""
        analysis_key = f"analysis:{article_id}"
        analysis_data = await self.redis.get(analysis_key)
        
        if analysis_data:
            try:
                return json.loads(analysis_data)
            except json.JSONDecodeError:
                logger.error(f"Error decoding analysis data for article {article_id}")
                return None
        return None 