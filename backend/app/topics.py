"""Simple keyword-based topic detection for CS questions."""

# Supported CS topic list used for keyword matching against student messages.
CS_TOPICS = [
    "Arrays & Strings",
    "Linked Lists",
    "Trees & Graphs",
    "Dynamic Programming",
    "Sorting & Searching",
    "Recursion",
    "Big-O & Complexity",
    "Hash Tables",
    "OOP Concepts",
    "Databases & SQL",
    "Networking",
    "Operating Systems",
    "Algorithms",
    "Data Structures",
    "System Design",
    "Python",
    "JavaScript",
    "Java",
    "C/C++",
    "React",
    "APIs & REST",
    "Git & Version Control",
    "Design Patterns",
    "Concurrency",
    "Memory Management",
]


def detect_topic(message: str) -> str:
    """Detect the CS topic from a student message using keyword matching.

    Compares the first word of each known topic against the lowercased
    message. Returns the first matching topic or a generic fallback.

    Args:
        message: The student's raw message text.

    Returns:
        The matched topic name, or ``"CS/Programming"`` if no match is found.
    """
    lower = message.lower()
    for topic in CS_TOPICS:
        first_word = topic.lower().split(" ")[0]
        if first_word in lower:
            return topic
    return "CS/Programming"
