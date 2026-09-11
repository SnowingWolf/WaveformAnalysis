#!/usr/bin/env python3
"""Run one managed Executor/Reviewer attempt; integration requires explicit accept.

Runtime records live under Git's common directory and do not replace task.yaml.
Tests are explicit shell commands: --test 'gate_name=python -m pytest ...'.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import uuid

import yaml


class WorkflowError(RuntimeError):
    pass


def git(repo, *args, raw=False):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise WorkflowError(result.stderr.strip() or f"git failed: {args}")
    return result.stdout if raw else result.stdout.strip()


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def digest(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def read_task(path):
    task = yaml.safe_load(path.read_text())
    if not isinstance(task, dict) or not isinstance(task.get("spec"), dict):
        raise WorkflowError("task.yaml must contain spec")
    spec = task["spec"]
    scope = spec.get("scope", {})
    if not isinstance(spec.get("goal"), str) or not spec["goal"].strip():
        raise WorkflowError("spec.goal is required")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", str(scope.get("base_sha", ""))):
        raise WorkflowError("spec.scope.base_sha must be a full commit SHA")
    paths = scope.get("allowed_paths")
    if not isinstance(paths, list) or not paths:
        raise WorkflowError("spec.scope.allowed_paths must be a nonempty list")
    for path in paths:
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or ".." in PurePosixPath(path).parts
            or path.startswith("-")
            or ".git" in PurePosixPath(path).parts
        ):
            raise WorkflowError(f"invalid allowed path: {path!r}")
    gates = spec.get("required_gates")
    if not isinstance(gates, list) or not gates or not all(isinstance(g, str) and g for g in gates):
        raise WorkflowError("spec.required_gates must be a nonempty list")
    return spec


def commands_for(spec, values):
    commands = {}
    for value in values:
        name, separator, command = value.partition("=")
        if not separator or not name or not command.strip() or name in commands:
            raise WorkflowError("--test must be a unique GATE=COMMAND")
        commands[name] = command
    missing = set(spec["required_gates"]) - commands.keys()
    if missing:
        raise WorkflowError("missing --test for required gates: " + ", ".join(sorted(missing)))
    return commands


def clean(repo):
    return not git(repo, "status", "--porcelain", "--untracked-files=all")


def changed_paths(repo, base):
    committed = git(repo, "diff", "--name-only", "--no-renames", "-z", base, "--", raw=True).split(
        "\0"
    )
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z", raw=True).split("\0")
    return sorted({p for p in committed + untracked if p})


def check_scope(repo, base, allowed):
    paths = changed_paths(repo, base)
    outside = [
        p
        for p in paths
        if not any(p == a.rstrip("/") or p.startswith(a.rstrip("/") + "/") for a in allowed)
    ]
    if outside:
        raise WorkflowError("out-of-scope changes: " + ", ".join(outside))
    return paths


@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / "lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError("another managed workflow operation is running") from exc
        yield


def logged_command(command, log, timeout, *, cwd=None, prompt=None, shell=False):
    """Kill the invocation's process group on timeout/interruption, including shell children."""
    with log.open("w") as stream:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=shell,
            text=True,
            stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            process.communicate(prompt, timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
        return process.returncode


def agent(worktree, prompt, output, log, timeout, schema=None):
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only" if schema else "workspace-write",
        "-C",
        str(worktree),
        "--output-last-message",
        str(output),
    ]
    if schema:
        command += ["--output-schema", str(schema)]
    command += ["-"]
    code = logged_command(command, log, timeout, prompt=prompt)
    if code or not output.is_file():
        raise WorkflowError(f"agent failed (exit {code}); see {log}")
    return output.read_text()


REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["pass", "rework"]},
        "report": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision", "report", "findings"],
}


