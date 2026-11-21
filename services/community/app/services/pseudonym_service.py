import random

ADJECTIVES = [
    "Giant", "Crazy", "Brave", "Clever", "Swift", "Silent", "Wise", "Happy",
    "Fierce", "Golden", "Mighty", "Cosmic", "Curious", "Gentle", "Jolly",
    "Loyal", "Noble", "Quick", "Silly", "Witty", "Bold", "Calm", "Eager",
    "Radiant", "Serene", "Sturdy", "Vibrant", "Zesty", "Kind", "Lucky"
]

NOUNS = [
    "Elephant", "Dog", "Falcon", "Tiger", "Fox", "Panda", "Otter", "Lion",
    "Wolf", "Dolphin", "Eagle", "Bear", "Owl", "Hawk", "Koala", "Badger",
    "Cheetah", "Giraffe", "Penguin", "Zebra", "Beaver", "Bison", "Jaguar",
    "Lynx", "Panther", "Raven", "Seal", "Walrus", "Whale", "Antelope"
]


def generate_random_pseudonym() -> str:
    """Generate whimsical random pseudonym in the format '<Adjective> <Noun>'."""
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f"{adjective} {noun}"
