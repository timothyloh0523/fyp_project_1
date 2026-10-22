#!/usr/bin/env python

# Test file for the chat application (Debugging Edition)

import sys
import uuid
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from graph import app_graph
from db.database import get_user_stats

load_dotenv()

async def main():
    session_id = str(uuid.uuid4())
    user_id = "cli_user"  # Default user ID for testing
    config = {"configurable": {"thread_id": session_id}}

    print("=== LearnLoop CLI [DEBUG MODE] ===")
    print(f"Session Thread ID: {session_id}")
    print("Commands:")
    print("  <your question>     : Ask a new tutor question")
    print("  /a <option(s)>      : Answer active probe (e.g., /a a or /a a, c)")
    print("  /exit OR /quit      : Terminate session\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["/exit", "/quit"]:
                print("Ending session. Goodbye!")
                break

            # Get current graph state
            current_state = app_graph.get_state(config)
            is_awaiting_eval = current_state.values.get("awaiting_eval", False) if current_state.values else False

            # Check if user explicitly used /a
            is_explicit_answer = user_input.startswith("/a")
            if is_explicit_answer:
                clean_answer = user_input[2:].strip()
                if not clean_answer:
                    print("[DEBUG System]: Please provide your answer choice after /a (e.g. /a a)")
                    continue
                user_input = clean_answer
            else:
                # If a probe was active and user typed a regular question instead, clear state
                if is_awaiting_eval:
                    app_graph.update_state(config, {"awaiting_eval": False, "options_list": None})

            # Fetch existing stats from DB
            existing_stats = get_user_stats(user_id)

            inputs = {
                "messages": [HumanMessage(content=user_input)],
                "awaiting_eval": is_explicit_answer and is_awaiting_eval,
                "user_id": user_id,
                "user_stats": existing_stats
            }
            
            result = await app_graph.ainvoke(inputs, config=config)
            messages = result.get("messages", [])
            
            # 1. If evaluation just completed
            if not result.get("awaiting_eval") and "user_stats" in result:
                stats = result["user_stats"]
                score = result.get("score", 0)
                latest_message = messages[-1] if messages else None
                eval_text = latest_message.content if latest_message else ""
                
                print(f"\n[EVALUATION FEEDBACK]:\n{eval_text}")
                print(f"[STATS UPDATE] Score: {score} | Streak: {stats['curr_streak']} (Best: {stats['best_streak']}) | Total: {stats['total_score']}/{stats['total_attempts']}\n" + "-"*50)
            
            # 2. If a new probing question was generated (Tutor explanation + Prober question are both in messages)
            elif result.get("awaiting_eval"):
                # Typically, messages[-2] is the tutor response and messages[-1] is the prober question
                tutor_text = messages[-2].content if len(messages) >= 2 else "(Tutor message missing)"
                probe_text = messages[-1].content if len(messages) >= 1 else "(Probe message missing)"
                
                options_list = result.get("options_list", [])
                correct_options = [item["option"] for item in options_list if item["is_correct"]]
                
                print(f"\n[TUTOR EXPLANATION]:\n{tutor_text}")
                print(f"\n[PROBING QUESTION]:\n{probe_text}")
                print(f"\n--- [DEBUG STATE INFO] ---")
                print(f"• Raw Options Meta List : {options_list}")
                print(f"• Expected Correct Key(s): {correct_options}")
                print(f"--------------------------\n")
            
            # 3. Regular Tutor Response (Fallback if no prober ran)
            else:
                latest_message = messages[-1] if messages else None
                response_text = latest_message.content if latest_message else ""
                print(f"\n[TUTOR RESPONSE]:\n{response_text}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSession interrupted. Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
