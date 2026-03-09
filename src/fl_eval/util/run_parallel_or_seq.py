import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, TypeVar
from tqdm import tqdm
import psutil


R = TypeVar('R')

# 1. The Core Limit (Physical reality)
PHYSICAL_CORES = psutil.cpu_count(logical=False) or 1
SAFE_THREADS = max(1, PHYSICAL_CORES)
CPU_LIMITER = threading.BoundedSemaphore(SAFE_THREADS)

# 2. The Management Limit (Virtual capacity)
# We set this high enough that you'll never run out of "manager" slots.
# 5,000 threads is well within the limits of modern OSs for sleeping threads.
MAX_MANAGEMENT_THREADS = 5000
_SHARED_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_MANAGEMENT_THREADS)

def run_parallel_or_seq(items: Iterable[Any], task_fn: Callable[..., R], desc: str, *task_args: Any, parallel: bool = True) -> list[R]:
    results: list[Any] = []
    cdesc = desc + f" (Active Cores:{SAFE_THREADS})"

    def semaphore_task(item : Any):
        # The 'parent' thread stays alive but 'blocks' here,
        with CPU_LIMITER:
            return task_fn(item, *task_args)

    if parallel:
        # We use the massive pool so we can always fit 'parent' tasks
        futures = {
            _SHARED_EXECUTOR.submit(semaphore_task, item): item
            for item in items
        }
        
        for future in tqdm(as_completed(futures), total=len(futures), desc=cdesc):
            item = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                print(f"[Warning] Error processing {item}: {e}")
    else:
        for item in tqdm(items, desc=f"{cdesc} (seq)"):
            try:
                with CPU_LIMITER:
                    results.append(task_fn(item, *task_args))
            except Exception as e:
                print(f"[Warning] Error processing {item}: {e}")

    return results
