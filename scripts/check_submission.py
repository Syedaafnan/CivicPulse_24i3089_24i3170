#!/usr/bin/env python3
"""Pre-submission lint for CivicPulse (assignment Section 5.8).

Not a grader - a mechanical check for the automatic-deduction items in Section 5.3
and the required-file layout in Section 5.7. A clean run does not guarantee a good
mark; a dirty run nearly guarantees a bad one.

Usage: python scripts/check_submission.py
Exit code: 0 if no FAILs (WARNs are still printed), 1 otherwise.
"""

from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []  # (level, check, detail)


def record(level: str, check: str, detail: str = "") -> None:
    results.append((level, check, detail))


def run_git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30
        )
        return out.stdout
    except Exception as exc:  # pragma: no cover - defensive only
        return f"__git_error__:{exc}"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------------------
# Section 5.3 automatic deductions
# ---------------------------------------------------------------------------

SECRET_FILENAME_RE = re.compile(r"(^|/)(\.env(\..+)?|.*\.pem|.*\.key|id_rsa.*)$")
SECRET_FILENAME_ALLOW = {".env.example"}


def check_secrets_in_history() -> None:
    out = run_git("log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:")
    if out.startswith("__git_error__"):
        record(WARN, "secrets-in-history", "could not run git log (not a git repo yet?)")
        return
    hits = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line in SECRET_FILENAME_ALLOW:
            continue
        if SECRET_FILENAME_RE.match(line):
            hits.append(line)
    if hits:
        record(FAIL, "secrets-in-history", f"filenames matching secret patterns were ever committed: {hits}")
    else:
        record(PASS, "secrets-in-history", "no .env/.pem/.key/id_rsa filenames found in any commit")


PLACEHOLDER_VALUES = {"", "changeme", "change_me", "replace_me", "replaceme", "please-set-me"}


def _looks_like_placeholder(value: str) -> bool:
    v = value.strip().strip('"').strip("'")
    if v.lower() in PLACEHOLDER_VALUES:
        return True
    try:
        decoded = base64.b64decode(v + "=" * (-len(v) % 4)).decode("utf-8", "ignore")
        if decoded.lower() in PLACEHOLDER_VALUES:
            return True
    except Exception:
        pass
    return False


def check_k8s_secret_placeholders() -> None:
    secret_file = ROOT / "k8s" / "base" / "secret.yaml"
    text = read(secret_file)
    if not text:
        record(WARN, "k8s-secret-placeholders", f"{secret_file} not found")
        return
    suspicious = []
    for m in re.finditer(r"^\s*([A-Z0-9_]+):\s*(.+)$", text, re.MULTILINE):
        key, value = m.group(1), m.group(2)
        if not _looks_like_placeholder(value):
            suspicious.append((key, value))
    if suspicious:
        record(FAIL, "k8s-secret-placeholders", f"non-placeholder-looking values in k8s/base/secret.yaml: {suspicious}")
    else:
        record(PASS, "k8s-secret-placeholders", "k8s/base/secret.yaml contains placeholders only")


def check_unpinned_images() -> None:
    offenders = []
    for compose_file in ("compose.yaml", "compose.prod.yaml"):
        text = read(ROOT / compose_file)
        anchors = dict(re.findall(r"&([\w-]+)\s+(\S+)", text))
        for m in re.finditer(r"^\s*image:\s*([^\s#]+)", text, re.MULTILINE):
            image = m.group(1)
            if image.startswith("*"):
                image = anchors.get(image[1:], image)  # resolve YAML alias
            if "${" in image:
                continue  # parameterised, checked separately
            if ":" not in image.split("/")[-1]:
                offenders.append(f"{compose_file}: {image}")
    for dockerfile in (ROOT / "backend" / "Dockerfile", ROOT / "frontend" / "Dockerfile"):
        for m in re.finditer(r"^FROM\s+(\S+)", read(dockerfile), re.MULTILINE):
            image = m.group(1)
            if ":" not in image:
                offenders.append(f"{dockerfile.relative_to(ROOT)}: {image}")
    if offenders:
        record(FAIL, "unpinned-images", f"images with no explicit tag: {offenders}")
    else:
        record(PASS, "unpinned-images", "all base images carry an explicit tag")


def check_localhost_service_to_service() -> None:
    offenders = []
    for path in (ROOT / "compose.yaml", ROOT / "compose.prod.yaml"):
        for i, line in enumerate(read(path).splitlines(), 1):
            if "localhost" in line.lower() and not line.strip().startswith("#"):
                offenders.append(f"{path.name}:{i}")
    for path in (ROOT / "k8s" / "base").glob("*.yaml"):
        for i, line in enumerate(read(path).splitlines(), 1):
            if "localhost" in line.lower() and not line.strip().startswith("#"):
                offenders.append(f"{path.relative_to(ROOT)}:{i}")
    if offenders:
        record(FAIL, "localhost-service-to-service", f"'localhost' found in compose/k8s config: {offenders}")
    else:
        record(PASS, "localhost-service-to-service", "no 'localhost' references in compose/k8s service config")


