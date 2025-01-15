from feed_poller import FeedPoller
from loguru import logger
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, POLLING_INTERVAL, ARTICLES_BUFFER_SIZE
from aiohttp import web
from aiohttp.web import middleware
import asyncio
import json
from typing import Dict, Any
import uuid
from dataclasses import dataclass
from asyncio import Queue
from datetime import datetime
import time

@dataclass(frozen=True)  # Makes the class hashable
class Client:
    id: str
    queue: Queue

# Change from set to dict to store client objects
connected_clients = {}  # Use dict instead of set

@middleware
async def cors_middleware(request, handler):
    """Middleware to handle CORS"""
    response = await handler(request)
    
    # Add CORS headers to every response
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Handle OPTIONS request
    if request.method == 'OPTIONS':
        return web.Response(status=204)
    
    return response

async def send_to_clients(data: Dict[str, Any]):
    """Send data to all connected clients"""
    disconnected = []
    for client_id, client in connected_clients.items():
        try:
            await client.queue.put(data)
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {str(e)}")
            disconnected.append(client_id)
    
    # Clean up disconnected clients
    for client_id in disconnected:
        connected_clients.pop(client_id, None)

async def get_articles(request):
    """Endpoint for initial articles fetch"""
    poller = request.app['poller']
    response = await poller.get_initial_articles()
    
    # Log the response format
    logger.debug(f"Articles response: {json.dumps(response, indent=2)}")
    
    if response.get("status") == "initializing":
        response_data = {
            "articles": [],
            "status": "initializing",
            "message": "Service is collecting initial articles. Please try again shortly.",
            "required": ARTICLES_BUFFER_SIZE,
            "current": len(poller.article_buffer),
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"Service initializing - Buffer: {len(poller.article_buffer)}/{ARTICLES_BUFFER_SIZE}")
        return web.json_response(response_data, status=503)  # Service Unavailable
    
    if len(response["articles"]) < ARTICLES_BUFFER_SIZE:
        response_data = {
            "articles": response["articles"],
            "status": "partial",
            "message": f"Service has only {len(response['articles'])} of {ARTICLES_BUFFER_SIZE} required articles",
            "required": ARTICLES_BUFFER_SIZE,
            "current": len(response["articles"]),
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"Partial content - Buffer: {len(response['articles'])}/{ARTICLES_BUFFER_SIZE}")
        return web.json_response(response_data, status=206)  # Partial Content
    
    response_data = {
        **response,
        "status": "success",
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"Full content served - Buffer: {len(response['articles'])}/{ARTICLES_BUFFER_SIZE}")
    return web.json_response(response_data)