def run(args, repo, root):
    task_path = Path(args.task)
    if not task_path.is_absolute():
        task_path = repo / task_path
    task_path = task_path.resolve()
    spec = read_task(task_path)
    commands = commands_for(spec, args.test)
    if args.max_reworks < 0 or args.timeout <= 0:
        raise WorkflowError("max-reworks must be >= 0 and timeout must be > 0")
    for existing in root.glob("*/state.json"):
        if json.loads(existing.read_text())["state"] not in {"failed", "rejected", "integrated"}:
            raise WorkflowError(f"an active attempt already exists: {existing.parent.name}")
    target_branch = git(repo, "symbolic-ref", "--short", "HEAD")
    base = git(repo, "rev-parse", spec["scope"]["base_sha"] + "^{commit}")
    if git(repo, "rev-parse", "HEAD") != base:
        raise WorkflowError("task base_sha must equal target HEAD")
    run_id = uuid.uuid4().hex[:12]
    directory = root / run_id
    directory.mkdir()
    worktree = directory / "worktree"
    state = {
        "id": run_id,
        "state": "created",
        "task": str(task_path),
        "spec_sha256": digest(spec),
        "base_sha": base,
        "target_repo": str(repo),
        "target_branch": target_branch,
        "worktree": str(worktree),
        "branch": "codex/managed-" + run_id,
        "tests": commands,
        "attempts": [],
    }

    def save():
        write_json(directory / "state.json", state)

    save()
    print(json.dumps({"id": run_id, "artifacts": str(directory)}), flush=True)
    try:
        git(repo, "worktree", "add", "-b", state["branch"], str(worktree), base)
        schema = directory / "review-schema.json"
        write_json(schema, REVIEW_SCHEMA)
        feedback = ""
        for number in range(args.max_reworks + 1):
            attempt = directory / f"attempt-{number + 1}"
            attempt.mkdir()
            state["state"] = "executing"
            record = {"number": number + 1, "artifacts": str(attempt)}
            state["attempts"].append(record)
            save()
            prompt = (
                "You are the sole Executor for this managed task. Implement the Task Spec below. "
                "Do not spawn agents, commit, switch branches, merge, or modify Git metadata. "
                "The runner owns commits and evidence. Stay within allowed_paths. "
                "Follow repository implementation rules; report results and blockers.\n"
                + yaml.safe_dump({"spec": spec}, allow_unicode=True)
                + "\nPrevious review/test feedback:\n"
                + feedback
            )
            (attempt / "executor-prompt.txt").write_text(prompt)
            agent(worktree, prompt, attempt / "executor.md", attempt / "executor.log", args.timeout)
            if git(worktree, "symbolic-ref", "--short", "HEAD") != state["branch"]:
                raise WorkflowError("Executor changed the managed branch")
            if git(worktree, "merge-base", base, "HEAD") != base:
                raise WorkflowError("Executor rewrote base history")
            paths = check_scope(worktree, base, spec["scope"]["allowed_paths"])
            if paths and not clean(worktree):
                git(worktree, "add", "--all")
                git(worktree, "commit", "-m", f"chore: managed task {run_id} attempt {number + 1}")
            head = git(worktree, "rev-parse", "HEAD")
            record["head_sha"] = head
            (attempt / "diff.patch").write_text(
                git(worktree, "diff", "--binary", base, head, "--", raw=True)
            )
            results = []
            for index, (name, command) in enumerate(commands.items()):
                log = attempt / f"test-{index + 1}.log"
                try:
                    code = logged_command(command, log, args.timeout, cwd=worktree, shell=True)
                except subprocess.TimeoutExpired:
                    code = 124
                results.append(
                    {"gate": name, "command": command, "exit_code": code, "log": str(log)}
                )
            write_json(attempt / "tests.json", results)
            record["tests"] = results
            if not clean(worktree) or git(worktree, "rev-parse", "HEAD") != head:
                raise WorkflowError("test commands changed the reviewed worktree")
            state["state"] = "reviewing"
            save()
            prompt = (
                "You are the sole independent Reviewer. Read Task Spec, inspect the diff and "
                "actual test logs, and assess acceptance criteria. Do not edit, commit, or spawn agents. "
                "Return JSON matching the supplied schema, with pass only when the task is complete "
                "and all required gates pass. Use rework with actionable findings otherwise.\n"
                + yaml.safe_dump({"spec": spec}, allow_unicode=True)
                + f"\nBase: {base}\nHead: {head}\nEvidence directory: {attempt}\n"
                + json.dumps(results)
            )
            (attempt / "reviewer-prompt.txt").write_text(prompt)
            review = json.loads(
                agent(
                    worktree,
                    prompt,
                    attempt / "review.json",
                    attempt / "reviewer.log",
                    args.timeout,
                    schema,
                )
            )
            if (
                not isinstance(review, dict)
                or review.get("decision") not in {"pass", "rework"}
                or not isinstance(review.get("report"), str)
                or not isinstance(review.get("findings"), list)
                or not all(isinstance(f, str) for f in review["findings"])
            ):
                raise WorkflowError("invalid Reviewer response")
            if not clean(worktree) or git(worktree, "rev-parse", "HEAD") != head:
                raise WorkflowError("Reviewer changed the reviewed worktree")
            record["review"] = review
            if review["decision"] == "pass" and all(r["exit_code"] == 0 for r in results):
                state.update(state="awaiting_acceptance", reviewed_head=head)
                save()
                return state
            feedback = json.dumps({"review": review, "tests": results}, ensure_ascii=False)
            state["state"] = "rework_required"
            save()
        raise WorkflowError("rework budget exhausted")
    except (Exception, KeyboardInterrupt) as exc:
        state.update(state="failed", error=str(exc) or type(exc).__name__)
        save()
        raise WorkflowError(f'{state["error"]}; preserved attempt {run_id}') from exc