def check_network_segmentation() -> None:
    text = read(ROOT / "compose.yaml")
    if not text:
        record(WARN, "network-segmentation", "compose.yaml not found")
        return
    services = re.split(r"\n(?=  \w[\w-]*:\n)", text)
    frontend_networks, db_networks, cache_networks = None, None, None
    for block in services:
        head = block.strip().splitlines()[0] if block.strip() else ""
        name = head.rstrip(":").strip()
        nets_match = re.search(r"networks:\s*\[([^\]]*)\]", block)
        nets = [n.strip() for n in nets_match.group(1).split(",")] if nets_match else None
        if name == "frontend":
            frontend_networks = nets
        if name == "postgres":
            db_networks = nets
        if name == "redis":
            cache_networks = nets
    problems = []
    if frontend_networks and "internal" in frontend_networks:
        problems.append("frontend is on the internal network")
    if db_networks and "edge" in db_networks:
        problems.append("postgres is on the edge network")
    if cache_networks and "edge" in cache_networks:
        problems.append("redis is on the edge network")
    if problems:
        record(FAIL, "network-segmentation", "; ".join(problems))
    else:
        record(PASS, "network-segmentation", "frontend/db/cache network membership looks correctly segmented")


def check_prod_ports_and_build_key() -> None:
    text = read(ROOT / "compose.prod.yaml")
    if not text:
        record(WARN, "compose-prod-hygiene", "compose.prod.yaml not found")
        return
    problems = []
    if re.search(r"^\s*build:\s*$|^\s*build:\s*\S", text, re.MULTILINE):
        problems.append("a `build:` key exists in compose.prod.yaml")
    blocks = re.split(r"\n(?=  \w[\w-]*:\n)", text)
    for block in blocks:
        head = block.strip().splitlines()[0] if block.strip() else ""
        name = head.rstrip(":").strip()
        if name in ("postgres", "redis") and re.search(r"^\s*ports:", block, re.MULTILINE):
            problems.append(f"{name} publishes a port in compose.prod.yaml")
    if problems:
        record(FAIL, "compose-prod-hygiene", "; ".join(problems))
    else:
        record(PASS, "compose-prod-hygiene", "no build: key, no published db/cache ports in compose.prod.yaml")


def check_k8s_service_types() -> None:
    offenders = []
    for path in (ROOT / "k8s" / "base").glob("*.yaml"):
        text = read(path)
        if re.search(r"type:\s*(NodePort|LoadBalancer)", text):
            offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        record(FAIL, "k8s-service-types", f"NodePort/LoadBalancer found in: {offenders}")
    else:
        record(PASS, "k8s-service-types", "no NodePort/LoadBalancer Services found")


def check_postgres_statefulset() -> None:
    text = read(ROOT / "k8s" / "base" / "postgres.yaml")
    if not text:
        record(WARN, "postgres-statefulset", "k8s/base/postgres.yaml not found")
        return
    if "kind: Deployment" in text and "kind: StatefulSet" not in text:
        record(FAIL, "postgres-statefulset", "postgres.yaml uses Deployment, not StatefulSet")
    elif "kind: StatefulSet" in text and "volumeClaimTemplates" in text:
        record(PASS, "postgres-statefulset", "postgres is a StatefulSet with volumeClaimTemplates")
    else:
        record(WARN, "postgres-statefulset", "could not confirm StatefulSet + volumeClaimTemplates")


def check_no_latest_deploy() -> None:
    cd = read(ROOT / ".github" / "workflows" / "cd.yml")
    offenders = []
    for i, line in enumerate(cd.splitlines(), 1):
        if re.search(r"kubectl\s+(set image|apply)", line) and ":latest" in line:
            offenders.append(f"cd.yml:{i}")
    for path in (ROOT / "k8s" / "overlays").rglob("*.yaml"):
        for i, line in enumerate(read(path).splitlines(), 1):
            code = line.split("#", 1)[0]
            if ":latest" in code:
                offenders.append(f"{path.relative_to(ROOT)}:{i}")
    if offenders:
        record(FAIL, "no-latest-deploy", f":latest referenced in a deploy path: {offenders}")
    else:
        record(PASS, "no-latest-deploy", "no :latest reference in any deploy path")


def check_needs_gating() -> None:
    cd = read(ROOT / ".github" / "workflows" / "cd.yml")
    job_blocks = re.split(r"\n(?=  [\w-]+:\n)", cd)
    problems = []
    for block in job_blocks:
        head_line = block.strip().splitlines()[0] if block.strip() else ""
        job_name = head_line.rstrip(":").strip()
        if job_name in ("build-push", "deploy-k8s", "deploy", "publish"):
            if "needs:" not in block:
                problems.append(job_name)
    if problems:
        record(FAIL, "needs-gating", f"jobs missing needs: {problems}")
    else:
        record(PASS, "needs-gating", "publishing/deploying jobs in cd.yml are needs:-gated")


