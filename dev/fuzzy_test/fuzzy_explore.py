from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from rapidfuzz import fuzz


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi"}
ASSET_EXTENSIONS = {".jpg", ".jpeg", ".nfo"}
ALL_EXTENSIONS = VIDEO_EXTENSIONS | ASSET_EXTENSIONS

SIMILARITY_THRESHOLD = 90


@dataclass
class Cluster:
    seed: Path
    members: List[Path]


@dataclass
class FinalCluster:
    core_guess: str
    members: List[Path]
    video_count: int


def _is_hidden(path: Path) -> bool:
    return path.name.startswith(".")


def _list_candidate_files(folder: Path) -> List[Path]:
    files: List[Path] = []
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        if _is_hidden(entry):
            continue
        ext = entry.suffix.lower()
        if ext in ALL_EXTENSIONS:
            files.append(entry)
    return sorted(files, key=lambda p: p.name)


def _split_files_by_role(files: Sequence[Path]) -> Tuple[List[Path], List[Path]]:
    video_files: List[Path] = []
    asset_files: List[Path] = []
    for f in files:
        ext = f.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            video_files.append(f)
        elif ext in ASSET_EXTENSIONS:
            asset_files.append(f)
    video_files.sort(key=lambda p: p.name)
    asset_files.sort(key=lambda p: p.name)
    return video_files, asset_files


def _cluster_files(
    video_files: Sequence[Path],
    asset_files: Sequence[Path],
) -> Tuple[List[Cluster], List[Path]]:
    clusters: List[Cluster] = []
    assigned_videos: Dict[Path, bool] = {vf: False for vf in video_files}
    assigned_assets: Dict[Path, bool] = {af: False for af in asset_files}

    # Cluster videos using seed-based similarity
    for seed in sorted(video_files, key=lambda p: p.name):
        if assigned_videos.get(seed):
            continue

        cluster_members: List[Path] = [seed]
        assigned_videos[seed] = True

        seed_name = seed.name
        for other in sorted(video_files, key=lambda p: p.name):
            if other is seed:
                continue
            if assigned_videos.get(other):
                continue
            score = fuzz.ratio(seed_name, other.name)
            if score >= SIMILARITY_THRESHOLD:
                cluster_members.append(other)
                assigned_videos[other] = True

        # Attach assets to this cluster based on similarity to seed
        for asset in sorted(asset_files, key=lambda p: p.name):
            if assigned_assets.get(asset):
                continue
            score = fuzz.ratio(seed_name, asset.name)
            if score >= SIMILARITY_THRESHOLD:
                cluster_members.append(asset)
                assigned_assets[asset] = True

        # Decide if this is a real cluster or a singleton
        if len(cluster_members) >= 2:
            clusters.append(Cluster(seed=seed, members=sorted(cluster_members, key=lambda p: p.name)))

    # Any unassigned videos or assets are singletons
    singleton_files: List[Path] = []
    for vf, assigned in assigned_videos.items():
        if not assigned:
            singleton_files.append(vf)
    for af, assigned in assigned_assets.items():
        if not assigned:
            singleton_files.append(af)

    singleton_files.sort(key=lambda p: p.name)
    return clusters, singleton_files


def _longest_common_prefix(strings: Sequence[str]) -> str:
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        # Short-circuit if prefix already empty
        if not prefix:
            break
        # Trim prefix until it matches the start of s
        while not s.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    return prefix


def _split_decoration_tokens(decoration_part: str) -> List[str]:
    if not decoration_part:
        return []
    separators = {"-", "_", " ", "."}
    tokens: List[str] = []
    current: List[str] = []
    for ch in decoration_part:
        if ch in separators:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _compute_core_and_decorations(
    cluster: Cluster,
) -> Tuple[str, Dict[Path, List[str]]]:
    stems: List[str] = [p.stem for p in cluster.members]
    core_guess = _longest_common_prefix(stems)
    if not core_guess and cluster.seed is not None:
        core_guess = cluster.seed.stem

    decorations: Dict[Path, List[str]] = {}
    for path in cluster.members:
        stem = path.stem
        if core_guess and stem.startswith(core_guess):
            decoration_part = stem[len(core_guess) :]
        else:
            decoration_part = stem
        tokens = _split_decoration_tokens(decoration_part)
        decorations[path] = tokens

    return core_guess, decorations


