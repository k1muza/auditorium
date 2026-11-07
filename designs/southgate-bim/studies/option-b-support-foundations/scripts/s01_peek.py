import ifcopenshell, ifcopenshell.util.element as ue, sys, json, collections
f = ifcopenshell.open(sys.argv[1])
for cls in ["IfcColumn","IfcFooting"]:
    e = f.by_type(cls)[0]
    print(cls, e.Name, e.ObjectType); print(json.dumps(ue.get_psets(e), indent=1, default=str)[:2500])
c = collections.Counter()
for cls in ["IfcBeam","IfcMember","IfcPlate","IfcMechanicalFastener","IfcColumn","IfcFooting","IfcSlab","IfcWall","IfcElementAssembly"]:
    for e in f.by_type(cls):
        n=(e.Name or "").split("-")
        c[(cls,"-".join(n[:2]))]+=1
for k,v in sorted(c.items()): print(k,v)
