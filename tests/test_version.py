import easyucs_scripts
from conftest import RunEucs


def test_version_option_prints_the_package_version(run_eucs: RunEucs) -> None:
    result = run_eucs("--version")

    assert result.exit_code == 0
    assert result.output.strip() == easyucs_scripts.__version__
