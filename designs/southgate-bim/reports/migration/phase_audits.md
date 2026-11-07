# Phase audits (saved checkpoints)

Build `20261107-073340_full`. Each phase was saved, reopened with IfcOpenShell and audited before the next phase started (`scripts/migrate/build_ifc.py`).

| Phase | Elements | Openings added | Build s | Audit status | Duplicate GUIDs | Checkpoint sha256 |
|---|---:|---:|---:|---|---|---|
| B Spatial structure, spaces and zones | 32 | 0 | 1.8 | {'OK': 32} | 0 | `9cbb1322da274df1` |
| C Structural and architectural framework | 63 | 0 | 16.2 | {'OK': 63} | 0 | `2ce182d5628199a3` |
| D Openings, facades and portals | 817 | 31 | 155.1 | {'OK': 817} | 0 | `c90f581a1d673152` |
| E Roof steel, covering and rainwater | 3999 | 0 | 526.8 | {'OK': 3812, 'REVIEW': 187} | 0 | `14ce797c5ca4bf25` |
| F Auditorium and stage | 2192 | 0 | 94.8 | {'OK': 2192} | 0 | `e99db545e2569e2c` |
| G Ancillary rooms (west office wing, restrooms, terrace) | 863 | 27 | 33.8 | {'OK': 863} | 0 | `1e4b72420b75a209` |
| H Building services and acoustic systems | 2449 | 0 | 83.8 | {'OK': 2449} | 0 | `69609986ba2d3b71` |
| I Foundations and substructure (concept) | 98 | 0 | 32.3 | {'OK': 98} | 0 | `90278c97986534e9` |

Fallbacks to tessellation after a failed native build: 0.

Checks per element: present by GlobalId; IFC class as planned; contained/aggregated/referenced; material; world-AABB vs source; volume vs source; volume calculable. File checks: duplicate GlobalIds, unplanned elements, openings/fills/voids.