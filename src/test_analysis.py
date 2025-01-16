import asyncio
import json
from loguru import logger
from article_analyzer import ArticleAnalyzer
from datetime import datetime
import aiohttp
from config import VLLM_HOST

# Test articles with different scenarios
TEST_ARTICLES = [
    {
        "id": "test-1",
        "title": "Bitcoin Surges Past $50,000 as ETF Approval Looms",
        "content": "Bitcoin's price surged above $50,000 for the first time since 2021, driven by optimism around potential ETF approvals and institutional adoption. Trading volume across major exchanges has increased significantly, with analysts pointing to renewed institutional interest.",
        "source": "cryptonews.com",
        "timestamp": datetime.utcnow().isoformat()
    },
    {
        "id": "test-2",
        "title": "Federal Reserve Holds Interest Rates Steady, Signals Future Cuts",
        "content": "The Federal Reserve maintained its benchmark interest rate while indicating potential cuts later this year. Chair Powell emphasized the need to balance inflation risks with economic growth concerns. Markets reacted positively to the dovish tone.",
        "source": "finance.news",
        "timestamp": datetime.utcnow().isoformat()
    },
    {
        "id": "test-3",
        "title": "Empty Article for Error Testing",
        "content": "",  # Empty content to test error handling
        "source": "test.com",
        "timestamp": datetime.utcnow().isoformat()
    }
]

async def check_vllm_server(host: str = VLLM_HOST) -> bool:
    """Check if vLLM server is running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{host}/health") as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"vLLM server check failed: {str(e)}")
        logger.info(
            "Please ensure vLLM server is running with:\n"
            "vllm serve --model cxllin/Llama2-7b-Finance --port 8000"
        )
        return False

async def test_analysis():
    """Test article analysis functionality"""
    # Check vLLM server first
    if not await check_vllm_server():
        logger.error("❌ vLLM server is not available. Please start the server first.")
        return
    
    logger.info("✅ vLLM server is running")
    analyzer = ArticleAnalyzer()
    logger.info("Starting analysis tests...")
    
    results = []
    errors = []
    
    for article in TEST_ARTICLES:
        try:
            logger.info(f"\nTesting analysis for article: {article['id']}")
            logger.info(f"Title: {article['title']}")
            
            # Validate article content
            if not article.get('content'):
                logger.warning(f"⚠️  Article {article['id']} has no content, skipping...")
                errors.append({
                    "article_id": article['id'],
                    "success": False,
                    "error": "Empty content"
                })
                continue
            
            # Run analysis
            start_time = datetime.utcnow()
            analysis = await analyzer.analyze_article(article)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            if analysis:
                logger.success(f"✅ Analysis successful for {article['id']}")
                logger.info(f"Inference time: {elapsed:.2f}s")
                logger.info("Analysis preview:")
                logger.info(analysis['analysis'][:200] + "...")
                results.append({
                    "article_id": article['id'],
                    "success": True,
                    "inference_time": elapsed,
                    "analysis": analysis
                })
            else:
                logger.error(f"❌ Analysis failed for {article['id']}")
                errors.append({
                    "article_id": article['id'],
                    "success": False,
                    "error": "Analysis returned None"
                })
                
        except Exception as e:
            logger.error(f"❌ Error processing {article['id']}: {str(e)}")
            errors.append({
                "article_id": article['id'],
                "success": False,
                "error": str(e)
            })
    
    # Print summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Total articles tested: {len(TEST_ARTICLES)}")
    logger.info(f"Successful analyses: {len(results)}")
    logger.info(f"Failed analyses: {len(errors)}")
    
    if errors:
        logger.warning("\nErrors encountered:")
        for error in errors:
            logger.warning(f"Article {error['article_id']}: {error['error']}")
    
    # Save results to file
    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_tests": len(TEST_ARTICLES),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }
    
    with open("analysis_test_results.json", "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Results saved to analysis_test_results.json")

if __name__ == "__main__":
    # Setup logging
    logger.add(
        "analysis_test_{time}.log",
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