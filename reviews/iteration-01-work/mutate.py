import bpy
d = bpy.data.objects
bpy.data.objects.remove(d["SEAT-C-R10-B3-S05"], do_unlink=True)
s = d["SEAT-C-R11-B3-S05"]; s.location.x += 0.3   # overlap neighbour
c = d["STR-COL-B6"]; t = d["SEAT-C-R20-B1-S01"]; t.location.x = c.location.x + 0.2; t.location.y = c.location.y
bpy.ops.wm.save_as_mainfile(filepath=r"C:\Users\Kelvin\Desktop\auditorium\reviews\iteration-01-work\mutated.blend")