def control(args, repo, root):
    if not re.fullmatch(r"[a-f0-9]{12}", args.run_id):
        raise WorkflowError("invalid run ID")
    path = root / args.run_id / "state.json"
    if not path.is_file():
        raise WorkflowError("unknown run ID")
    state = json.loads(path.read_text())
    if args.command == "status":
        return state
    if args.command == "reject":
        if state["state"] not in {"awaiting_acceptance", "failed"}:
            raise WorkflowError("only awaiting_acceptance or failed attempts can be rejected")
        state.update(state="rejected")
    else:
        if state["state"] != "awaiting_acceptance":
            raise WorkflowError("accept requires awaiting_acceptance")
        target = Path(state["target_repo"])
        worktree = Path(state["worktree"])
        if target != repo:
            raise WorkflowError("accept must run from the original target worktree")
        if digest(read_task(Path(state["task"]))) != state["spec_sha256"]:
            raise WorkflowError("Task Spec changed after execution")
        head = state["reviewed_head"]
        if not clean(worktree) or git(worktree, "rev-parse", "HEAD") != head:
            raise WorkflowError("reviewed worktree changed")
        if not clean(target):
            raise WorkflowError("target worktree must be clean")
        if git(target, "symbolic-ref", "--short", "HEAD") != state["target_branch"]:
            raise WorkflowError("target branch changed")
        if git(target, "rev-parse", "HEAD") != state["base_sha"]:
            raise WorkflowError("target HEAD changed; rerun against the new base")
        git(target, "merge", "--ff-only", head)
        state.update(state="integrated", integrated_head=git(target, "rev-parse", "HEAD"))
    write_json(path, state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="target repository worktree")
    subs = parser.add_subparsers(dest="command", required=True)
    start = subs.add_parser("run")
    start.add_argument("--task", required=True)
    start.add_argument("--test", action="append", default=[], metavar="GATE=COMMAND")
    start.add_argument("--max-reworks", type=int, default=2)
    start.add_argument(
        "--timeout", type=int, default=1800, help="seconds per agent/test invocation"
    )
    for name in ("status", "accept", "reject"):
        subs.add_parser(name).add_argument("run_id")
    args = parser.parse_args(argv)
    try:
        repo = Path(git(Path(args.repo).resolve(), "rev-parse", "--show-toplevel")).resolve()
        common = Path(git(repo, "rev-parse", "--git-common-dir"))
        root = (repo / common).resolve() / "managed-workflow"
        if args.command == "status":
            state = control(args, repo, root)
        else:
            with locked(root):
                state = (
                    run(args, repo, root) if args.command == "run" else control(args, repo, root)
                )
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0
    except (WorkflowError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
