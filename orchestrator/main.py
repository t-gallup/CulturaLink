from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import uvicorn
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables for MCP services
APIFY_MCP_URL = os.getenv("APIFY_MCP_URL", "http://localhost:8001/")
DEEPL_MCP_URL = os.getenv("DEEPL_MCP_URL", "http://localhost:8002/")
CLAUDE_MCP_URL = os.getenv("CLAUDE_MCP_URL", "http://localhost:8003/")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "apify/website-content-crawler")

# Define Pydantic models
class AskRequest(BaseModel):
    query: str
    country_code: Optional[str] = None

class AskResponse(BaseModel):
    context: str
    source_url: Optional[str] = None
    translated_text: Optional[str] = None

# Create FastAPI app
app = FastAPI()

# Helper function to make MCP API calls
async def call_mcp(client: httpx.AsyncClient, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = await client.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        print(f"Request error: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))

@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    # Simple version - just call Claude directly
    async with httpx.AsyncClient() as client:
        try:
            # Prepare Claude MCP payload
            claude_payload = {
                "model": "claude/answer",
                "stream": False,
                "inputs": {
                    "query": request.query
                }
            }
            
            # Call Claude MCP
            claude_response = await call_mcp(client, CLAUDE_MCP_URL, claude_payload)
            
            # Extract response text
            response_text = claude_response.get("result", {}).get("text", "No response")
            
            return AskResponse(context=response_text)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Extended version - implement full workflow with Apify and DeepL
@app.post("/ask_full", response_model=AskResponse)
async def ask_full(request: AskRequest) -> AskResponse:
    # This is a placeholder for the full workflow implementation
    # Full implementation would:
    # 1. Call Apify to get relevant content based on query/country
    # 2. Call DeepL to translate non-English content
    # 3. Call Claude to provide context and explanation
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Call Apify MCP to scrape relevant content
            search_terms = f"{request.query}"
            if request.country_code:
                search_terms += f" {request.country_code}"
                
            apify_payload = {
                "model": APIFY_ACTOR_ID,
                "stream": False,
                "inputs": {
                    "startUrls": [{"url": f"https://www.google.com/search?q={search_terms.replace(' ', '+')}"}],
                    "maxPagesPerCrawl": 3
                }
            }
            
            apify_response = await call_mcp(client, APIFY_MCP_URL, apify_payload)
            
            # In a real implementation, extract content and URL from Apify response
            content = "Example content from website about the query"
            source_url = "https://example.com/article"
            
            # 2. Call DeepL MCP to translate content (if needed)
            deepl_payload = {
                "model": "deepl/translate",
                "stream": False,
                "inputs": {
                    "text": [content],
                    "target_lang": "EN-US"
                }
            }
            
            deepl_response = await call_mcp(client, DEEPL_MCP_URL, deepl_payload)
            translated_text = deepl_response.get("result", {}).get("translations", [{}])[0].get("text", content)
            
            # 3. Call Claude MCP to provide context
            claude_payload = {
                "model": "claude/contextualize",
                "stream": False,
                "inputs": {
                    "text": translated_text
                }
            }
            
            claude_response = await call_mcp(client, CLAUDE_MCP_URL, claude_payload)
            context = claude_response.get("result", {}).get("text", "No context available")
            
            return AskResponse(
                context=context,
                source_url=source_url,
                translated_text=translated_text
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Add a route to serve static files (UI)
@app.get("/")
async def read_root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CulturaLink</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2c3e50; }
            textarea { width: 100%; height: 100px; margin-bottom: 10px; padding: 10px; }
            button { padding: 10px 20px; background-color: #3498db; color: white; border: none; cursor: pointer; }
            button:hover { background-color: #2980b9; }
            #results { margin-top: 20px; padding: 10px; border: 1px solid #ddd; min-height: 100px; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h1>CulturaLink - Cultural Translator Agent</h1>
        <p>Ask a question about any culture or country around the world.</p>
        
        <textarea id="query" placeholder="e.g., Why do Koreans take off their shoes inside?"></textarea>
        <button id="askButton">Ask</button>
        
        <div id="results"></div>
        
        <script>
            document.getElementById('askButton').addEventListener('click', async () => {
                const query = document.getElementById('query').value;
                const resultsElement = document.getElementById('results');
                
                if (!query) {
                    resultsElement.textContent = "Please enter a query";
                    return;
                }
                
                // Show loading state
                const button = document.getElementById('askButton');
                button.disabled = true;
                button.textContent = "Loading...";
                resultsElement.textContent = "Searching for cultural context...";
                
                try {
                    const response = await fetch('/ask', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ query })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`Error: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    resultsElement.textContent = data.context;
                } catch (error) {
                    resultsElement.textContent = `An error occurred: ${error.message}`;
                } finally {
                    // Reset button state
                    button.disabled = false;
                    button.textContent = "Ask";
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# Import HTMLResponse for the root route
from fastapi.responses import HTMLResponse

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)