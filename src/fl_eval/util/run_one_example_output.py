import json
import shutil
from pathlib import Path
from typing import Any, cast

import config as gl
from fl_eval.metrics.scoring import ExamOutput, load_execution_metadata_from_cache
from fl_eval.strategies.autofix_ranker import AutoFixRanker
from fl_eval.strategies.llm_ranker import LLMRanker
from fl_eval.util.terminal_colors import Color, colored, separator
from fl_eval.util.trace_extractor import (
    extract_autofix_summary,
    extract_counterexample_base_summary,
    extract_counterexample_trace_summary,
    find_latest_autofix_csv,
)
from logging_config import get_logger

logger = get_logger(__name__)


def print_section(title: str) -> None:
    print("\n" + separator("="))
    print(colored(title, Color.HEADER + Color.BOLD))
    print(separator("="))


def print_one_example_intro(technique_name: str, dfy_path: Path) -> None:
    print("\n" + separator("="))
    print(colored("SINGLE FILE EVALUATION", Color.HEADER + Color.BOLD))
    print(separator("="))
    print_section("INPUT")
    print(f"{colored('Technique', Color.BOLD):24}: {technique_name}")
    print(f"{colored('Mutant File', Color.BOLD):24}: {dfy_path}")


def _chat_item_text(item: Any) -> str | None:
    if isinstance(item, str):
        return item

    if isinstance(item, dict):
        item_dict = cast(dict[str, Any], item)
        content = item_dict.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for part in cast(list[Any], content):
                if isinstance(part, dict):
                    part_dict = cast(dict[str, Any], part)
                    text = part_dict.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
            if chunks:
                return "".join(chunks)

    return None


def extract_prompt_and_response(chat_history: list[Any]) -> tuple[str | None, str | None]:
    prompt: str | None = None
    response: str | None = None

    for item in chat_history:
        if isinstance(item, dict):
            item_dict = cast(dict[str, Any], item)
            role = item_dict.get("role")
            text = _chat_item_text(item)
            if role == "user" and text is not None and prompt is None:
                prompt = text
            elif role == "assistant" and text is not None and response is None:
                response = text

    if prompt is None and response is None and chat_history:
        first = _chat_item_text(chat_history[0])
        second = _chat_item_text(chat_history[1]) if len(chat_history) > 1 else None
        prompt = first
        response = second

    return prompt, response


def print_llm_trace_if_available(flt_name: str, fl_technique: Any) -> None:
    if not isinstance(fl_technique, LLMRanker):
        print(colored("ℹ Technique is not LLM-based; no prompt/response trace available.", Color.YELLOW))
        return

    chat_history = fl_technique.llm.get_chat_history()
    if not chat_history:
        print(
            colored(
                "⚠ No chat history recorded. This can happen on cache hits or if no LLM call was performed.",
                Color.YELLOW,
            )
        )
        return

    prompt, response = extract_prompt_and_response(chat_history)

    print(colored(f"Technique: {flt_name}", Color.CYAN))
    print(colored(f"Chat events captured: {len(chat_history)}", Color.CYAN))

    print("\n" + colored("PROMPT", Color.BLUE + Color.BOLD))
    print(separator("-"))
    print(prompt if prompt is not None else "<prompt unavailable>")

    print("\n" + colored("MODEL RESPONSE", Color.BLUE + Color.BOLD))
    print(separator("-"))
    print(response if response is not None else "<response unavailable>")


def print_counterexample_trace_if_available(
    flt_name: str,
    execution_metadata: dict[str, Any] | None,
) -> None:
    if execution_metadata is None:
        print(colored("⚠ No cached execution metadata available for trace extraction.", Color.YELLOW))
        return

    stdout = execution_metadata.get("stdout")
    if not isinstance(stdout, str) or not stdout.strip():
        print(colored("⚠ Execution metadata has no stdout payload for trace extraction.", Color.YELLOW))
        return

    summary = None
    if flt_name == "counterBase":
        summary = extract_counterexample_base_summary(stdout)
    else:
        summary = extract_counterexample_trace_summary(stdout)

    if summary is None:
        print(colored("⚠ Could not parse counterexample trace payload from cached stdout.", Color.YELLOW))
        return

    print(colored(f"Trace Source: {summary.source}", Color.CYAN))
    print(colored(f"Traces Found: {summary.trace_count}", Color.CYAN))
    print(colored(f"Nodes Parsed: {summary.node_count}", Color.CYAN))
    print(colored(f"Unique Lines: {summary.unique_line_count}", Color.CYAN))
    print(colored("Raw:", Color.CYAN))
    print(json.dumps(summary.raw, indent=2))

    print("\n" + colored("TOP SUSPICIOUS LINES (frequency)", Color.BLUE + Color.BOLD))
    print(separator("-"))
    if summary.top_lines:
        for line, freq in summary.top_lines:
            print(f"Line {line:<6} Frequency {freq}")
    else:
        print("<no ranked lines found>")


