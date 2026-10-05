#!/usr/bin/env python
 
# Test file for the chat application

import sys
import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from graph import app_graph

load_dotenv()

def main():
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    print("=== LearnLoop CLI Session ===")
    print(f"Session Thread ID: {session_id}")
    print("Commands:")
    print("  <your question>     : Ask a new question (default behaviour, ignores active probing check)")
    print("  /a <your answer>    : Answer the active probing question")
    print("  /exit OR /quit           : Terminate session\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["/exit", "/quit"]:
                print("Ending session. Goodbye!")
                break

            # Get current graph state to check if we are currently awaiting evaluation
            current_state = app_graph.get_state(config)
            is_awaiting_eval = current_state.values.get("awaiting_eval", False) if current_state.values else False

            # Case 1: User explicitly wants to answer the probing question using /a
            if user_input.startswith("/a"):
                clean_answer = user_input[2:].strip()
                if not clean_answer:
                    print("[System]: Please provide your answer after /a (e.g. /a eigenvector)")
                    continue
                
                if not is_awaiting_eval:
                    print("[System]: There is currently no active probing question to answer. Treating as a new question...\n")
                    user_input = clean_answer
                else:
                    user_input = clean_answer

            # Case 2: Default behaviour - user typed a prompt without /a
            else:
                # If a probing question was active, explicitly clear awaiting_eval state to ask a new question
                if is_awaiting_eval:
                    app_graph.update_state(config, {"awaiting_eval": False})

            inputs = {"messages": [HumanMessage(content=user_input)]}
            result = app_graph.invoke(inputs, config=config)

            # Update user_stats if evaluation just completed

            if not result.get("awaiting_eval") and "user_stats" in result:
                board = result["user_stats"]
                score = result.get("score", 0)
                print(f"\n[Evaluation Response]:\n{latest_message.content}\n")
                print("--------------------------------------------------")
                print(f"   USER STATISTICS (Current Run):")
                print(f"   • Result         : {'Correct (1/1)' if score == 1 else 'Incorrect (0/1)'}")
                print(f"   • Total Attempts : {board['total_attempts']}")
                print(f"   • Total Score    : {board['total_score']} / {board['total_attempts']}")
                print(f"   • Current Streak : {board['curr_streak']} ")
                print(f"   • Best Streak    : {board['best_streak']} ")
                print("--------------------------------------------------\n")
            
            latest_message = result["messages"][-1]
            
            # Print execution mode feedback
            if result.get("awaiting_eval"):
                print(f"\n[Tutor Response + Probing Question]:\n{latest_message.content}\n")
                print("--> (Side Panel: Probing question active. Type '/a <answer>' to answer it, or just type your next question to ignore it.)\n")
            else:
                print(f"\n[Evaluation Response]:\n{latest_message.content}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSession interrupted. Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    main()