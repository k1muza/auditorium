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
