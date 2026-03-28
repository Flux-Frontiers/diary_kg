"""transformer.py — DiaryTransformer: the main orchestrator class.

``DiaryTransformer`` wires together the parsing, chunking, feature, and
classification modules into two public workflows:

``transform_file``
    One-shot batch: parse → chunk-cache → diverse-sample → classify → save.

``transform_file_incremental``
    Resumable: same pipeline but tracks injected indices in a ``StateManager``
    so repeated runs only process new entries.
"""

from __future__ import annotations

import multiprocessing as mp
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

import spacy
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from sentence_transformers import SentenceTransformer

from .chunker import segment_content
from .classifier import (
    classify_chunk_hybrid,
    discover_semantic_categories,
    extract_context,
)
from .features import select_diverse_sample
from .models import DiaryEntry, EntryChunk
from .parser import parse_diary_file
from .state import (
    StateManager,
    filter_uninjected,
    load_chunks_from_cache,
    save_chunks_to_cache,
)

console = Console()

try:
    _TRANSFORMER_VERSION = _pkg_version("diary-kg")
except PackageNotFoundError:
    _TRANSFORMER_VERSION = "unknown"


def write_run_summary(
    output_path: str, run_params: dict, stats: dict, summary_file: str | None = None
) -> str:
    """Write a Markdown provenance summary alongside the output file.

    The summary is written to ``<output_stem>_run_summary.md`` in the same
    directory as *output_path*.

    :param output_path: Path to the primary output file.
    :param run_params: Run parameters dict (timestamp, input_file, etc.).
    :param stats: Counts dict with keys ``entries_parsed``, ``entries_selected``,
        ``entries_generated``, ``time_range_start``, ``time_range_end``.
    :return: Path to the written summary file.
    """
    out = Path(output_path)
    summary_path = Path(summary_file) if summary_file else out.parent / f"{out.stem}_run_summary.md"

    cmd = " ".join(sys.argv)
    ts = run_params.get("timestamp", datetime.now().isoformat())
    dt = datetime.fromisoformat(ts)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    lines = [
        "# Diary Transformer — Run Summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Date | {date_str} |",
        f"| Time | {time_str} |",
        f"| Version | {_TRANSFORMER_VERSION} |",
        "",
        "## Invocation",
        "",
        "```",
        cmd,
        "```",
        "",
        "## Inputs & Outputs",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Input file | `{run_params.get('input_file', '—')}` |",
        f"| Output file | `{output_path}` |",
        "",
        "## Run Parameters",
        "",
        "| Parameter | Value |",
        "|---|---|",
    ]
    skip = {"timestamp", "input_file"}
    for key, val in run_params.items():
        if key in skip:
            continue
        label = key.replace("_", " ").title()
        lines.append(f"| {label} | `{val}` |")

    time_range_start = stats.get("time_range_start", "—")
    time_range_end = stats.get("time_range_end", "—")
    lines += [
        "",
        "## Pipeline Statistics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Entries parsed | {stats.get('entries_parsed', '—')} |",
        f"| Entries selected | {stats.get('entries_selected', '—')} |",
        f"| Entries generated | {stats.get('entries_generated', '—')} |",
        f"| Time range | {time_range_start} → {time_range_end} |",
        f"| Runtime | {stats.get('runtime_s', 0):.1f}s |",
        "",
    ]

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[bold green]✓[/bold green] Run summary → {summary_path}")
    return str(summary_path)


