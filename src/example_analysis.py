from langchain import Agent, Task
from transformers import pipeline
import asyncio
import redis
import json

# Load models
summary_model = pipeline("summarization", model="mrm8488/t5-base-finetuned-summarize-news")
sentiment_model = pipeline("text-classification", model="mrm8488/deberta-v3-ft-financial-news-sentiment-analysis")

# Redis setup
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

# In-memory cache
in_memory_cache = {}

# Define tasks using LangChain
class SummarizeTask(Task):
    async def run(self, news):
        summary = summary_model(news, max_length=100, min_length=30, do_sample=False)[0]["summary_text"]
        in_memory_cache["summary"] = summary
        return summary

class SentimentTask(Task):
    async def run(self, news):
        sentiment = sentiment_model(news)[0]
        in_memory_cache["sentiment"] = sentiment
        return sentiment

# Define the agent
class NewsAgent(Agent):
    async def run(self, news):
        # Create tasks
        summarize_task = SummarizeTask()
        sentiment_task = SentimentTask()
        
        # Run tasks concurrently
        summary, sentiment = await asyncio.gather(
            summarize_task.run(news),
            sentiment_task.run(news)
        )
        
        # Combine results
        result = {
            "summary": summary,
            "sentiment": sentiment
        }
        # Store result in Redis
        redis_client.set("latest_news_analysis", json.dumps(result))
        return result

# Example usage
async def main():
    input_news = "The Federal Reserve raised interest rates by 0.25%, signaling a cautious approach to curbing inflation."
    agent = NewsAgent()
    result = await agent.run(input_news)
    print("Compiled Result:", result)

if __name__ == "__main__":
    asyncio.run(main())