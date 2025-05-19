from pathlib import Path
import doctr.models as models

cache_dir = Path.home() / ".cache" / "doctr" / "models"
required_models = ["db_resnet50.pt", "parseq.pt"]

# Check for each model
def model_exists(name):
    return any(p.name.startswith(name) for p in cache_dir.glob("*.pt"))

print("Verifying DocTR models...")

if not model_exists("db_resnet50"):
    print("Downloading db_resnet50 (text detection)...")
    models.detection.db_resnet50(pretrained=True)
else:
    print("db_resnet50 model already present.")

if not model_exists("parseq"):
    print("Downloading parseq (text recognition)...")
    models.recognition.parseq(pretrained=True)
else:
    print("parseq model already present.")

print("All required DocTR models are present.")