class DiaryTransformer:
    """Transform diary entries into semantic memory chunks.

    :param max_chunk_length: Hard character cap per chunk.
    :param num_workers: Parallel workers for feature extraction (1 = sequential).
    :param topics_file: Path to a YAML topics file; defaults to ``topics.yaml``
        bundled with this package.
    :param chunking_strategy: ``"semantic"``, ``"sentence_group"`` (default), or
        ``"hybrid"``.
    :param sentences_per_chunk: Sentences per chunk for ``sentence_group`` /
        ``hybrid`` strategies.
    """

    def __init__(
        self,
        max_chunk_length: int = 512,
        num_workers: int = 1,
        topics_file: str | None = None,
        chunking_strategy: str = "sentence_group",
        sentences_per_chunk: int = 4,
    ) -> None:
        self.max_chunk_length = max_chunk_length
        self.chunking_strategy = chunking_strategy
        self.sentences_per_chunk = sentences_per_chunk
        self.num_workers = max(1, min(num_workers, mp.cpu_count()))
        self.topics_file = topics_file
        self._current_input_path: str | None = None
        self._init_models()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_models(self) -> None:
        console.print("[dim]Loading NLP models...[/dim]")

        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            console.print(
                "[bold red]Error: spaCy model not found. Run: python -m spacy download en_core_web_sm[/bold red]"
            )
            sys.exit(1)

        try:
            self.sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            console.print(f"[bold red]Error loading sentence transformer: {exc}[/bold red]")
            sys.exit(1)

        self.topic_classifier: Any | None = None
        try:
            from .topic_classifier import TopicClassifier  # pylint: disable=import-outside-toplevel

            path = self.topics_file or str(Path(__file__).parent / "topics.yaml")
            self.topic_classifier = TopicClassifier(path)
            console.print(f"[bold green]✓[/bold green] Loaded TopicClassifier: [dim]{path}[/dim]")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            console.print(
                f"[yellow]Warning: TopicClassifier unavailable ({exc}); using unsupervised only[/yellow]"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _segment(
        self,
        content: str,
        max_chunks_per_entry: int = 3,
        timestamp: datetime | None = None,
    ) -> list[str]:
        return segment_content(
            content=content,
            nlp=self.nlp,
            sentence_model=self.sentence_model,
            max_chunk_length=self.max_chunk_length,
            chunking_strategy=self.chunking_strategy,
            sentences_per_chunk=self.sentences_per_chunk,
            max_chunks_per_entry=max_chunks_per_entry,
            timestamp=timestamp,
        )

    def _load_or_build_cache(self, input_path: str) -> list[DiaryEntry]:
        """Return entries from chunk cache, building it first if absent."""
        self._current_input_path = input_path
        base = Path(input_path).parent / f"{Path(input_path).stem}_chunks.json"
        pkl = Path(str(base).replace(".json", ".pkl"))

        if pkl.exists() or base.exists():
            console.print("[bold green]✓[/bold green] Found chunk cache, loading...")
            return load_chunks_from_cache(str(base))

        console.print("[dim]No chunk cache found, parsing and chunking all entries...[/dim]")
        entries = parse_diary_file(input_path)
        for idx, entry in enumerate(entries):
            entry.index = idx
        save_chunks_to_cache(entries, str(base), self._segment)
        return load_chunks_from_cache(str(base))

    # ------------------------------------------------------------------
    # Core transform pipeline
    # ------------------------------------------------------------------

    def transform_entries(
        self,
        entries: list[DiaryEntry],
        seed: int | None = None,
        max_chunks_per_entry: int = 3,
    ) -> list[EntryChunk]:
        """Segment, categorise, and classify a list of diary entries.

        :param entries: Entries to transform.
        :param seed: RNG seed for reproducible category discovery.
        :param max_chunks_per_entry: Max chunks emitted per entry.
        :return: List of ``EntryChunk`` objects.
        """
        console.print(f"Transforming [bold]{len(entries)}[/bold] entries into memory chunks")

        all_chunks: list[tuple] = []
        chunk_texts: list[str] = []

        _progress_columns = (
            SpinnerColumn(),
            BarColumn(),
            TextColumn("{task.description} {task.completed}/{task.total}"),
            TimeElapsedColumn(),
        )

        with Progress(*_progress_columns, console=console) as progress:
            seg_task = progress.add_task("Segmenting entries", total=len(entries))
            for idx, entry in enumerate(entries):
                for chunk in self._segment(entry.content, max_chunks_per_entry, entry.timestamp):
                    all_chunks.append((idx, entry, chunk))
                    chunk_texts.append(chunk)
                progress.advance(seg_task)

        console.print(f"Created [bold]{len(all_chunks)}[/bold] semantic chunks")

        categories = discover_semantic_categories(chunk_texts, seed=seed)

        memory_chunks: list[EntryChunk] = []
        with Progress(*_progress_columns, console=console) as progress:
            cls_task = progress.add_task("Classifying chunks", total=len(all_chunks))
            for entry_idx, entry, chunk in all_chunks:
                category, topic_scores = classify_chunk_hybrid(
                    chunk, categories, self.topic_classifier
                )
                context = extract_context(chunk, self.nlp)
                memory_chunks.append(
                    EntryChunk(
                        timestamp=entry.timestamp,
                        semantic_category=category,
                        context_classification=context,
                        content=chunk,
                        confidence=1.0,
                        phase="immediate",
                        source_entry_index=entry_idx,
                        source_entry=entry,
                        topics=topic_scores,
                    )
                )
                progress.advance(cls_task)

        console.print(f"Generated [bold]{len(memory_chunks)}[/bold] memory chunks")
        return memory_chunks

    def save_entries(
        self,
        entries: list[EntryChunk],
        output_path: str,
        run_params: dict | None = None,
    ) -> None:
        """Write chunks to a pipe-delimited output file with provenance headers.

        :param entries: Chunks to write.
        :param output_path: Destination file path.
        :param run_params: Run metadata written as comment header lines.
        """
        console.print(f"Saving [bold]{len(entries)}[/bold] entries to {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            if run_params:
                f.write("# Diary Transformer - Run Parameters\n")
                for key in (
                    "timestamp",
                    "input_file",
                    "batch_size",
                    "chunk_size",
                    "max_chunks_per_entry",
                    "seed",
                ):
                    f.write(
                        f"# {key.replace('_', ' ').title()}: {run_params.get(key, 'Unknown')}\n"
                    )
                f.write("#\n")

            f.write("# ======== ENTRIES ========\n\n")
            current_source: DiaryEntry | None = None
            for memory in entries:
                source = getattr(memory, "source_entry", None)
                sidx = getattr(memory, "source_entry_index", None)
                if source and source is not current_source:
                    current_source = source
                    ts = source.timestamp.strftime("%Y-%m-%d %H:%M")
                    preview = source.content[:100] + ("..." if len(source.content) > 100 else "")
                    f.write(f"\n# === Source Entry #{(sidx or 0) + 1} ({ts}) ===\n")
                    f.write(f"# Original: {source.original_type} | {source.category}\n")
                    f.write(f"# Content: {preview}\n")
                    f.write("# Extracted entries:\n")
                ts = memory.timestamp.strftime("%Y-%m-%dT%H:%M")
                f.write(
                    f"{ts} | {memory.semantic_category} | "
                    f"{memory.context_classification} | {memory.content}\n"
                )
        console.print(f"[bold green]✓[/bold green] Entries saved to {output_path}")

    # ------------------------------------------------------------------
    # Public workflows
    # ------------------------------------------------------------------

    def transform_file(
        self,
        input_path: str,
        output_path: str,
        batch_size: int = 20,
        seed: int | None = None,
        max_chunks_per_entry: int = 3,
        summary_file: str | None = None,
    ) -> None:
        """One-shot transformation: parse, sample, transform, save.

        :param input_path: Pipe-delimited diary file.
        :param output_path: Output file for transformed chunks.
        :param batch_size: Number of diverse entries to process.
        :param seed: RNG seed.
        :param max_chunks_per_entry: Max chunks per diary entry.
        :param summary_file: Override path for the Markdown run summary.
        """
        console.print(
            f"Starting transformation: [dim]{input_path}[/dim] -> [dim]{output_path}[/dim]"
        )
        _t0 = datetime.now()
        entries = self._load_or_build_cache(input_path)
        if batch_size and len(entries) > batch_size:
            selected = select_diverse_sample(
                entries,
                batch_size,
                self.nlp,
                self.num_workers,
                input_file_path=self._current_input_path,
                seed=seed,
            )
        else:
            selected = entries
        memory_entries = self.transform_entries(
            selected, seed=seed, max_chunks_per_entry=max_chunks_per_entry
        )
        memory_entries.sort(key=lambda m: m.timestamp)
        run_params = {
            "timestamp": datetime.now().isoformat(),
            "input_file": str(input_path),
            "batch_size": batch_size,
            "chunk_size": self.max_chunk_length,
            "max_chunks_per_entry": max_chunks_per_entry,
            "chunking_strategy": self.chunking_strategy,
            "seed": seed,
        }
        self.save_entries(memory_entries, output_path, run_params)
        write_run_summary(
            output_path,
            run_params,
            {
                "entries_parsed": len(entries),
                "entries_selected": len(selected),
                "entries_generated": len(memory_entries),
                "time_range_start": memory_entries[0].timestamp.strftime("%Y-%m-%d")
                if memory_entries
                else "—",
                "time_range_end": memory_entries[-1].timestamp.strftime("%Y-%m-%d")
                if memory_entries
                else "—",
                "runtime_s": (datetime.now() - _t0).total_seconds(),
            },
            summary_file=summary_file,
        )
        console.print(
            f"[bold green]Transformation complete![/bold green] Generated [bold]{len(memory_entries)}[/bold] entries"
        )

    def ingest_to_corpus(
        self,
        input_path: str,
        corpus_dir: str,
        batch_size: int = 20,
        seed: int | None = None,
        max_chunks_per_entry: int = 3,
        source_file: str | None = None,
        embed_cache: str | None = None,
        embed_model: str = "nomic-ai/nomic-embed-text-v1",
        embed_workers: int = 0,
    ) -> int:
        """Transform diary entries and write DocKG-compatible Markdown files.

        Each chunk is written as a ``.md`` file with YAML frontmatter carrying
        provenance fields that ``DocKG`` can index.  The ``source_file`` value
        surfaces the original source ``.txt`` path — not the generated chunk
        file — so cross-KG queries can cite the real document.

        Optionally, after writing the corpus, embeds all chunk texts via
        ``diary_embedder.embed_multiprocess`` (nomic-ai model, multi-process)
        and writes a JSON cache consumable by ``pepys_manifold_explorer.py``.

        Directory layout::

            <corpus_dir>/
              entry_0042_chunk_0.md
              entry_0042_chunk_1.md
              ...

        Frontmatter fields per chunk::

            source_file: pepys_diary.txt
            entry_index: 42
            chunk_index: 0
            timestamp: 1667-04-15T22:30
            category: domestic
            context: Home

        :param input_path: Pipe-delimited diary source file.
        :param corpus_dir: Destination directory for generated ``.md`` files.
        :param batch_size: Number of diverse entries to sample (0 = all).
        :param seed: RNG seed for reproducible diversity sampling.
        :param max_chunks_per_entry: Max chunks emitted per entry.
        :param source_file: Override provenance path written into frontmatter.
            Defaults to the basename of *input_path*.
        :param embed_cache: If set, path for the JSON embedding cache produced
            by ``diary_embedder``.  Skipped when ``None`` (default).
        :param embed_model: HuggingFace model id passed to
            ``embed_multiprocess`` (default: ``nomic-ai/nomic-embed-text-v1``).
        :param embed_workers: Parallel embedding workers (0 = ``os.cpu_count()``).
        :return: Number of ``.md`` files written.
        """
        from pathlib import Path as _Path  # pylint: disable=import-outside-toplevel

        out_dir = _Path(corpus_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        src_label = source_file or _Path(input_path).name

        entries = self._load_or_build_cache(input_path)
        # Stamp source_file on every entry if not already set
        for e in entries:
            if not e.source_file:
                e.source_file = src_label

        if batch_size and len(entries) > batch_size:
            selected = select_diverse_sample(
                entries,
                batch_size,
                self.nlp,
                self.num_workers,
                input_file_path=self._current_input_path,
                seed=seed,
            )
        else:
            selected = entries

        memory_entries = self.transform_entries(
            selected, seed=seed, max_chunks_per_entry=max_chunks_per_entry
        )

        written = 0
        chunk_counter: dict[int, int] = {}
        for mem in memory_entries:
            eidx = mem.source_entry_index
            cidx = chunk_counter.get(eidx, 0)
            chunk_counter[eidx] = cidx + 1

            src = mem.source_entry
            sf = (src.source_file if src and src.source_file else src_label) if src else src_label

            # Serialize topics as "name:score,name:score" sorted by confidence.
            top_topics = sorted(mem.topics.items(), key=lambda x: x[1], reverse=True)[:5]
            topics_str = ",".join(f"{t}:{s:.4f}" for t, s in top_topics)

            frontmatter = (
                "---\n"
                f"source_file: {sf}\n"
                f"entry_index: {eidx}\n"
                f"chunk_index: {cidx}\n"
                f"timestamp: {mem.timestamp.strftime('%Y-%m-%dT%H:%M')}\n"
                f"category: {mem.semantic_category}\n"
                f"context: {mem.context_classification}\n"
                + (f"topics: {topics_str}\n" if topics_str else "")
                + "---\n"
            )

            # Semantic seeding: prepend topic labels so DocKG embeddings encode topic context.
            topic_labels = [t for t, _ in top_topics]
            if topic_labels:
                body = f"[Topics: {', '.join(topic_labels)}]\n\n{mem.content}\n"
            else:
                body = mem.content + "\n"

            fname = f"entry_{eidx:04d}_chunk_{cidx}.md"
            (out_dir / fname).write_text(frontmatter + "\n" + body, encoding="utf-8")
            written += 1

        console.print(
            f"[bold green]✓[/bold green] Wrote [bold]{written}[/bold] chunk files to {corpus_dir}"
        )

        if embed_cache:
            from .diary_embedder import (  # pylint: disable=import-outside-toplevel
                embed_multiprocess,
                save_cache,
            )

            console.print(
                f"\n[dim][Embedding] Building cache ({len(memory_entries)} chunks) → {embed_cache} …[/dim]"
            )
            embed_texts = [
                f"{m.semantic_category} | {m.context_classification} | {m.content}"
                for m in memory_entries
            ]
            embed_timestamps = [m.timestamp for m in memory_entries]
            E = embed_multiprocess(
                embed_texts,
                model=embed_model,
                n_workers=embed_workers or None,
            )
            save_cache(embed_cache, E, embed_texts, embed_timestamps)

        return written

    def transform_file_incremental(
        self,
        input_path: str,
        output_path: str,
        state_file: str,
        batch_size: int = 20,
        seed: int | None = None,
        max_chunks_per_entry: int = 3,
        resume_mode: bool = False,
        summary_file: str | None = None,
    ) -> None:
        """Incremental transformation with resumable state.

        :param input_path: Pipe-delimited diary file.
        :param output_path: Output file for transformed chunks.
        :param state_file: JSON file tracking injected entry indices.
        :param batch_size: Max entries per run.
        :param seed: RNG seed.
        :param max_chunks_per_entry: Max chunks per diary entry.
        :param resume_mode: If True, load existing state to skip processed entries.
        """
        console.print(
            f"Starting transformation: [dim]{input_path}[/dim] -> [dim]{output_path}[/dim]"
        )
        console.print(f"Resume mode: [bold]{resume_mode}[/bold]")
        _t0 = datetime.now()

        state = StateManager(state_file)
        if resume_mode:
            state.load(input_path)
            console.print(
                f"Loaded state: [bold]{len(state.injected_entry_indices)}[/bold] entries already injected"
            )

        entries = self._load_or_build_cache(input_path)
        available = filter_uninjected(entries, state.injected_entry_indices)

        if not available:
            console.print("[bold green]✓[/bold green] All entries already injected, nothing to do")
            return

        console.print(f"Found [bold]{len(available)}[/bold] entries available for injection")

        if len(available) > batch_size:
            selected = select_diverse_sample(
                available,
                batch_size,
                self.nlp,
                self.num_workers,
                input_file_path=self._current_input_path,
                seed=seed,
            )
        else:
            selected = available
            console.print(f"Processing all [bold]{len(selected)}[/bold] available entries")

        memory_entries = self.transform_entries(
            selected, seed=seed, max_chunks_per_entry=max_chunks_per_entry
        )
        memory_entries.sort(key=lambda m: m.timestamp)

        state.processing_stats["total_runs"] += 1
        state.processing_stats["total_entries_injected"] += len(selected)
        state.processing_stats["last_run"] = datetime.now().isoformat()
        state.mark_injected(selected)

        run_params = {
            "timestamp": datetime.now().isoformat(),
            "input_file": str(input_path),
            "batch_size": len(selected),
            "chunk_size": self.max_chunk_length,
            "max_chunks_per_entry": max_chunks_per_entry,
            "chunking_strategy": self.chunking_strategy,
            "seed": seed,
            "mode": "resume" if resume_mode else "incremental",
        }
        self.save_entries(memory_entries, output_path, run_params)
        state.save(output_path, run_params)
        write_run_summary(
            output_path,
            run_params,
            {
                "entries_parsed": len(entries),
                "entries_selected": len(selected),
                "entries_generated": len(memory_entries),
                "time_range_start": memory_entries[0].timestamp.strftime("%Y-%m-%d")
                if memory_entries
                else "—",
                "time_range_end": memory_entries[-1].timestamp.strftime("%Y-%m-%d")
                if memory_entries
                else "—",
                "runtime_s": (datetime.now() - _t0).total_seconds(),
            },
            summary_file=summary_file,
        )

        console.print("\n[bold green]Incremental transformation complete![/bold green]")
        console.print(f"  - [bold]{len(memory_entries)}[/bold] new entries")
        console.print(f"  - Total runs: [bold]{state.processing_stats['total_runs']}[/bold]")
        console.print(
            f"  - Total entries injected: [bold]{state.processing_stats['total_entries_injected']}[/bold]"
        )
