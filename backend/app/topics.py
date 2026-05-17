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
    lower = message.lower()
    for topic in CS_TOPICS:
        first_word = topic.lower().split(" ")[0]
        if first_word in lower:
            return topic
    return "CS/Programming"