def check_direct_pushes_to_main() -> None:
    out = run_git("log", "main", "--pretty=format:%H %P")
    if out.startswith("__git_error__") or not out.strip():
        record(WARN, "direct-pushes-to-main", "no local `main` branch to inspect yet")
        return
    lines = out.strip().splitlines()
    non_merge_non_root = 0
    for line in lines[:-1]:  # exclude the root commit (last line)
        parts = line.split()
        parents = parts[1:]
        if len(parents) <= 1:
            non_merge_non_root += 1
    if non_merge_non_root:
        record(
            WARN,
            "direct-pushes-to-main",
            f"{non_merge_non_root} non-root commit(s) on main have a single parent "
            "(could be a direct push, or a squash-merge PR - verify on GitHub)",
        )
    else:
        record(PASS, "direct-pushes-to-main", "every non-root commit on main is a merge commit")


def check_readme_quickstart() -> None:
    readme = read(ROOT / "README.md")
    if "docker compose up" not in readme:
        record(FAIL, "readme-quickstart", "README.md does not mention `docker compose up`")
    elif not (ROOT / "compose.yaml").exists():
        record(FAIL, "readme-quickstart", "README references compose but compose.yaml is missing")
    else:
        record(PASS, "readme-quickstart", "README references docker compose and compose.yaml exists")


# ---------------------------------------------------------------------------
# Section 5.7 required file layout
# ---------------------------------------------------------------------------

REQUIRED_FILES = [
    "backend/Dockerfile",
    "backend/.dockerignore",
    "backend/pyproject.toml",
    "frontend/Dockerfile",
    "frontend/.dockerignore",
    "frontend/package.json",
    "frontend/nginx.conf",
    "k8s/base/kustomization.yaml",
    "k8s/overlays/dev/kustomization.yaml",
    "k8s/overlays/prod/kustomization.yaml",
    "load/k6-script.js",
    "docs/ENGINEERING-NOTES.md",
    "docs/RUNBOOK.md",
    "docs/AI-USAGE.md",
    "docs/TRIAGE.md",
    "docs/adr/0001-provider-interface.md",
    "docs/adr/0002-frontend-runtime-config.md",
    "docs/adr/0003-deploy-by-sha.md",
    "docs/adr/0004-pii-and-data-governance.md",
    ".github/workflows/ci.yml",
    ".github/workflows/cd.yml",
    ".github/workflows/release.yml",
    "compose.yaml",
    "compose.prod.yaml",
    ".env.example",
    ".gitignore",
    "README.md",
    "LICENSE",
]


def check_required_files() -> None:
    missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
    if missing:
        record(FAIL, "required-files", f"missing: {missing}")
    else:
        record(PASS, "required-files", f"all {len(REQUIRED_FILES)} required files present")


def check_evidence_dir() -> None:
    ev = ROOT / "docs" / "evidence"
    if not ev.exists():
        record(FAIL, "evidence-dir", "docs/evidence/ does not exist")
        return
    contents = list(ev.glob("*"))
    if not contents:
        record(WARN, "evidence-dir", "docs/evidence/ exists but is empty - add the required screenshots")
    else:
        record(PASS, "evidence-dir", f"docs/evidence/ has {len(contents)} file(s)")


def check_ai_usage_filled() -> None:
    text = read(ROOT / "docs" / "AI-USAGE.md")
    unresolved_brackets = len(re.findall(r"\[(Partner|add|Fill|describe|List real)", text, re.IGNORECASE))
    if unresolved_brackets:
        record(WARN, "ai-usage-filled", f"{unresolved_brackets} bracketed placeholder(s) still in docs/AI-USAGE.md")
    else:
        record(PASS, "ai-usage-filled", "docs/AI-USAGE.md has no obvious unresolved placeholders")


CHECKS = [
    check_secrets_in_history,
    check_k8s_secret_placeholders,
    check_unpinned_images,
    check_localhost_service_to_service,
    check_network_segmentation,
    check_prod_ports_and_build_key,
    check_k8s_service_types,
    check_postgres_statefulset,
    check_no_latest_deploy,
    check_needs_gating,
    check_direct_pushes_to_main,
    check_readme_quickstart,
    check_required_files,
    check_evidence_dir,
    check_ai_usage_filled,
]


def main() -> int:
    for check in CHECKS:
        check()

    width = max(len(c) for _, c, _ in results)
    for level, check, detail in results:
        marker = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[level]
        print(f"[{marker}] {level:<4} {check:<{width}}  {detail}")

    n_fail = sum(1 for level, *_ in results if level == FAIL)
    n_warn = sum(1 for level, *_ in results if level == WARN)
    print(f"\n{len(results)} checks: {len(results) - n_fail - n_warn} pass, {n_warn} warn, {n_fail} fail.")
    print("This is a lint, not a grader. A clean run does not guarantee a good mark;")
    print("a dirty run nearly guarantees a bad one.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
