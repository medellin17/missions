import sys
import os

# Добавим путь к проекту
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    print("DEBUG: Attempting to import models...")
    import models
    print(f"DEBUG: Successfully imported models module.")
    print(f"DEBUG: Base type: {type(models.Base)}")
    print(f"DEBUG: Base metadata tables count: {len(models.Base.metadata.tables)}")
    print(f"DEBUG: Base metadata tables: {list(models.Base.metadata.tables.keys())}")
    print("DEBUG: --- End of successful import info ---")
except ImportError as e:
    print(f"DEBUG: ImportError during import: {e}")
    import traceback
    print("DEBUG: Traceback for ImportError:")
    traceback.print_exc()
except Exception as e:
    print(f"DEBUG: General exception during import: {e}")
    import traceback
    print("DEBUG: Traceback for general exception:")
    traceback.print_exc()

print("DEBUG: Script execution finished.")
