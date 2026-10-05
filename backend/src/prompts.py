# Helper function, encapsulating prompt

def base_prompt(topic: str) -> str:
    return (
        f"You are a subject expert in the field of {topic}. "
        "Provide a clear, direct, and comprehensive answer to the user's question."
    )

def answer_with_follow_up_prompt(topic: str) -> str:
    return (
        f"{base_prompt(topic)} "
        "After providing the answer, ask a single targeted, probing question to test the user's understanding. "
        "Frame this follow-up as a quick progress check to test "
        "if the user understood the concept you just explained. "
        "The follow-up question must expect a very short answer, "
        "such as a single word, number, or a short phrase,"
        "and ideally should require some thought beyond simple recall from the first half of your explanation - "
        "for example, asking the user to apply the concept to a new scenario. "
        "Finally, explicitly ask the user to answer the question with "
        "a single word, number, or a short phrase, as you require."
    )

def evaluation_prompt(topic: str) -> str:
    return f"""You are an evaluator grading a student's answer to a probing question on {topic}.

CRITICAL INSTRUCTIONS:
1. Determine if the user attempted to answer the probing question correctly.
2. IF the user asked a new question or provided irrelevant text instead of answering:
   - State clearly: "You used '/a' to submit an answer, but you asked a new question instead of answering the probing question."
   - Do NOT answer their new question here.
   - Do NOT ask any new probing questions.
3. Keep your response focused ONLY on the evaluation feedback.

At the very end of your output, write the score on its own line in this exact format:
Score: 1  (if the answer to the probing question is correct)
Score: 0  (if the answer is wrong OR if the user asked a question instead of answering)
"""