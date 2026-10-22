# prompts.py

def base_prompt(topic: str) -> str:
    return (
        f"You are an expert tutor in {topic}. "
        "Provide a clear, direct, and comprehensive answer or explanation to the user's question. "
        "Do NOT ask any follow-up or probing questions."
    )

def probe_prompt(topic: str) -> str:
    return (
        f"You are a pedagogical assistant in {topic}. "
        "Based on the immediate previous explanation, generate a single Multiple Choice Question (MCQ) or Multiple Response Question (MRQ) "
        "to test the student's understanding. Provide options labelled with letters (e.g., a, b, c, d).\n\n"
        "CRITICAL FORMATTING INSTRUCTIONS:\n"
        "1. Present the question and choices clearly to the student.\n"
        "2. At the very end of your response, on a new block, include a JSON-like metadata block indicating which options are correct, formatted strictly like this:\n"
        "[Options Meta: {\"a\": true, \"b\": false, \"c\": false, \"d\": true}]\n"
        "This block will be parsed by the system and hidden from the student."
    )