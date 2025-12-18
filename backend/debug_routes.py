import sys
import os
sys.path.insert(0, os.getcwd())

from app.main import app

print("Listing all registered routes:")
for route in app.routes:
    if hasattr(route, "path"):
        print(f"{route.path} [{route.name}]")
    elif hasattr(route, "routes"):
        # Mounts
        for sub_route in route.routes:
             print(f"{route.path}{sub_route.path} [{sub_route.name}]")
