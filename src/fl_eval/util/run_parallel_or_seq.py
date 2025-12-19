import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, TypeVar
from tqdm import tqdm

R = TypeVar('R')  # Return type of task_fn

def run_parallel_or_seq(parallel : bool, desc : str, items: Iterable[Any] , task_fn: Callable[..., R], *task_args: Any) -> list[R]:
    """
    Runs `task_fn(item, *task_args)` either in parallel or sequentially.
    
    Args:
        items (iterable): List of work items.
        task_fn (callable): Function that takes (item, *task_args).
        desc (str): Description for tqdm progress bar.
        *task_args: Extra arguments to pass to the task function.
        parallel (bool): Whether to use threads or run sequentially.
    
    Returns:
        List of results (or None for failed tasks).
    """
    results: list[Any] = []
    safe_threads: int = 1
    if parallel:
        PHYSICAL_CORES: int = (os.cpu_count() or 1)
        safe_threads = max(1, PHYSICAL_CORES - 1)

    cdesc = desc + f" (Cores:{safe_threads})"
    if parallel:
        with ThreadPoolExecutor(max_workers=safe_threads) as executor:
            futures = {
                executor.submit(task_fn, item, *task_args): item
                for item in items
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc=cdesc):
                item = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"[Warning] Error processing {item}: {e}")
    else:
        for item in tqdm(items, desc=f"{cdesc} (sequential)"):
            try:
                results.append(task_fn(item, *task_args))
            except Exception as e:
                print(f"[Warning] Error processing {item}: {e}")

    return results