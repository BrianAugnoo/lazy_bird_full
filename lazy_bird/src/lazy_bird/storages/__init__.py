from pathlib import Path
import shutil
from fastapi import UploadFile

storage_dir = Path(__file__).resolve().parent

def store_file(dir: str, file: UploadFile) -> dict:
    relative_dir = Path(dir)
    if relative_dir.is_absolute() or ".." in relative_dir.parts:
        raise ValueError("Invalid destination directory")

    filename = Path(file.filename or "").name
    if not filename:
        raise ValueError("Invalid file name")

    target_dir = storage_dir / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    full_name = filename
    extension = Path(full_name).suffix.lower()
    file_name = Path(full_name).stem
    size = file.size

    try:
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise RuntimeError(f"Failed to store file {filename}: {e}")

    return {
        "name": file_name,
        "path": str(target_path),
        "extension": extension,
        "size": size
    }
