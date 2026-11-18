#!/usr/bin/env bash
# Commit + push state files safely from a workflow (a bot pushes to main every few minutes, so plain `git pull --rebase; git push` loses races).
# usage: scripts/git_sync.sh "<commit message>" <path>...        exits 0 even when it gave up (a failed push must not kill a loop; it prints ::warning::) unless GIT_SYNC_STRICT=1 (then exit 1)
#  - stages only the given paths, commits only when something changed
#  - up to 8 attempts: pull --rebase with `-X theirs` (during a rebase "theirs" = OUR commit: our fresh state wins a same-line conflict; append-only logs use merge=union, see .gitattributes)
#  - a rebase that still fails is aborted (never leave the checkout in a half-rebased state: the next loop iteration would fail every git command), then retried after a jittered sleep
#  - if every attempt fails the local commit is undone (--soft: files stay in the working tree) so the checkout stays pushable and the next iteration commits them again
msg="$1"; shift
[ $# -gt 0 ] || { echo "usage: git_sync.sh msg paths..."; exit 0; }
git config user.name >/dev/null 2>&1 || git config user.name "highlights-bot"
git config user.email >/dev/null 2>&1 || git config user.email "highlights-bot@users.noreply.github.com"
git rebase --abort >/dev/null 2>&1 || true
git add -- "$@" 2>/dev/null
if git diff --cached --quiet; then exit 0; fi
git commit -q -m "$msg" || { echo "::warning::git_sync: commit failed"; git reset -q 2>/dev/null; exit 0; }
for i in 1 2 3 4 5 6 7 8; do
  if git pull --rebase --autostash -q -X theirs 2>/dev/null && git push -q 2>/dev/null; then exit 0; fi
  git rebase --abort >/dev/null 2>&1 || true
  sleep $(( (RANDOM % 4) + i ))
done
echo "::warning::git_sync: push failed after 8 attempts, un-committing (the files stay in the working tree and are committed again next iteration): $msg"
git reset -q --soft HEAD~1 2>/dev/null && git reset -q -- "$@" 2>/dev/null || true
[ -n "$GIT_SYNC_STRICT" ] && exit 1   # callers that must not continue without a pushed commit (autopilot: dispatching a render of files that are not on main) set GIT_SYNC_STRICT=1
exit 0
