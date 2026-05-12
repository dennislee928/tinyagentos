"""taosctl — command-line interface for taOS.

Agents inside containers and human operators use the same binary. Auth via
the TAOS_TOKEN env var (auto-set in agent containers) or
`taosctl auth login` for humans. Server URL via TAOS_URL (defaults to
http://localhost:6969).
"""
__version__ = "0.1.0"
