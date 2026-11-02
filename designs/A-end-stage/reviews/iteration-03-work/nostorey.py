import bpy
from collections import Counter
print("NOSTOREY", Counter((o.users_collection[0].name if o.users_collection else '-') for o in bpy.context.scene.objects if o.type=='MESH' and not o.get("storey")))
