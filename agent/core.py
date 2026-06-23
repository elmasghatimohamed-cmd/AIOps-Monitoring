import os
from typing import List, Dict, Any
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

class AIAgentCore:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key :
            raise ValueError(
                "Missing credentials. Please check your root .env file configuration."
            )
            
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o"
        
        # Rigorous operational mandates for the AUI Data Center architecture
        self.system_guidance = (
            "You are the AUI Data Center AI Operations Intelligence Agent, an advanced reasoning "
            "layer built directly on top of the deterministic Centreon monitoring engine.\n\n"
            "OPERATIONAL GUIDELINES:\n"
            "1. You will be passed a real-time Markdown telemetry context snapshot at each turn. Use it as your source of truth.\n"
            "2. When clarifying warnings or critical failures, intelligently correlate metrics "
            "(e.g., cross-referencing high CPU Load with process counts, or database anomalies with connectivity values).\n"
            "3. Offer precise, production-focused engineering insights. Avoid speculation on architectural items not visible in your snapshot.\n"
            "4. Maintain an objective, calm, and highly technical tone."
        )

    async def run(self, user_message: str, live_context: str, chat_history: List[Dict[str, str]]) -> str:
        """
        Processes real-time operations telemetry and user messages via GPT-4o.
        """
        messages = [
            {"role": "system", "content": self.system_guidance},
            {"role": "system", "content": f"=== CURRENT LIVE INFRASTRUCTURE CONTEXT ===\n{live_context}"}
        ]
        
        # Maintain conversational thread depth limits
        for past_interaction in chat_history[-6:]:
            messages.append(past_interaction)
            
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=750
            )
            return response.choices[0].message.content or "No response returned."
        except Exception as e:
            return f"Agent Core Inference Exception: {str(e)}"

ai_agent_core = AIAgentCore()