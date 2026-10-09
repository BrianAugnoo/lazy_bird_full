"""How urgent work is: the lower the number, the sooner it runs (and the more it may displace).

Only the rank matters, not the gaps. ``NOW`` never comes from the program: it is what a
user asks for when a task must run immediately.
"""

NOW = 0
SEARCH = 1
INFERENCE = 2
BACKGROUND = 5  # embedding, chunking, downloads... the default of a task