async def stream(request):
    """SSE endpoint for real-time updates"""
    # Get client info
    client_ip = request.remote
    client_id = str(uuid.uuid4())[:8]
    logger.info(f"New client connecting - ID: {client_id}, IP: {client_ip}")

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    
    await response.prepare(request)
    
    # Create a queue for this client
    queue = asyncio.Queue()
    client = Client(id=client_id, queue=queue)
    connected_clients[client_id] = client
    
    buffer_size = len(request.app['poller'].article_buffer)
    logger.info(f"Client {client_id} initialized - Buffer has {buffer_size}/{ARTICLES_BUFFER_SIZE} articles")
    
    try:
        # Send initial articles when client first connects
        poller = request.app['poller']
        initial_articles = await poller.get_initial_articles()
        
        # Add buffer status and timestamp to the response
        initial_data = {
            **initial_articles,
            "buffer_status": {
                "required": ARTICLES_BUFFER_SIZE,
                "current": len(initial_articles["articles"])
            },
            "timestamp": datetime.utcnow().isoformat(),
            "type": "initial"
        }
        
        logger.debug(f"Sending initial data to client {client_id}: {json.dumps(initial_data, indent=2)}")
        await response.write(f'data: {json.dumps(initial_data)}\n\n'.encode('utf-8'))
        
        while True:
            try:
                data = await queue.get()
                # Add current buffer size and timestamp to updates
                update_data = {
                    **data,
                    "buffer_status": {
                        "required": ARTICLES_BUFFER_SIZE,
                        "current": len(poller.article_buffer)
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                logger.debug(f"Sending update to client {client_id}: {json.dumps(update_data, indent=2)}")
                await response.write(f'data: {json.dumps(update_data)}\n\n'.encode('utf-8'))
            except ConnectionResetError:
                logger.warning(f"Connection reset for client {client_id}")
                break
    finally:
        connected_clients.pop(client_id, None)
        logger.info(f"Client {client_id} disconnected - {len(connected_clients)} clients remaining")
    
    return response

async def start_background_tasks(app):
    """Start the feed polling in the background"""
    poller = FeedPoller(send_to_clients)
    await poller.setup()  # Initialize async components
    app['poller'] = poller
    app['polling_task'] = asyncio.create_task(app['poller'].poll_feeds())

async def cleanup_background_tasks(app):
    """Clean up the background tasks"""
    logger.info("Starting graceful shutdown...")
    
    try:
        # Cancel polling task
        app['polling_task'].cancel()
        try:
            await app['polling_task']
        except asyncio.CancelledError:
            logger.info("Polling task cancelled successfully")
        
        # Close Redis connections
        if 'poller' in app:
            await app['poller'].redis_client.close()
            logger.info("Redis connections closed")
        
        # Notify connected clients
        for client in connected_clients.values():
            try:
                await client.queue.put({"type": "shutdown", "message": "Server shutting down"})
            except:
                pass
        
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

async def clear_cache(request):
    """Endpoint to clear the Redis cache and article buffer"""
    poller = request.app['poller']
    
    # Clear Redis
    await poller.redis_client.clear_cache()
    
    # Clear article buffer
    poller.article_buffer = []
    poller.is_ready = False
    
    return web.json_response({
        "status": "success",
        "message": "Cache cleared successfully"
    })

async def send_to_client(client_id, client, data, disconnected):
    try:
        await client.queue.put(data)
    except Exception as e:
        logger.error(f"Error sending to client {client_id}: {str(e)}")
        disconnected.append(client_id)

async def health_check(request):
    """Health check endpoint for monitoring"""
    poller = request.app['poller']
    
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "buffer_size": len(poller.article_buffer),
        "connected_clients": len(connected_clients),
        "uptime": time.time() - request.app.get('start_time', time.time())
    })

async def get_article_analysis(request):
    """Endpoint to fetch analysis for a specific article"""
    article_id = request.match_info.get('article_id')
    if not article_id:
        return web.json_response({
            "error": "Missing article_id parameter"
        }, status=400)
    
    try:
        poller = request.app['poller']
        analysis = await poller.redis_client.get_analysis(article_id)
        
        if analysis:
            return web.json_response({
                "articleId": article_id,
                "analysis": analysis
            })
        else:
            return web.json_response({
                "articleId": article_id,
                "error": "Analysis not found"
            }, status=404)
            
    except Exception as e:
        logger.error(f"Error fetching analysis for article {article_id}: {str(e)}")
        return web.json_response({
            "error": "Internal server error"
        }, status=500)

def main():
    """Main entry point"""
    logger.info(f"Starting RSS Polling Service")
    logger.info(f"Redis Configuration - Host: {REDIS_HOST}, Port: {REDIS_PORT}, DB: {REDIS_DB}")

    app = web.Application(middlewares=[cors_middleware])
    
    # Store start time for uptime tracking
    app['start_time'] = time.time()
    
    # Add routes
    app.router.add_get('/articles', get_articles)
    app.router.add_get('/stream', stream)
    app.router.add_post('/clear-cache', clear_cache)
    app.router.add_get('/health', health_check)  # Add health check endpoint
    app.router.add_get('/analysis/{article_id}', get_article_analysis)  # Add new route

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    # Try different ports if 8000 is taken
    ports = [8000, 8001, 8002, 8003]
    for port in ports:
        try:
            web.run_app(app, host='0.0.0.0', port=port)
            break
        except OSError as e:
            if port == ports[-1]:  # Last port attempt
                raise
            logger.warning(f"Port {port} is in use, trying next port...")
            continue

if __name__ == "__main__":
    main() 