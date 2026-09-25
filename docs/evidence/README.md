# Evidence index

Screenshots and captured output proving the process requirements actually happened, not just that
the config exists. Each item below needs a real action first — nothing here should be staged or
implied without the underlying action having actually occurred.

| File | What it proves | How to produce it |
|---|---|---|
| `branch-protection.png` | `main` requires a PR, ≥1 approval, and blocks direct pushes | GitHub → repo → Settings → Branches → screenshot the rule for `main` |
| `merge-conflict-markers.png` | The deliberate conflict actually conflicted | Terminal or editor screenshot showing the raw `<<<<<<<`/`=======`/`>>>>>>>` markers before resolution (see `merge-conflict-demo.sh`) |
| `merge-conflict-resolved.png` | It was actually resolved and merged | GitHub PR page after merge, or `git log --graph --oneline` showing the merge commit with two parents |
| `pr-blocked-red.png` | A failing check actually blocks merge | Screenshot of a PR with a red/failing required check and a disabled merge button |
| `pr-green-merged.png` | The same PR after the fix, passing | Screenshot of the same PR green and merged |
| `hpa-watch.png` (or `.log`) | HPA actually scaled under load | `kubectl get hpa -w -n civicpulse` output captured while running `load/k6-script.js` (see `scripts/record-hpa.sh`) |
| `replicas-vs-load-chart.png` | The relationship between offered load and replica count | Built from the same load-test run; referenced by `docs/ENGINEERING-NOTES.md` Q5 |
| `vpa-recommendation.png` | VPA produced real Target/Lower/Upper bound numbers | `kubectl describe vpa backend-vpa -n civicpulse` output |

Nothing in this directory should be added until the corresponding real action has been taken.
