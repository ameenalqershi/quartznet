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

def assert_required_packages(folder):
    selected = {}
    for name in ("Quartz.Dashboard", "Quartz.Dashboard.Host"):
        matches = list(folder.glob(name + ".[0-9]*.nupkg"))
        assert len(matches) == 1, f"expected exactly one {name} package; got {matches}"
        inspect(matches[0])
        selected[name] = matches[0]
    return selected


def require_rejected(label, package, expected_message):
    try:
        inspect(package)
    except AssertionError as error:
        assert expected_message in str(error), (label, str(error))
        print(f"PASS negative fixture: {label} rejected")
    else:
        raise AssertionError(f"Malformed nupkg accepted: {label}")


def main():
    selected = assert_required_packages(PACKAGE_DIR)
    original = selected["Quartz.Dashboard"]
    asset_to_drop = sorted(inspect(original))[0]
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        variants = (
            ("missing-asset", asset_to_drop, lambda entry, data: data),
            ("missing-props", PROPS_PATH, lambda entry, data: data),
            ("no-asset-references", None, lambda entry, data: data.replace(b"staticwebassets/", b"unrelatedassets/").replace(b"staticwebassets\\", b"unrelatedassets\\") if entry == PROPS_PATH else data),
        )
        for label, omitted_entry, transform in variants:
            corrupt = tmp / (label + ".nupkg")
            with ZipFile(original) as source, ZipFile(corrupt, "w", ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    if entry.filename != omitted_entry:
                        target.writestr(entry, transform(entry.filename, source.read(entry.filename)))
            expected = asset_to_drop if label == "missing-asset" else "missing props file" if label == "missing-props" else "has only 0 asset references"
            require_rejected(label, corrupt, expected)
        # A missing Dashboard package must be rejected even when Host is intact.
        missing_dashboard = tmp / "missing-dashboard"
        missing_dashboard.mkdir()
        host = selected["Quartz.Dashboard.Host"]
        (missing_dashboard / host.name).write_bytes(host.read_bytes())
        try:
            assert_required_packages(missing_dashboard)
        except AssertionError as error:
            assert "Quartz.Dashboard" in str(error), str(error)
            print("PASS negative fixture: missing Dashboard package rejected")
        else:
            raise AssertionError("Missing Dashboard package accepted")
        # The same check must reject missing Host even if Dashboard is valid.
        missing_host = tmp / "missing-host"
        missing_host.mkdir()
        (missing_host / original.name).write_bytes(original.read_bytes())
        try:
            assert_required_packages(missing_host)
        except AssertionError as error:
            assert "Quartz.Dashboard.Host" in str(error), str(error)
            print("PASS negative fixture: missing Host package rejected")
        else:
            raise AssertionError("Missing Host package accepted")
    print("SUCCESS: 1 positive + 5 negative package integrity fixtures")


if __name__ == "__main__":
    main()
