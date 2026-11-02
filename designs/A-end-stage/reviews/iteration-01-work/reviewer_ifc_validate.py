import ifcopenshell, ifcopenshell.validate, logging, json
from collections import Counter
f = ifcopenshell.open(r"C:\Users\Kelvin\Desktop\auditorium\reviews\iteration-01-work\copy.ifc")
lg = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate(f, lg, express_rules=False)
print("SCHEMA_ISSUES", len(lg.statements))
print(Counter(str(s.get("message"))[:80] for s in lg.statements).most_common(10))
d = f.by_type("IfcDoor")
print("door attr widths", Counter((x.OverallWidth, x.OverallHeight) for x in d).most_common(5))
print("shear walls", [(w.Name) for w in f.by_type("IfcWall") if w.PredefinedType=="SHEAR"])
for s in f.by_type("IfcSpace"):
    p = s.Decomposes[0].RelatingObject.Name if s.Decomposes else None
    print("space", s.Name, p) if s.Name in ("SPC-SP-01","SPC-SP-07") else None
import ifcopenshell.util.element as ue
print("stairs", [(s.Name, s.PredefinedType) for s in f.by_type("IfcStair")])
print("ramps", [(s.Name) for s in f.by_type("IfcRamp")])
print("zones sample", [(z.Name, z.LongName) for z in f.by_type("IfcSpatialZone")[:3]])
