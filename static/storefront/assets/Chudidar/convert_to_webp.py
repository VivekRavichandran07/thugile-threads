from PIL import Image
from pathlib import Path

# Folder containing your images
INPUT_FOLDER = Path(".")

# WebP quality: 80-85 is good for websites
QUALITY = 82

extensions = {".png", ".jpg", ".jpeg"}

for file in INPUT_FOLDER.iterdir():
    if file.is_file() and file.suffix.lower() in extensions:
        output = file.with_suffix(".webp")

        try:
            with Image.open(file) as img:
                # Preserve transparency for PNG
                if img.mode in ("RGBA", "LA"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

                img.save(
                    output,
                    "WEBP",
                    quality=QUALITY,
                    method=6,
                )

            old_size = file.stat().st_size / 1024
            new_size = output.stat().st_size / 1024

            print(
                f"✓ {file.name} -> {output.name} "
                f"({old_size:.1f} KB -> {new_size:.1f} KB)"
            )

        except Exception as e:
            print(f"✗ Failed: {file.name}: {e}")

print("\nConversion complete.")
