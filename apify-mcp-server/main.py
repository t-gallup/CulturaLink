from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import uvicorn
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check for Apify API token
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
if not APIFY_API_TOKEN:
    print("Warning: APIFY_API_TOKEN not found in environment variables")

# Define Pydantic models for MCP
class MCPInput(BaseModel):
    model: str
    stream: bool = False
    inputs: Dict[str, Any]

class MCPResult(BaseModel):
    result: Dict[str, Any]

app = FastAPI()

@app.post("/")
async def process_request(request: MCPInput) -> MCPResult:
    """
    Process an MCP request by forwarding it to the Apify API.
    """
    if not APIFY_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APIFY_API_TOKEN not configured"
        )
    
    # Extract actor ID from model field
    # Format could be "apify/website-content-crawler" or just "website-content-crawler"
    actor_id = request.model.split("/")[-1] if "/" in request.model else request.model
    
    # We need to handle the prefixed part to determine if it's from Apify store or user
    actor_prefix = request.model.split("/")[0] if "/" in request.model else ""
    
    # Prepare request to Apify API - use actor runs endpoint instead of actor tasks
    apify_url = f"https://api.apify.com/v2/acts/{actor_id}/runs"
    
    # If it's a user actor (not from Apify store), use the username in the URL
    if actor_prefix and actor_prefix != "apify":
        apify_url = f"https://api.apify.com/v2/acts/{actor_prefix}~{actor_id}/runs"
    
    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # First, start the actor run
            run_response = await client.post(
                apify_url,
                json=request.inputs,
                headers=headers,
                timeout=60.0
            )
            
            run_response.raise_for_status()
            run_data = run_response.json()
            
            # Get the run ID
            run_id = run_data.get("data", {}).get("id")
            if not run_id:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get run ID from Apify response"
                )
                
            # Wait for the run to finish - this is simplified and would need improvement
            # for production (e.g., polling with backoff)
            run_status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
            
            max_tries = 30  # Limit the number of tries to avoid infinite loops
            tries = 0
            
            while tries < max_tries:
                tries += 1
                status_response = await client.get(
                    run_status_url,
                    headers=headers,
                    timeout=10.0
                )
                
                status_response.raise_for_status()
                status_data = status_response.json()
                
                status = status_data.get("data", {}).get("status")
                
                if status == "SUCCEEDED":
                    # Get the dataset items
                    dataset_id = status_data.get("data", {}).get("defaultDatasetId")
                    if not dataset_id:
                        return MCPResult(result={"status": "success", "data": status_data.get("data", {})})
                    
                    # Get the dataset items
                    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
                    dataset_response = await client.get(
                        dataset_url,
                        headers=headers,
                        timeout=30.0
                    )
                    
                    dataset_response.raise_for_status()
                    dataset_data = dataset_response.json()
                    
                    return MCPResult(result={"status": "success", "data": dataset_data})
                
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Actor run failed with status: {status}"
                    )
                
                # Wait before checking again
                await httpx.AsyncClient().get("https://httpbin.org/delay/2")
            
            # If we've reached this point, the run hasn't completed in time
            raise HTTPException(
                status_code=504,
                detail="Timeout waiting for actor run to complete"
            )
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error communicating with Apify API: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Apify API error: {e.response.text}"
        )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)