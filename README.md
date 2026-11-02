# 3,000-seat church auditorium - multi-design concept study

CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION. Reviewer scores are QA metrics, not engineering certification.

| Path | Purpose |
|---|---|
| `DESIGN_BRIEF.md`, `QUALITY_RUBRIC.md` | Project-wide brief and BIM rubric (common to all designs; original text kept) |
| `designs/A-end-stage/` | Option A - end stage. **Frozen baseline PL08-590d273e35.** Self-contained: config, scripts, tests, model, reports, exports, renders, logs, archive, reviews, proposal |
| `designs/B-long-side-stage/` | Option B - stage on the long side (competing design) |
| `shared/` | Reusable code for new designs (geometry primitives, Blender builder, IFC export, environment discovery) |
| `documentation/` | Shared publication design system (`proposal/template/`), migration records, project-wide briefs |
| `comparisons/` | A-vs-B study, measured from each design's own outputs |
| `agents/` | Specialist reviewer briefs and the multidisciplinary review rubric |
| `tools/` | Repository tools: baseline verification, revision reproduction, per-design builds |

Build / verify / document (from the repository root, Windows venv):
```
.venv/Scripts/python tools/build.py --design B --iteration 3          # Option B full pipeline -> designs/B-long-side-stage/
.venv/Scripts/python tools/build.py --design A                        # Option A: non-destructive reproduction of PL08
.venv/Scripts/python tools/build.py --design A --revision pl-02       # ... or of the recovered PL02
.venv/Scripts/python comparisons/compare.py                           # A-vs-B measurements + figures -> comparisons/out/
.venv/Scripts/python comparisons/score_reviews.py                     # rubric-weighted review scores
.venv/Scripts/python documentation/proposal/build_proposal.py --design A|B   # engineering design proposal (HTML + PDF)
.venv/Scripts/python documentation/proposal/build_proposal.py --compare      # comparative feasibility report
```
Current state: Option A PL08-590d273e35 (frozen), Option B B03-44bc3ae457. Recommendation: `comparisons/RECOMMENDATION.md`.
Migration record: `documentation/migration/MIGRATION_AND_CHANGE_REPORT.md`.

Verification (read-only on every design):
```
.venv/Scripts/python tools/verify_baseline.py                                # 729 pre-restructure files, byte-exact
.venv/Scripts/python tools/reproduce_revision.py --design A --revision pl-08  # rebuild A in a temp folder, compare manifest
```
Each design writes only inside its own folder. Blender is found via `BLENDER_EXE`, PATH, or the standard install folder.

---

## Original starter README (kept for reference)

# Auditorium BIM — Builder / Independent Reviewer workflow

This is a **starter project for running an AI-assisted architectural/BIM concept loop**, not an auditorium design, an engineering calculation, or an approved construction plan. It does not include Blender itself, Codex, Claude or model files; the AI builder generates those when you run it with compatible installed tooling.

## Quick start
1. Create/open a dedicated local project directory. Extract/copy all files from this package into it, preserving hidden `.codex/` and `.claude/` folders.
2. Install Blender, the appropriate Blender MCP bridge and Codex CLI or Claude Code. Optionally install Bonsai/IfcOpenShell if compatible with your Blender version. Configure your MCP connection in your parent agent; this package does not install or configure MCP.
3. Open a **new Codex CLI or Claude Code session** in the project directory (agents may need a restarted session to be discovered).
4. Paste the text of `RUN_PROMPT.md` into Codex/Claude. Confirm you approve the intended local file and Blender changes when requested.
5. Follow each build/review cycle; final output should be in `model/`, `reports/`, `exports/`, `reviews/`, and `scripts/`.

## How custom subagent loading works
- **Codex:** `.codex/agents/bim-reviewer.toml` custom subagent. Prompt the lead agent to delegate to `bim-reviewer`. See https://learn.chatgpt.com/docs/agent-configuration/subagents
- **Claude Code:** `.claude/agents/bim-reviewer.md` custom subagent. Prompt the lead agent to delegate to `bim-reviewer`. See https://academy.claude.com/courses/introduction-to-subagents/creating-a-subagent

If agent discovery fails, inspect the installed version's documentation; agent config is evolving.

## The loop
Build -> Independent review -> `python scripts/evaluate_review.py reviews/iteration-01.json` -> stop if score >9.0 and no blockers -> otherwise repair and repeat up to 3 iterations.

The validator computes an independently repeatable weighted score and verifies that cited evidence **files exist**. It does not prove the evidence is truthful, that an IFC is semantically correct, that seat counts are right, or that the proposed building is safe. The reviewer must inspect those substantively.

## Key boundary
The target is a conceptual, **engineering-coordination** BIM model. A suitably qualified architect and structural engineer and relevant local authorities must establish and verify applicable standards, life-safety compliance, member design, foundations and construction documentation before work starts on site.
