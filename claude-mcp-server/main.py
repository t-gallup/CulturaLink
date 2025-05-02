from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import os
import uvicorn
import anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the Anthropic client
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = None

if anthropic_api_key:
    try:
        # Initialize with only the api_key parameter
        anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
    except Exception as e:
        print(f"Failed to initialize Anthropic client: {e}")
else:
    print("ANTHROPIC_API_KEY not found in environment variables")

# Define Pydantic models for MCP request and response
class MCPInput(BaseModel):
    text: Optional[str] = None
    query: Optional[str] = None

class MCPRequest(BaseModel):
    model: str
    inputs: MCPInput
    stream: Optional[bool] = False

class MCPResult(BaseModel):
    text: str

class MCPResponse(BaseModel):
    result: MCPResult

# Create FastAPI app
app = FastAPI()

@app.post("/", response_model=MCPResponse)
async def process_request(request: MCPRequest) -> MCPResponse:
    if not anthropic_client:
        raise HTTPException(
            status_code=500, 
            detail="Anthropic client not initialized. Check your API key."
        )
    
    # Determine the desired operation
    operation = "answer"
    if "summarize" in request.model.lower():
        operation = "summarize"
    elif "contextualize" in request.model.lower():
        operation = "contextualize"
    
    # Check if required inputs are present
    if operation in ["summarize", "contextualize"] and not request.inputs.text:
        raise HTTPException(
            status_code=400,
            detail=f"Operation '{operation}' requires 'text' input"
        )
    elif operation == "answer" and not request.inputs.query:
        raise HTTPException(
            status_code=400,
            detail="Operation 'answer' requires 'query' input"
        )
    
    # Construct prompt based on operation
    prompt = ""
    if operation == "summarize":
        prompt = f"Summarize the following text concisely, capturing the key points:\n\n{request.inputs.text}"
    elif operation == "contextualize":
        prompt = f"Provide cultural context and explanation for the following text:\n\n{request.inputs.text}"
    else:  # answer
        prompt = request.inputs.query
    
    try:
        # Call Anthropic API with proper parameters
        model = "claude-3-5-haiku-20240620"
        message = anthropic_client.messages.create(
            model=model,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract response text
        response_text = message.content[0].text
        
        return MCPResponse(result=MCPResult(text=response_text))
    
    except anthropic.APIError as e:
        raise HTTPException(
            status_code=e.status_code if hasattr(e, 'status_code') else 500,
            detail=f"Anthropic API error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8003))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)