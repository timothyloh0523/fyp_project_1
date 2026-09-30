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

    print("=== LearnLoop Interactive CLI ===")
    print(f"Session Thread ID: {session_id}\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Ending session. Goodbye!")
                break

            inputs = {"messages": [HumanMessage(content=user_input)]}
            result = app_graph.invoke(inputs, config=config)
            
            latest_message = result["messages"][-1]
            print(f"\nTutor: {latest_message.content}\n")

            # Check if state is waiting for follow-up progress answer
            if result.get("awaiting_eval"):
                print("--- [PROGRESS CHECK ACTIVE] ---")
                answer_input = input("Your Answer (Short phrase/word): ").strip()
                
                eval_inputs = {"messages": [HumanMessage(content=answer_input)]}
                eval_result = app_graph.invoke(eval_inputs, config=config)
                
                eval_message = eval_result["messages"][-1]
                print(f"\n[Evaluation Node]:\n{eval_message.content}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSession interrupted. Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    main()