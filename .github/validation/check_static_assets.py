"""Package integrity regression test for Quartz.NET #4236 (CI test branch only)."""
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

PACKAGE_DIR = Path("artifacts/packages")
ASSET_RE = re.compile(r"\.\.[\\/]staticwebassets[\\/](?P<file>[^'<>]+)'")
PROPS_PATH = "build/Microsoft.AspNetCore.StaticWebAssets.props"

def inspect(pkg):
    with ZipFile(pkg) as archive:
        contained = set(archive.namelist())
        assert PROPS_PATH in contained, f"{pkg} missing props file"
        props_text = archive.read(PROPS_PATH).decode("utf-8")
        expected = {
            "staticwebassets/" + match.group("file").replace("\\", "/")
            for match in ASSET_RE.finditer(props_text)
        }
        assert len(expected) >= 3, f"{pkg} has only {len(expected)} asset references"
        missing = expected - contained
        assert not missing, f"{pkg}: missing {sorted(missing)}"
        print(f"PASS {pkg.name}: {len(expected)} / {len(expected)} referenced assets")
        return expected

def main():
    for name in ("Quartz.Dashboard", "Quartz.Dashboard.Host"):
        pkgs = list(PACKAGE_DIR.glob(name + ".[0-9]*.nupkg"))
        assert len(pkgs) == 1, (name, pkgs)
        inspect(pkgs[0])
    original = next(PACKAGE_DIR.glob("Quartz.Dashboard.[0-9]*.nupkg"))
    asset_to_drop = sorted(inspect(original))[0]
    with TemporaryDirectory() as tmp:
        corrupt = Path(tmp) / original.name
        with ZipFile(original) as src, ZipFile(corrupt, "w", ZIP_DEFLATED) as dst:
            for entry in src.infolist():
                if entry.filename != asset_to_drop:
                    dst.writestr(entry, src.read(entry.filename))
        try:
            inspect(corrupt)
        except AssertionError as error:
            assert asset_to_drop in str(error), str(error)
            print(f"PASS negative fixture: missing {asset_to_drop} detected")
        else:
            raise AssertionError("Malformed nupkg was not rejected")
    print("SUCCESS: package integrity validation")

if __name__ == "__main__":
    main()
