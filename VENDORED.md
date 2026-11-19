# Vendored upstream code

The game itself — the `pyxel` WatchDogsGo frontend — is **vendored**: copied
into this repository so it can be modified for the CardputerZero (320×170
layout, keyboard, pins, packaging) and shipped as a self-contained app. This
file records exactly what was copied, from where, and how to re-sync.

## Provenance

| | |
|---|---|
| Upstream | <https://github.com/LOCOSP/WatchDogsGo> (`main`) at **`8a2cb54`** — "fix(portal): detect uConsole via the clockworkpi-uconsole boot overlay", version **0.10.0** |
| Fork branch replayed on top | owner's fork <https://github.com/codemonkeybr/WatchDogsGo>, branch `feat/aiov2-wifi-bt-fallback`, original tip **`cad1e77`**, based on `7427fbf` |
| What that branch adds | the fallback that lets the game run on the host's own WiFi/BT through an ESP32-emulating bridge (`wdg_wifi_bridge.py`) when no ESP32 is found — 4 commits |
| Result copied here | the tree at **`4bed612`**, the tip of those 4 commits rebased onto `8a2cb54` (no conflicts) |

The four fork commits and their rebased counterparts:

| Original (on `7427fbf`) | Rebased (on `8a2cb54`) | Subject |
|---|---|---|
| `3e8c22e` | `293cb06` | feat: fall back to AIO v2 WiFi/BT bridge when no ESP32 is found |
| `c1f7638` | `31c2913` | fix: don't nag about ESP32 firmware updates when using the AIO v2 bridge |
| `6356101` | `9f4c3f3` | feat: let WiFi and BT wardriving run concurrently, stop independently |
| `cad1e77` | `4bed612` | fix: drop blanket WiFi/BT state clear on the device's stop echo |

`wdg_wifi_bridge.py` itself comes from a community fork (its header credits
"FusedStamen"); it was already in upstream before these four commits.

### Reproducing the rebase

Done in a throwaway clone (2026-11-18); the commits exist on the fork's GitHub
branch, so anyone can redo it:

```bash
git clone https://github.com/LOCOSP/WatchDogsGo.git wdg && cd wdg
git remote add fork https://github.com/codemonkeybr/WatchDogsGo.git
git fetch fork feat/aiov2-wifi-bt-fallback
git checkout -b trial fork/feat/aiov2-wifi-bt-fallback
git rebase origin/main        # at 8a2cb54: replays the 4 commits, no conflicts
```

The only file touched by both sides is `watchdogs/app.py`, in different
regions, and the result compiles. If upstream has moved on, re-check for
conflicts before trusting the same recipe.

## What was copied (and what wasn't)

Copied, byte for byte: `watchdogs/`, `plugins/`, `assets/`, `hs_capture.py`,
`wdg_wifi_bridge.py`, `requirements.txt`, `secrets.conf.example`, `LICENSE`.

Not copied: upstream's `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/`,
`.github/`, and the uConsole installers/launchers (`setup.sh`, `run.sh`,
`watchdogs.desktop`, `watchdogs-launcher`) — we have our own docs, and the
CardputerZero is launched through APPLaunch (`docs/launcher-guidelines.md`).
User data (`loot/`, `maps/`, `secrets.conf`) is never vendored.

## Local modifications

The vendoring commit contains **only** upstream bytes. Every change after it is
an ordinary commit, so our delta against upstream is always:

```bash
git diff <vendoring-commit>..HEAD -- watchdogs plugins assets hs_capture.py wdg_wifi_bridge.py
```

Keep that delta small and localized (display-profile constants, an input/video
shim, uConsole-only features stubbed) so merges from upstream stay cheap.

## Re-syncing with upstream

1. Fetch upstream; list what changed since the recorded base:
   `git diff 8a2cb54..<new-upstream-sha> --stat`.
2. Apply the relevant changes to the vendored paths (a 3-way merge of the
   upstream diff onto our files works well because our edits are localized).
3. Update the table above (new base SHA, date) in the same commit, and re-read
   `docs/portal-rules.md` — upstream's rules for the WDGWars portal change.

## License

The vendored code is MIT-licensed, © 2025-2026 LOCOSP — see `LICENSE`, which
must stay with it. Choosing the license for the code *we* add is on the
pre-publication checklist in `ROADMAP.md`.
