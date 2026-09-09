"""Reject branch builds, private repositories and mismatched release tags."""
import os
import re
import subprocess
import tomllib
from pathlib import Path

tag = os.environ.get("RELEASE_TAG", "")
if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
    raise SystemExit("An exact vX.Y.Z release tag is required")
if os.environ.get("REPOSITORY_VISIBILITY") != "public":
    raise SystemExit("Public repository audit and visibility change must precede publishing")
metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
if metadata["project"]["version"] != tag[1:]:
    raise SystemExit("Tag and package versions differ")
if metadata["tool"]["comfy"]["PublisherId"] != "bryan711":
    raise SystemExit("Unexpected Registry publisher")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
tag_head = subprocess.check_output(["git", "rev-parse", "refs/tags/" + tag + "^{commit}"], text=True).strip()
if head != tag_head:
    raise SystemExit("Checkout does not match the release tag")
subprocess.run(["git", "merge-base", "--is-ancestor", head, "origin/main"], check=True)
print(f"Verified fixed release {tag} at {head}")
