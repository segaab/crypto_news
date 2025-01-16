import modal
from loguru import logger

app = modal.App("financial-news-analyzer")

# Create image with minimal dependencies
image = (
    modal.Image.debian_slim()
    .pip_install("torch", "transformers", "accelerate", "loguru", "sentencepiece")
)

@app.function(
    image=image,
    gpu="T4",
    timeout=600,
    retries=2
)
def analyze_article(article_data: dict):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import time
    
    start_time = time.time()
    logger.info(f"Starting analysis for article: {article_data['id']}")
    
    try:
        # Model configuration - using standard HF model
        MODEL_NAME = "curiousily/Llama-3-8B-Instruct-Finance-RAG"
        
        MAX_LENGTH = 512
        
        # Load model
        logger.info("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
        
        logger.info("Loading model...")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="auto",
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True
        )
        
        # Create prompt using model's format
        prompt = f"""<|system|>Use only the information to answer the question</s>
<|user|>Analyze this financial article:

Title: {article_data['title']}
Content: {article_data['content']}

Provide:
1. Summary (2-3 sentences)
2. Market Impact
3. Trading Ideas
4. Key Assets
5. Risk Level</s>
<|assistant|>"""

        # Generate analysis
        logger.info("Generating analysis...")
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_LENGTH,
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                num_beams=1,
                pad_token_id=tokenizer.eos_token_id
            )
        
        analysis = tokenizer.decode(outputs[0], skip_special_tokens=True)
        elapsed_time = time.time() - start_time
        
        return {
            "article_id": article_data["id"],
            "timestamp": article_data["timestamp"],
            "analysis": analysis,
            "model": MODEL_NAME,
            "version": "1.0",
            "processing_time": elapsed_time
        }
        
    except Exception as e:
        logger.error(f"Error in analyze_article: {str(e)}")
        raise

@app.local_entrypoint()
def main():
    test_article = {
        "id": "test-1",
        "title": "Bitcoin Surges Past $50,000",
        "content": "Bitcoin's price surged above $50,000 driven by ETF approvals.",
        "source": "test.com",
        "timestamp": "2024-01-01T00:00:00"
    }
    
    try:
        logger.info("Starting test analysis...")
        result = analyze_article.remote(test_article)
        logger.success("Analysis completed successfully")
        logger.info(f"Analysis result: {result}")
        
    except modal.exception.TimeoutError:
        logger.error("Analysis timed out - consider increasing the timeout value")
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}") 