def _build_final_clusters(
    initial_clusters: Sequence[Cluster],
    video_files: Sequence[Path],
    asset_files: Sequence[Path],
) -> Tuple[List[FinalCluster], List[Path], List[str], List[str], List[str]]:
    # All candidate files (videos + assets)
    all_files: List[Path] = sorted(
        list(video_files) + list(asset_files),
        key=lambda p: p.name,
    )

    # Collect core candidates from initial fuzzy clusters
    core_candidates: List[str] = []
    for cluster in initial_clusters:
        core_guess, _ = _compute_core_and_decorations(cluster)
        if core_guess:
            core_candidates.append(core_guess)

    # Deduplicate cores
    core_candidates = sorted(set(core_candidates))

    if not core_candidates:
        # No cores at all: everything is a singleton
        return [], all_files, [], [], []

    # Compute average core length
    avg_len = sum(len(c) for c in core_candidates) / len(core_candidates)

    # "Short" = length < half of average
    short_threshold = 0.5 * avg_len

    normal_cores = [c for c in core_candidates if len(c) >= short_threshold]
    short_cores = [c for c in core_candidates if len(c) < short_threshold]

    # Normal cores: alphabetical
    normal_cores.sort()

    # Short cores: sort from longer to shorter
    short_cores.sort(key=lambda s: (-len(s), s))

    ordered_cores = normal_cores + short_cores

    # Compute shared substrings from the first few normal cores
    def _common_substrings(a: str, b: str) -> List[str]:
        # Very simple: all substrings of a that also appear in b, length >= 2
        subs: set[str] = set()
        la = len(a)
        for i in range(la):
            for j in range(i + 2, la + 1):
                sub = a[i:j]
                if sub in b:
                    subs.add(sub)
        return list(subs)

    shared_substrings: List[str] = []
    if normal_cores:
        # Take up to first 5 normal cores
        sample = normal_cores[:5]
        # Start with all substrings of the first core
        base = sample[0]
        current: set[str] = set()
        lb = len(base)
        for i in range(lb):
            for j in range(i + 2, lb + 1):
                current.add(base[i:j])
        # Intersect with substrings of the others
        for other in sample[1:]:
            other_subs = set(_common_substrings(base, other))
            current &= other_subs
            if not current:
                break
        shared_substrings = sorted(current, key=lambda s: (-len(s), s))

    # Assign files to cores by prefix
    file_assigned: Dict[Path, bool] = {f: False for f in all_files}
    final_clusters: List[FinalCluster] = []

    for core in ordered_cores:
        members: List[Path] = []
        for f in all_files:
            if file_assigned[f]:
                continue
            stem = f.stem
            if stem.startswith(core):
                members.append(f)

        if not members:
            # This core did not capture any files; discard it
            continue

        for f in members:
            file_assigned[f] = True

        video_count = sum(
            1 for f in members if f.suffix.lower() in VIDEO_EXTENSIONS
        )
        final_clusters.append(
            FinalCluster(
                core_guess=core,
                members=sorted(members, key=lambda p: p.name),
                video_count=video_count,
            )
        )

    # Any unassigned files are singletons
    final_singletons: List[Path] = [
        f for f, assigned in file_assigned.items() if not assigned
    ]
    final_singletons.sort(key=lambda p: p.name)

    all_cores = [c.core_guess for c in final_clusters]

    return final_clusters, final_singletons, all_cores, normal_cores, shared_substrings


def _sanitize_folder_name(folder: Path) -> str:
    base = folder.name or "root"
    sanitized_chars: List[str] = []
    for ch in base:
        if ch.isalnum():
            sanitized_chars.append(ch)
        else:
            sanitized_chars.append("_")
    sanitized = "".join(sanitized_chars).strip("_")
    return sanitized or "folder"


