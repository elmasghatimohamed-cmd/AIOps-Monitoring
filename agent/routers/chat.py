import os
import json
import asyncio
import traceback
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

# Import the unified orchestrator instance instead of just the Redis pool
from bridge.services.context_orchestrator import orchestrator

load_dotenv()

router = APIRouter()

# Instantiate Google GenAI Framework
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("CRITICAL: GEMINI_API_KEY is missing from your .env file!")

client = genai.Client(api_key=GEMINI_API_KEY)


@router.websocket("/agent/chat/ws") 
async def websocket_chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(" Contextual Chat WebSocket interface active.")
    
    try:
        while True:
            # Receive natural language streaming questions from the user interface
            data = await websocket.receive_text()
            print(f"User input question: {data}")
            
            # Declare system_context in an outer scope to ensure the fallback engine can access it
            system_context = {}
            try:
                # Gather deep context across Redis, TimescaleDB, and ChromaDB
                system_context = await orchestrator.gather_context(user_query=data)
                
                # Format system context metrics profiles JSON text arrays
                redis_str = json.dumps(system_context.get("redis", {}), indent=2)
                timescale_str = json.dumps(system_context.get("timescaledb", []), indent=2)
                chroma_str = json.dumps(system_context.get("chromadb", {}), indent=2)

                # Construct a highly detailed system instruction payload for the LLM
                system_prompt = (
                    "You are an expert operations intelligence agent supervising a Centreon infrastructure pipeline.\n"
                    "You have direct cross-reference visibility into the hardware ecosystem across three distinct memory stores:\n"
                    "1. REDIS (Real-Time operational metrics cache layer)\n"
                    "2. TIMESCALEDB (1-Hour time-series average telemetry metrics arrays)\n"
                    "3. CHROMADB (Semantic vector incident histories and operational runbooks log ledger)\n\n"
                    
                    "FORMATTING RULES:\n"
                    "1. Organize metrics logically into clean Markdown components (use headers, bold labels, or structured tables).\n"
                    "2. Use bullet points (`*`) for breakdown lists to ensure high readability.\n"
                    "3. Use code tags (e.g., `19.42%`) or bold accents for specific numerical values so they stand out.\n"
                    "4. Add visual layout separators (`---`) between major system sections.\n"
                    "5. Keep the tone highly professional, crisp, and direct. Avoid generic, conversational filler text.\n\n"
                    
                    "=== INFRASTRUCTURE MULTI-TIER REASONING CONTEXT ===\n"
                    f"INTENT CLASSIFICATION DETECTED: {system_context.get('intent_classification')}\n\n"
                    
                    "--- 1. REAL-TIME BUFFER STATE (REDIS) ---\n"
                    f"{redis_str}\n\n"
                    
                    "--- 2. HISTORICAL TREND TIMELINES (TIMESCALEDB) ---\n"
                    f"{timescale_str}\n\n"
                    
                    "--- 3. SEMANTIC MEMORY CORRELATIONS (CHROMADB) ---\n"
                    f"{chroma_str}\n"
                    "====================================================\n\n"
                    "Instructions: Answer the user's inquiry strictly utilizing the metrics data vectors provided above. "
                    "If data points are missing or empty from an engine layer (e.g., TimescaleDB metrics are empty because query intent was categorized as CURRENT_STATUS), "
                    "rely exclusively on the active parameters present in the cache system."
                )

                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                )

                # Exponential Backoff Loop for 503/429 Upstream Transient Events
                max_retries = 3
                delay = 1.0
                response_stream = None

                for attempt in range(max_retries):
                    try:
                        response_stream = await client.aio.models.generate_content_stream(
                            model='gemini-2.5-flash',
                            contents=data,
                            config=config
                        )
                        break  # Stream acquired successfully, exit retry loop
                    except (APIError, Exception) as api_ex:
                        err_str = str(api_ex)
                        # Check for temporary service capacity limits or rate-limiting
                        if "503" in err_str or "429" in err_str:
                            if attempt < max_retries - 1:
                                print(f"[Gemini API Backoff]: 503/429 anomaly hit. Retrying in {delay}s (Attempt {attempt + 1}/{max_retries})...")
                                await asyncio.sleep(delay)
                                delay *= 2  # Exponential backoff scaling
                                continue
                        raise api_ex  # Re-raise immediately if it's an unrecoverable error

                if response_stream:
                    async for chunk in response_stream:
                        if chunk.text:
                            await websocket.send_json({"type": "text", "content": chunk.text})
                else:
                    raise RuntimeError("Failed to establish Gemini stream sequence interface matrix.")
                        
            except Exception as api_err:
                print(" Exception inside contextual Gemini execution streaming matrix!")
                traceback.print_exc()
                
                #Prevent silence during a severe crisis
                summary_data = system_context.get("redis", {}).get("summary", {})
                warning_count = summary_data.get("services_warning", "UNK")
                critical_count = summary_data.get("services_critical", "UNK")
                intent_detected = system_context.get("intent_classification", "UNKNOWN")
                
                fallback_payload = (
                    " **[SRE Agent Fallback Mode]**: Upstream LLM reasoning endpoints are experiencing high demand.\n"
                    "Deploying deterministic platform analysis from local pipeline cache state:\n\n"
                    "--- \n"
                    f"• **Classified Routing Intent**: `{intent_detected}`\n"
                    f"• **Active Infrastructure State Alerts**: Warnings: `{warning_count}` | Criticals: `{critical_count}`\n"
                    "• **Recommended Action**: The agent's core connection loop will auto-recover shortly. "
                    "Please analyze the live telemetry visualizations dashboard to maintain visual operational tracking."
                )
                await websocket.send_json({"type": "text", "content": fallback_payload})

    except WebSocketDisconnect:
        print(" Operator closed session chat context panels.")
    except Exception as server_err:
        print("Structural websocket framework error encountered!")
        traceback.print_exc()