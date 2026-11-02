import ifcopenshell
from collections import Counter
f = ifcopenshell.open(r"C:\Users\Kelvin\Desktop\auditorium\reviews\iteration-01-work\copy.ifc")
for rel in f.by_type("IfcRelContainedInSpatialStructure"):
    print(rel.RelatingStructure.Name, len(rel.RelatedElements), Counter(e.is_a() for e in rel.RelatedElements).most_common(6))
import ifcopenshell.util.placement as up
z = Counter()
for rel in f.by_type("IfcRelContainedInSpatialStructure"):
    if rel.RelatingStructure.Name == "L03":
        for e in rel.RelatedElements:
            if e.is_a("IfcMember") or e.is_a("IfcElementAssembly"):
                z[round(float(up.get_local_placement(e.ObjectPlacement)[2,3]),1)] += 1
print("L03 member placement z", z.most_common(8))