def print_autofix_trace_if_available(flt_name: str, fl_technique: Any, dfy_path: Path) -> None:
    if not isinstance(fl_technique, AutoFixRanker):
        print(colored("⚠ Technique is not AutoFix-based; no AutoFix artifacts available.", Color.YELLOW))
        return

    csv_path = find_latest_autofix_csv(fl_technique.output_root, dfy_path.stem)
    if csv_path is None:
        print(colored("⚠ AutoFix CSV artifact not found for this mutant.", Color.YELLOW))
        return

    summary = extract_autofix_summary(csv_path)
    if summary is None:
        print(colored("⚠ AutoFix CSV could not be parsed or is empty.", Color.YELLOW))
        return

    print(colored(f"Artifact: {summary.csv_path}", Color.CYAN))
    print(colored(f"Ranked Lines: {summary.line_count}", Color.CYAN))
    print(colored(f"Score Range: {summary.min_score:.6f} .. {summary.max_score:.6f}", Color.CYAN))
    print(colored(f"Average Score: {summary.avg_score:.6f}", Color.CYAN))

    print("\n" + colored("TOP SUSPICIOUS LINES (score)", Color.BLUE + Color.BOLD))
    print(separator("-"))
    for line, score in summary.top_lines:
        print(f"Line {line:<6} Score {score:.6f}")


def print_technique_trace(
    flt_name: str,
    fl_technique: Any,
    dfy_path: Path,
    execution_metadata: dict[str, Any] | None,
) -> None:
    print_section("TECHNIQUE TRACE")

    if isinstance(fl_technique, LLMRanker):
        print_llm_trace_if_available(flt_name, fl_technique)
        return

    if flt_name in {"counterBase", "counterExampleIf", "counterExampleIfReassume"}:
        print_counterexample_trace_if_available(flt_name, execution_metadata)
        return

    if isinstance(fl_technique, AutoFixRanker):
        print_autofix_trace_if_available(flt_name, fl_technique, dfy_path)
        return

    print(colored("ℹ No rich trace renderer configured for this technique.", Color.YELLOW))


def print_single_file_summary(
    flt_name: str,
    dfy_path: Path,
    diff_path: Path,
    score: ExamOutput,
) -> None:
    print_section("EVALUATION SUMMARY")

    found_icon = "✓" if score.file.found else "✗"
    found_color = Color.GREEN if score.file.found else Color.RED

    print(f"{colored('Technique', Color.BOLD):24}: {flt_name}")
    print(f"{colored('Mutant File', Color.BOLD):24}: {dfy_path}")
    print(f"{colored('Diff File', Color.BOLD):24}: {diff_path}")
    print(f"{colored('Ground Truth Line', Color.BOLD):24}: {score.method.line_ground_truth}")
    print(f"{colored('Predictions (File)', Color.BOLD):24}: {score.file.line_prediction}")
    print(f"{colored('Predictions (Method)', Color.BOLD):24}: {score.method.line_prediction}")
    print(f"{colored('File EXAM', Color.BOLD):24}: {score.file.score:.6f}")
    print(f"{colored('Method EXAM', Color.BOLD):24}: {score.method.score:.6f}")
    print(
        f"{colored('Fault Found (File)', Color.BOLD):24}: "
        f"{colored(f'{found_icon} {score.file.found}', found_color + Color.BOLD)}"
    )
    print(f"{colored('Cache Path', Color.BOLD):24}: {gl.get_file_cache_path(dfy_path, flt_name)}")


def clean_cache_for_run(dfy_path: Path, technique_name: str, enable_pretty_output: bool = True) -> None:
    cache = gl.get_file_cache_path(dfy_path, technique_name)
    if enable_pretty_output:
        print_section("CACHE")
        print(f"{colored('Target Cache', Color.BOLD):24}: {cache}")

    if cache.exists():
        try:
            if cache.is_dir():
                shutil.rmtree(cache)
            else:
                cache.unlink()
            if enable_pretty_output:
                print(colored("✓ Removed cache entry", Color.GREEN + Color.BOLD))
        except OSError as e:
            if enable_pretty_output:
                print(colored(f"✗ Could not remove cache entry: {e}", Color.RED + Color.BOLD))
            else:
                logger.error("Could not remove cache entry %s: %s", cache, e)
    elif enable_pretty_output:
        print(colored("ℹ No cache entry found; running fresh evaluation.", Color.YELLOW))


def render_one_example_pretty_result(
    flt_name: str,
    dfy_path: Path,
    fl_technique: Any,
    score: ExamOutput,
    diff_path: Path,
    gtruth: Any,
    dataset_dir: Path,
) -> None:
    execution_metadata = load_execution_metadata_from_cache(fl_technique, gtruth, dataset_dir)
    print_technique_trace(
        flt_name,
        fl_technique,
        dfy_path,
        execution_metadata,
    )
    print_single_file_summary(flt_name, dfy_path, diff_path, score)

    if isinstance(fl_technique, LLMRanker):
        print_section("LLM COST ESTIMATE")
        fl_technique.get_costs()
