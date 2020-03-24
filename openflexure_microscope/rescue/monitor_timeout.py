import multiprocessing
import logging
import time

# bar
def test_long_fn():
    for _ in range(100):
        print("Tick")
        time.sleep(1)


def launch_timeout_test_process(target, args=(), kwargs=None, timeout=10):
    if not kwargs:
        kwargs = {}

    # Start target as a process
    p = multiprocessing.Process(target=target, args=args, kwargs=kwargs)
    p.start()

    # Wait for 10 seconds or until process finishes
    p.join(timeout)

    # If thread is still active
    if p.is_alive():
        logging.error(
            f"Function {target} reached timeout after {timeout} seconds. Terminating."
        )

        # Terminate
        p.terminate()
        p.join()

        return False
    else:
        return True


if __name__ == "__main__":
    launch_timeout_test_process(test_long_fn, timeout=5)
