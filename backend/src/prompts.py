# Helper function, encapsulating prompt

def base_prompt(topic: str) -> str:
    return (
        f"You are a subject expert in the field of {topic}. "
        "Provide a clear, direct, and comprehensive answer to the user's question."
    )

def answer_with_follow_up_prompt(topic: str) -> str:
    return (
        f"{base_prompt(topic)} "
        "After providing the answer, ask a single targeted, probing question "
        "to test the user's understanding."
        "Frame this follow-up as a quick progress check to test if the user "
        "understood the concept you just explained."
        "The follow-up question must expect a very short answer, "
        "such as a single word, number, or a short phrase."
        "Finally, explicitly ask the user to answer the question with "
        "a single word, number, or a short phrase, as you require."
    )

def evaluation_prompt(topic: str) -> str:
    return (
        f"You are a subject expert in the field of {topic}. "
        "Evaluate the user's answer to the progress check question you previously asked. "
        "Determine their level of understanding and score it on a scale from 1 to 5 "
        "(1 = complete misunderstanding, 5 = thorough mastery). "
        "Provide brief constructive feedback along with the score formatted clearly as 'Score: X/5'."
    )