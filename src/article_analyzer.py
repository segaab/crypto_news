import modal
from loguru import logger
from typing import Dict, Any, Optional
import time

class ArticleAnalyzer:
    def __init__(self):
        self.stub = modal.Stub.from_name("financial-news-analyzer")
        self.model = self.stub.ModelService()
        logger.info("ArticleAnalyzer initialized with Modal")

    async def analyze_article(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze article using Modal service"""
        start_time = time.time()
        logger.info(f"Starting analysis for article: {article['id']} - {article['title'][:50]}...")
        
        try:
            result = self.model.analyze_article.remote(article)
            
            if result:
                elapsed_time = time.time() - start_time
                logger.info(
                    f"Analysis completed for article {article['id']} in {elapsed_time:.2f}s\n"
                    f"Title: {article['title'][:50]}...\n"
                    f"Analysis Preview: {result['analysis'][:200]}..."
                )
                return result
            else:
                logger.error("Analysis failed: No result returned")
                return None
                
        except Exception as e:
            logger.error(f"Error analyzing article: {str(e)}")
            return None 