import os
from loguru import logger
from typing import List

# Print current working directory for debugging
logger.info(f"Current working directory: {os.getcwd()}")

# Log environment variables before loading .env
logger.info("Environment variables before loading .env:")
logger.info(f"REDIS_PORT (from env): {os.getenv('REDIS_PORT', '6379')}")

# Load environment variables from .env file
env_path = os.path.join(os.getcwd(), ".env")
logger.info(f"Looking for .env file at: {env_path}")

if os.path.exists(env_path):
    # Clear existing environment variables
    if 'REDIS_PORT' in os.environ:
        logger.warning(f"Clearing existing REDIS_PORT from environment: {os.environ['REDIS_PORT']}")
        del os.environ['REDIS_PORT']
    
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Log environment variables after loading .env
logger.info(f"Environment REDIS_PORT after loading .env: {os.getenv('REDIS_PORT', '6379')}")

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# RSS Feed Configuration
RSS_FEEDS = [
    'https://ambcrypto.com/feed/',  # Keep one main feed for testing
    # Comment out others until performance is verified
]

Freelancing = [
    # 'https://www.reddit.com/r/freelance/.rss',
    # 'https://www.reddit.com/r/Entrepreneur/.rss',
    # 'https://www.reddit.com/r/smallbusiness/.rss',
    # 'https://www.reddit.com/r/SideProject/.rss',
    # 'https://www.reddit.com/r/indiehackers/.rss',
]

Crypto = [
    'https://ambcrypto.com/feed/',          # Main feed
    # 'https://cointelegraph.com/rss',        # Major crypto news
    # 'https://news.bitcoin.com/feed/',       # Bitcoin news
    # 'https://cryptonews.com/news/feed/',    # General crypto news
    # 'https://bitcoinmagazine.com/feed',     # Bitcoin focused
    # 'https://decrypt.co/feed',              # Modern crypto news
    # 'https://blog.coinbase.com/feed',       # Exchange news
    # 'https://newsbtc.com/feed/'             # Trading focused
]
CDD = [
    # 'https://www.reddit.com/r/technology/.rss',
    # 'https://www.reddit.com/r/supplychain/.rss',
    # 'https://www.reddit.com/r/SupplyChainLogistics/.rss',
    # 'https://www.reddit.com/r/SupplyChainManagement/.rss',
    # 'https://www.reddit.com/r/SupplyChain/.rss',
    # 'https://www.reddit.com/r/SupplyChainNews/.rss',
    # 'https://www.reddit.com/r/LogisticsHub/.rss',
    # 'https://www.reddit.com/r/Logistics/.rss',
    # 'https://www.reddit.com/r/logisticsjobs/.rss',
    # 'https://www.reddit.com/r/logisticsnews/.rss',
    # 'https://www.reddit.com/r/logisticsporn/.rss',
    # 'https://www.reddit.com/r/LogisticsSoftware/.rss',
    # 'https://www.reddit.com/r/LogisticsStudy/.rss',
    # 'https://www.reddit.com/r/ProductOperations/.rss',
    # 'https://www.reddit.com/r/mechanic/.rss',
    # 'https://www.reddit.com/r/MechanicAdvice/.rss',
    # 'https://www.reddit.com/r/MechanicalEngineering/.rss',
    # 'https://www.reddit.com/r/Miata/.rss'
]
BiltP2P = [

]

# Polling Configuration
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '300'))  # Increase to 5 minutes
CLOUDFLARE_POLLING_INTERVAL = int(os.getenv('CLOUDFLARE_POLLING_INTERVAL', '300'))  # Default: 5 minutes
INITIAL_RETRY_DELAY = 5  # seconds
MAX_RETRY_DELAY = 300  # seconds

# Buffer Configuration
ARTICLES_BUFFER_SIZE = int(os.getenv('ARTICLES_BUFFER_SIZE', '15'))  # Reduce buffer size

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_RETENTION = "1 day"  # Limit log file retention

# Cloudflare-protected feeds
CLOUDFLARE_PROTECTED_DOMAINS = [
    'coinpaprika.com',
    'coindesk.com',
    'cointelegraph.com',
    'reddit.com'
]

def is_cloudflare_feed(feed_url: str) -> bool:
    """Check if a feed URL is from a Cloudflare-protected domain"""
    return any(domain in feed_url for domain in CLOUDFLARE_PROTECTED_DOMAINS)

# Log configured values
logger.info(f"Configured REDIS_PORT: {REDIS_PORT}") 

# Add these lines to config.py
VLLM_HOST = os.getenv('VLLM_HOST', 'http://localhost:8000')
VLLM_MAX_TOKENS = int(os.getenv('VLLM_MAX_TOKENS', '512'))
VLLM_TEMPERATURE = float(os.getenv('VLLM_TEMPERATURE', '0.5')) 

# Resource optimization settings
MAX_CONCURRENT_FEEDS = int(os.getenv('MAX_CONCURRENT_FEEDS', '3'))  # Limit concurrent processing 