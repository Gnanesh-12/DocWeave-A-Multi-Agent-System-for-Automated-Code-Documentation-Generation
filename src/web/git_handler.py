# Copyright (c) Meta Platforms, Inc. and affiliates
"""
Git handler for the docstring generation web interface.

This module handles cloning a repository from a URL into a scratch
workspace directory, and diffing it after docstring generation has run
so the frontend can show exactly what changed.
"""

import re
import uuid
from pathlib import Path
from typing import List, Dict, Any

import git

# Only allow http(s) git URLs (optionally ending in .git) - avoids passing
# arbitrary strings (e.g. local file paths, ssh targets requiring auth) to
# GitPython's clone command.
_VALID_URL_RE = re.compile(r"^https?://[^\s]+$")


def clone_repo(url: str, workspace_dir: Path) -> Path:
    """Shallow-clone a public git repository into a fresh workspace subdirectory.

    Args:
        url: HTTP(S) URL of the repository to clone
        workspace_dir: Base directory under which a new subdirectory is created

    Returns:
        Path to the cloned repository

    Raises:
        ValueError: If the URL doesn't look like a valid http(s) git URL
        git.GitCommandError: If the clone fails (private repo, bad URL, etc.)
    """
    url = url.strip()
    if not _VALID_URL_RE.match(url):
        raise ValueError("Only http(s) git URLs are supported")

    workspace_dir.mkdir(parents=True, exist_ok=True)
    dest = workspace_dir / uuid.uuid4().hex

    git.Repo.clone_from(url, str(dest), depth=1)

    return dest


def get_diff(repo_path: str) -> List[Dict[str, Any]]:
    """Get the per-file diff of uncommitted changes in a cloned repository.

    Since the repository is cloned fresh for each job, any diff against
    HEAD is exactly what the docstring generation process changed.

    Args:
        repo_path: Path to the (previously cloned) repository

    Returns:
        List of {file, diff} dictionaries, one per changed file
    """
    repo = git.Repo(repo_path)
    changed_files = [item.a_path for item in repo.index.diff(None)]

    results = []
    for file_path in changed_files:
        diff_text = repo.git.diff(None, "--", file_path)
        results.append({"file": file_path, "diff": diff_text})

    return results


def get_full_diff(repo_path: str) -> str:
    """Get the combined diff of all uncommitted changes as a single patch.

    The result is a standard multi-file unified diff - it can be saved as a
    .patch file and applied elsewhere with `git apply`.

    Args:
        repo_path: Path to the (previously cloned) repository

    Returns:
        The full diff text (empty string if nothing changed)
    """
    repo = git.Repo(repo_path)
    return repo.git.diff(None)
