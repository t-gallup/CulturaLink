from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import uvicorn
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check for DeepL API key
DEEPL_AUTH_KEY = os.getenv("DEEPL_AUTH_KEY")
if not DEEPL_AUTH_KEY:
    print("Warning: DEEPL_AUTH_KEY not found in environment variables")

# Define Pydantic models for MCP
class Translation(BaseModel):
    text: str
    detected_source_language: str

class TranslationResult(BaseModel):
    translations: List[Translation]

class MCPInput(BaseModel):
    model: str
    stream: bool = False
    inputs: Dict[str, Any]

class MCPResult(BaseModel):
    result: TranslationResult

app = FastAPI()

@app.post("/")
async def process_request(request: MCPInput) -> MCPResult:
    """
    Process an MCP request by forwarding it to the DeepL API.
    """
    if not DEEPL_AUTH_KEY:
        raise HTTPException(
            status_code=500,
            detail="DEEPL_AUTH_KEY not configured"
        )
    
    # Extract request parameters
    text = request.inputs.get("text", [])
    target_lang = request.inputs.get("target_lang", "EN-US")
    
    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text provided for translation"
        )
    
    # Prepare request to DeepL API
    deepl_url = "https://api.deepl.com/v2/translate"
    
    # Prepare the data for DeepL API
    data = {
        "text": text if isinstance(text, list) else [text],
        "target_lang": target_lang
    }
    
    headers = {
        "Authorization": f"DeepL-Auth-Key {DEEPL_AUTH_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                deepl_url,
                json=data,
                headers=headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Return translations in the expected format
            return MCPResult(result=TranslationResult(**result))
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error communicating with DeepL API: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"DeepL API error: {e.response.text}"
        )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)