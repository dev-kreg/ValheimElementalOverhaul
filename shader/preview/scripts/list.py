import sys, UnityPy
env = UnityPy.load(sys.argv[1])
for o in env.objects:
    if o.type.name in ("GameObject","Texture2D","Material","ParticleSystem","Light","MonoBehaviour"):
        try:
            n = o.peek_name() if hasattr(o,"peek_name") else o.read().m_Name
        except Exception as e: n = "?"
        if o.type.name in ("GameObject","Texture2D","Material"): print(o.type.name, n)
from collections import Counter
print(Counter(o.type.name for o in env.objects))
