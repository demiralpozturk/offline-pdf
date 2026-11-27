"""Build the Windows release: PyInstaller folder, zip, and a self-test of the packaged exe.

Run: python scripts/build.py
Output: dist/OfflinePDF/ and release/OfflinePDF-<version>-windows-x64.zip
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from offlinepdf import __version__  # noqa: E402


def main() -> int:
    dist = ROOT / "dist" / "OfflinePDF"
    release = ROOT / "release"
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(dist, ignore_errors=True)
    release.mkdir(exist_ok=True)

    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(ROOT / "offlinepdf.spec")], cwd=ROOT, check=True)

    for name in ("LICENSE", "README.md"):
        shutil.copy2(ROOT / name, dist / name)

    # Self-test the packaged GUI exe (headless) and the CLI.
    selftest_dir = release / "selftest"
    shutil.rmtree(selftest_dir, ignore_errors=True)
    code = subprocess.run([str(dist / "OfflinePDF.exe"), "--selftest", str(selftest_dir)], timeout=600).returncode
    report = json.loads((selftest_dir / "report.json").read_text(encoding="utf-8"))
    for check in report["checks"]:
        print("PASS" if check["ok"] else "FAIL", check["name"], "-", check["detail"])
    version = subprocess.run([str(dist / "offlinepdf-cli.exe"), "--version"], capture_output=True, text=True).stdout.strip()
    print("cli:", version)
    if code != 0 or not report["ok"] or __version__ not in version:
        print("Self-test FAILED")
        return 1

    archive = release / f"OfflinePDF-{__version__}-windows-x64.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(dist.rglob("*")):
            if path.is_file():
                zf.write(path, Path("OfflinePDF") / path.relative_to(dist))
    size = sum(p.stat().st_size for p in dist.rglob("*") if p.is_file())
    print(f"folder: {dist} ({size / 1e6:.1f} MB)")
    print(f"zip:    {archive} ({archive.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
