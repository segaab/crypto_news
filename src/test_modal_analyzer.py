import modal
import asyncio
from loguru import logger
from setup_modal import setup_modal

async def test_analysis():
    """Test the Modal-based analyzer"""
    # Ensure Modal is set up
    if not setup_modal():
        logger.error("Modal setup failed. Please run setup_modal.py first")
        return
        
    logger.info("Starting Modal analyzer test...")
    
    try:
        # Import the analyzer app
        app = modal.App.from_name("financial-news-analyzer")
        
        test_articles = [
            {
                "id": "test-1",
                "title": "Bitcoin Surges Past $50,000",
                "content": "Bitcoin's price surged above $50,000 driven by ETF approvals.",
                "source": "test.com",
                "timestamp": "2024-01-01T00:00:00"
            },
            {
                "id": "test-2",
                "title": "Federal Reserve Holds Rates",
                "content": "The Federal Reserve maintained interest rates while signaling future cuts.",
                "source": "test.com",
                "timestamp": "2024-01-01T00:00:00"
            }
        ]
        
        for article in test_articles:
            logger.info(f"\nTesting article: {article['title']}")
            
            try:
                # Call the Modal function with timeout
                result = await asyncio.wait_for(
                    app.analyze_article.remote.aio(article),
                    timeout=60
                )
                
                if result:
                    logger.success("✅ Analysis successful")
                    logger.info("Analysis preview:")
                    logger.info(result['analysis'][:200] + "...")
                else:
                    logger.error("❌ Analysis failed")
                    
            except asyncio.TimeoutError:
                logger.error("❌ Analysis timed out")
            except Exception as e:
                logger.error(f"❌ Error analyzing article: {str(e)}")
                
    except modal.exception.AuthError:
        logger.error("❌ Modal authentication failed. Please run setup_modal.py")
    except Exception as e:
        logger.error(f"❌ Error during test: {str(e)}")

if __name__ == "__main__":
    # Configure logging
    logger.add(
        "modal_test_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG"
    )
    
    try:
        asyncio.run(test_analysis())
    except KeyboardInterrupt:
        logger.warning("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}") 