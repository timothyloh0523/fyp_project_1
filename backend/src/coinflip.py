import random

def flip_coin() -> str:
    """Returns 'heads' for direct answer or 'tails' for probing question."""
    return "heads" if random.choice([True, False]) else "tails"