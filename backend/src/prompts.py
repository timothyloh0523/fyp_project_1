# Helper function, encapsulating prompt
def build_initial_prompt(topic: str) -> str:
    return f"You are a subject expert in the field of {topic}."

def build_direct_answer_prompt(topic: str) -> str:
    return (
        f"{build_initial_prompt(topic)} "
        "Provide a clear, direct, and comprehensive answer to the user's question."
    )

def build_probing_question_prompt(topic: str) -> str:
    return (
        f"{build_initial_prompt(topic)} "
        "Do NOT give away the direct answer. Instead, ask a single targeted, probing question "
        "or hint to guide the user toward discovering the answer themselves and test their understanding."
    )