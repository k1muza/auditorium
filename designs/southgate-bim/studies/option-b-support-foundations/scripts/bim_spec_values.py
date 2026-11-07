"""Writes bim_spec/J_values.md: the quantities quoted in the BIM implementation specification, from calcs/selection.json (S3)."""
import json, os
ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
s = json.load(open(ROOT + "/calcs/selection.json"))["S3"]
st, fq, wq, hd = s["steel_t"], s["found_q"], s["wall_q"], s["hd"]
pads = [b for b in s["bases"]]
L = ["# J — computed values for the BIM implementation specification (S3, G2/F2)", "",
     f"- Column section: {s['column']}",
     f"- Steel nominal masses (t): columns {st['columns']:.1f}; posts {st['posts']:.1f}; bracing, girders, ties and post struts {st['bracing_girders']:.1f}; plates {st['plates']:.1f}; total {st['total']:.1f}",
     f"- Holding-down bolts: {hd['n']} (by diameter: {hd.get('by_dia')}); base-plate shear keys {hd['shear_keys']}; pad downstand keys {hd.get('pad_keys', 0)}",
     f"- Footing concrete (pads + encasement) {fq['concrete_m3']:.1f} m3; wall strip {wq['concrete_m3']:.1f} m3 over {wq.get('length_m', 0):.1f} m",
     f"- Reinforcement: pads {fq['rebar_kg']/1000:.2f} t; wall strip {wq['rebar_kg']/1000:.2f} t; anchor reinforcement {hd['anchor_reinf_kg']/1000:.2f} t",
     "", "| Base | Pad B x L x D (m) | Base plate | Holding-down |", "|---|---|---|---|"]
for b in pads:
    nm = f"{b['kind']} {b['line']}" + ({0: 'A', 1: 'B'}.get(b['side'], '') if b['kind'] == 'column' else f" k{b['k']}")
    L.append(f"| {nm} | {b['pad']['B']:.1f} x {b['pad']['L']:.2f} x {b['pad']['D']:.2f} | {b['base']['plate_mm']} | {b['base']['bolts']} |")
open(ROOT + "/bim_spec/J_values.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("J values written")
