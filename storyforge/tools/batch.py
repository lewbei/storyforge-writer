from typing import Union


def batch_generate_impl(num_chapters: int, auto_continue: bool) -> str:
    """Return a structured status message for batch chapter generation.

    This function does not perform any model calls or file I/O.
    It simply encodes the requested batch parameters so the orchestrator
    (main loop) can decide how to act.
    """
    try:
        n = int(num_chapters)
    except (TypeError, ValueError):
        return "STATUS: ERROR | message=invalid num_chapters"

    if n <= 0:
        return "STATUS: ERROR | message=num_chapters must be positive"

    return (
        f"STATUS: READY | requested_chapters={n} | "
        f"auto_continue={'True' if auto_continue else 'False'}"
    )
