import aiohttp
import json
from loguru import logger
from typing import Dict, Any, Optional

class ArticleAnalyzer:
    def __init__(self, vllm_host: str = "http://localhost:8000"):
        self.vllm_host = vllm_host
        self.endpoint = f"{vllm_host}/v1/completions"
        
    def _create_analysis_prompt(self, article: Dict[str, Any]) -> str:
        """Create a structured prompt for the article analysis"""
        return f"""Analyze this financial article briefly:

Title: {article['title']}
Source: {article['source']}
Content: {article['content']}

Provide a concise analysis:
1. Summary: Key points in 2-3 sentences
2. Market Impact: Main effects on markets
3. Trading Ideas: 1-2 specific trading opportunities
4. Assets: Key instruments mentioned
5. Risk: Low/Medium/High with brief reason

Keep responses short and focused."""

    async def analyze_article(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send article to vLLM for analysis"""
        try:
            prompt = self._create_analysis_prompt(article)
            
            payload = {
                "model": "cxllin/Llama2-7b-Finance",
                "prompt": prompt,
                "max_tokens": 512,
                "temperature": 0.5
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers={"Content-Type": "application/json"},
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        analysis = result['choices'][0]['text']
                        
                        return {
                            "article_id": article["id"],
                            "timestamp": article["timestamp"],
                            "analysis": analysis,
                            "model": "Llama2-7b-Finance",
                            "version": "1.0"
                        }
                    else:
                        logger.error(f"Analysis failed with status {response.status}: {await response.text()}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error analyzing article: {str(e)}")
            return None 