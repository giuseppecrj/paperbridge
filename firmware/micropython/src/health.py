def snapshot(ethernet, queue):
    return {"ethernet": ethernet.status(), "queue": queue.status()}