def _format_decoration_token(token: str) -> str:
    # Keep raw token; quoting handled in report
    return token


def _write_report(
    folder: Path,
    clusters: Sequence[FinalCluster],
    singletons: Sequence[Path],
    all_cores: Sequence[str],
    normal_cores: Sequence[str],
    shared_substrings: Sequence[str],
    report_path: Path,
) -> None:
    lines: List[str] = []

    considered_files: List[Path] = []
    for c in clusters:
        considered_files.extend(c.members)
    considered_files.extend(singletons)
    considered_files = sorted(set(considered_files), key=lambda p: p.name)

    lines.append(f"FOLDER: {folder}")
    lines.append(f"FILE COUNT (considered): {len(considered_files)}")
    lines.append(
        "EXTENSIONS: " + ", ".join(sorted(ALL_EXTENSIONS))
    )
    lines.append(
        f"SIMILARITY: rapidfuzz.fuzz.ratio, threshold={SIMILARITY_THRESHOLD}"
    )
    lines.append("")

    # MEDIA UNIT CORES
    lines.append("MEDIA UNIT CORES (clusters only):")
    core_summaries: List[Tuple[str, int]] = []
    for cluster in clusters:
        core_summaries.append((cluster.core_guess, len(cluster.members)))

    for core_guess, count in core_summaries:
        lines.append(f'  core="{core_guess}"  files={count}')
    lines.append("")
    lines.append(f"TOTAL MEDIA UNITS (clusters): {len(clusters)}")
    lines.append("")

    # SIGNIFICANT TAGS FROM CORES
    lines.append("CORE-BASED SHARED STRINGS:")
    if not shared_substrings or not normal_cores:
        lines.append("  (none)")
    else:
        total_normals = len(normal_cores)
        # Count how many normal cores contain each shared substring
        tag_infos: List[Tuple[str, int, float]] = []
        for sub in shared_substrings:
            count = sum(1 for c in normal_cores if sub in c)
            ratio = count / total_normals if total_normals else 0.0
            tag_infos.append((sub, count, ratio))

        # Determine "significant tag" (only one, must be in >= 90% of normals)
        significant_tags = [
            (sub, count, ratio)
            for (sub, count, ratio) in tag_infos
            if ratio >= 0.9
        ]

        if len(significant_tags) == 1:
            sub, count, ratio = significant_tags[0]
            lines.append(
                f'  SIGNIFICANT TAG: "{sub}"  present_in={count}/{total_normals} ({ratio:.0%} of non-short cores)'
            )
        else:
            lines.append("  SIGNIFICANT TAG: (none with >=90% coverage)")

        # List all shared substrings with brief remarks
        lines.append("  OTHER SHARED STRINGS (from first few cores):")
        for sub, count, ratio in tag_infos:
            remark = ""
            if ratio >= 0.9:
                remark = " (>=90% of non-short cores)"
            elif ratio >= 0.5:
                remark = " (>=50% of non-short cores)"
            lines.append(
                f'    "{sub}"  in {count}/{total_normals} non-short cores{remark}'
            )
    lines.append("")

    # CLUSTERS WITH MULTIPLE VIDEO FILES
    lines.append("CLUSTERS WITH MULTIPLE VIDEO FILES:")
    multi_video = [
        c for c in clusters
        if c.video_count > 1
    ]
    if not multi_video:
        lines.append("  (none)")
    else:
        for c in multi_video:
            lines.append(
                f'  core="{c.core_guess}"  video_files={c.video_count}  total_files={len(c.members)}'
            )
    lines.append("")

    # FOLDER DECORATIONS SUMMARY
    decoration_counter: Counter[str] = Counter()
    core_strings = {c.core_guess for c in clusters}

    for cluster in clusters:
        core_guess = cluster.core_guess
        decorations: Dict[Path, List[str]] = {}
        # Compute decorations relative to this core_guess
        for path in cluster.members:
            stem = path.stem
            if core_guess and stem.startswith(core_guess):
                decoration_part = stem[len(core_guess):]
            else:
                decoration_part = stem
            tokens = _split_decoration_tokens(decoration_part)
            decorations[path] = tokens

        for tokens in decorations.values():
            for token in tokens:
                token = _format_decoration_token(token)
                # Skip tokens that are part of any core name
                skip = False
                for core in core_strings:
                    if token and token in core:
                        skip = True
                        break
                if skip:
                    continue
                decoration_counter[token] += 1

    lines.append("FOLDER DECORATIONS (all tokens across clusters, excluding core names):")
    if decoration_counter:
        sorted_tokens = sorted(
            decoration_counter.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        for token, count in sorted_tokens:
            lines.append(f'  "{token}" : {count}')
    lines.append("")

    # CLUSTER DETAILS
    for idx, cluster in enumerate(clusters, start=1):
        core_guess = cluster.core_guess
        decorations: Dict[Path, List[str]] = {}
        for path in cluster.members:
            stem = path.stem
            if core_guess and stem.startswith(core_guess):
                decoration_part = stem[len(core_guess):]
            else:
                decoration_part = stem
            tokens = _split_decoration_tokens(decoration_part)
            decorations[path] = tokens

        lines.append(f"CLUSTER #{idx}")
        lines.append(f"  core_guess: {core_guess}")
        lines.append(f"  members ({len(cluster.members)}):")
        for member in cluster.members:
            lines.append(f"    {member.name}")
        lines.append("")
        lines.append("  decorations (relative to core_guess):")
        for member in cluster.members:
            tokens = decorations.get(member, [])
            token_repr = ", ".join(f'"{t}"' for t in tokens)
            lines.append(f"    {member.name}")
            lines.append(f"      tokens: [ {token_repr} ]")
        lines.append("")

    # SINGLETONS
    lines.append("SINGLETONS")
    lines.append(f"  count: {len(singletons)}")
    lines.append("")
    lines.append("  core guesses (stems):")
    for s in singletons:
        lines.append(f"    {s.stem}")
    lines.append("")
    lines.append("  DETAILS:")
    for s in singletons:
        lines.append("    SINGLETON")
        lines.append(f"      filename: {s.name}")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _current_timestamp_str() -> str:
    # Use UTC for deterministic naming
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d-%H%M%S")


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        sys.stderr.write(
            "Usage: python dev/fuzzy_test/fuzzy_explore.py /path/to/folder1 [/path/to/folder2 ...]\n"
        )
        return 1

    folder_args = [Path(arg).expanduser() for arg in argv]
    timestamp = _current_timestamp_str()

    for folder in folder_args:
        folder = folder.resolve()
        if not folder.exists():
            sys.stderr.write(f"[WARN] Path does not exist, skipping: {folder}\n")
            continue
        if not folder.is_dir():
            sys.stderr.write(f"[WARN] Not a directory, skipping: {folder}\n")
            continue

        candidate_files = _list_candidate_files(folder)
        if not candidate_files:
            sys.stderr.write(f"[INFO] No candidate files in folder: {folder}\n")
            continue

        video_files, asset_files = _split_files_by_role(candidate_files)
        initial_clusters, _ = _cluster_files(video_files, asset_files)

        # Build final clusters based on core guesses and prefix matching
        (
            final_clusters,
            final_singletons,
            all_cores,
            normal_cores,
            shared_substrings,
        ) = _build_final_clusters(
            initial_clusters,
            video_files,
            asset_files,
        )

        sanitized_name = _sanitize_folder_name(folder)
        report_filename = f"{timestamp}_{sanitized_name}.txt"
        report_path = Path("dev") / "fuzzy_test" / "logs" / report_filename

        _write_report(
            folder,
            final_clusters,
            final_singletons,
            all_cores,
            normal_cores,
            shared_substrings,
            report_path,
        )
        sys.stderr.write(f"[INFO] Wrote report: {report_path}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
