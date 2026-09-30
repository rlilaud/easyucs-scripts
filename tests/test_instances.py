from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence

import pytest

from easyucs_scripts.instances import Instance, InstanceDefinitionError, resolve_instances


def write(tmp_path: Path, text: str, filename: str = "instances.yaml") -> Path:
    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return path


def load(tmp_path: Path, text: str, filename: str = "instances.yaml") -> list[Instance]:
    return resolve_instances(write(tmp_path, text, filename), [])


def load_error(tmp_path: Path, text: str, filename: str = "instances.yaml") -> str:
    with pytest.raises(InstanceDefinitionError) as caught:
        load(tmp_path, text, filename)
    return str(caught.value)


def resolve_error(instances_file: Optional[Path], urls: Sequence[str]) -> str:
    with pytest.raises(InstanceDefinitionError) as caught:
        resolve_instances(instances_file, urls)
    return str(caught.value)


def test_a_yaml_file_lists_instances_with_their_options(tmp_path: Path) -> None:
    ca_bundle = tmp_path / "pki" / "company-ca.pem"
    instances = load(
        tmp_path,
        f"""
instances:
  - url: https://easyucs.paris.example.com
    name: paris
    verify_tls: true
    ca_bundle: {ca_bundle.as_posix()}
  - url: http://10.0.0.5:5010
    verify_tls: false
""",
    )

    assert instances == [
        Instance(url="https://easyucs.paris.example.com", name="paris", verify_tls=True, ca_bundle=ca_bundle),
        Instance(url="http://10.0.0.5:5010", name="10.0.0.5_5010", verify_tls=False, ca_bundle=None),
    ]


def test_a_json_file_is_accepted_even_when_indented_with_tabs(tmp_path: Path) -> None:
    instances = load(
        tmp_path,
        '{\n\t"instances": [\n\t\t{"url": "http://10.0.0.5:5010", "name": "lab"}\n\t]\n}\n',
        "instances.json",
    )

    assert instances == [Instance(url="http://10.0.0.5:5010", name="lab")]


def test_tls_is_verified_without_a_ca_bundle_by_default(tmp_path: Path) -> None:
    (instance,) = load(tmp_path, "instances:\n  - url: https://easyucs.example.com\n")

    assert (instance.verify_tls, instance.ca_bundle) == (True, None)


def test_a_relative_ca_bundle_is_relative_to_the_instances_file(tmp_path: Path) -> None:
    (instance,) = load(tmp_path, "instances:\n  - url: https://easyucs.example.com\n    ca_bundle: pki/ca.pem\n")

    assert instance.ca_bundle == tmp_path / "pki" / "ca.pem"


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("http://10.0.0.5:5010", "10.0.0.5_5010"),
        ("https://easyucs.example.com/", "easyucs.example.com"),
        ("http://[fe80::1]:5010", "fe80::1_5010"),
    ],
)
def test_the_name_is_derived_from_host_and_port_when_absent(url: str, name: str) -> None:
    (instance,) = resolve_instances(None, [url])

    assert instance.name == name


def test_urls_become_instances_after_those_of_the_file(tmp_path: Path) -> None:
    path = write(tmp_path, "instances:\n  - url: http://10.0.0.5:5010\n    name: lab\n")

    instances = resolve_instances(path, ["http://10.0.0.6:5010", "http://10.0.0.7"])

    assert [i.name for i in instances] == ["lab", "10.0.0.6_5010", "10.0.0.7"]
    assert instances[1] == Instance(url="http://10.0.0.6:5010", name="10.0.0.6_5010")


def test_duplicate_names_in_the_file_are_rejected(tmp_path: Path) -> None:
    message = load_error(
        tmp_path,
        """
instances:
  - url: http://10.0.0.5:5010
    name: lab
  - url: http://10.0.0.6:5010
    name: lab
""",
    )

    assert "'lab'" in message
    assert "http://10.0.0.5:5010" in message
    assert "http://10.0.0.6:5010" in message


def test_an_explicit_name_clashing_with_a_derived_one_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "instances:\n  - url: http://10.0.0.6:5010\n    name: 10.0.0.5_5010\n")

    message = resolve_error(path, ["http://10.0.0.5:5010"])

    assert "'10.0.0.5_5010'" in message


def test_the_same_url_given_twice_is_rejected_as_a_duplicate_name() -> None:
    message = resolve_error(None, ["http://10.0.0.5:5010", "http://10.0.0.5:5010/"])

    assert "'10.0.0.5_5010'" in message
    assert "once" in message


def test_an_entry_without_url_is_rejected_naming_the_entry(tmp_path: Path) -> None:
    message = load_error(
        tmp_path,
        "instances:\n  - url: http://10.0.0.5:5010\n  - name: paris\n",
    )

    assert "entry 2" in message
    assert "'url'" in message
    assert "required" in message


def test_an_unknown_field_is_rejected_with_the_accepted_fields(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: https://easyucs.example.com\n    verfy_tls: false\n")

    assert "entry 1" in message
    assert "'verfy_tls'" in message
    for accepted in ("url", "name", "verify_tls", "ca_bundle", "auth"):
        assert accepted in message


def test_an_unknown_top_level_field_is_rejected(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instance:\n  - url: https://easyucs.example.com\n")

    assert "'instance'" in message
    assert "instances" in message


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "instances"),
        ("instances: []\n", "at least one"),
        ("instances: http://10.0.0.5\n", "list"),
        ("instances:\n  - http://10.0.0.5\n", "entry 1"),
        ("- url: http://10.0.0.5\n", "instances"),
    ],
)
def test_a_file_without_a_list_of_instance_entries_is_rejected(tmp_path: Path, text: str, expected: str) -> None:
    assert expected in load_error(tmp_path, text)


def test_an_absent_auth_block_is_accepted(tmp_path: Path) -> None:
    assert len(load(tmp_path, "instances:\n  - url: http://10.0.0.5:5010\n")) == 1


def test_auth_type_none_is_accepted(tmp_path: Path) -> None:
    (instance,) = load(tmp_path, "instances:\n  - url: http://10.0.0.5:5010\n    auth:\n      type: none\n")

    assert instance == Instance(url="http://10.0.0.5:5010", name="10.0.0.5_5010")


def test_an_auth_block_requires_a_type(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://10.0.0.5:5010\n    auth:\n      username: admin\n")

    assert "entry 1" in message
    assert "'auth.type'" in message
    assert "required" in message


def test_an_unsupported_auth_type_is_rejected_as_not_supported_yet(tmp_path: Path) -> None:
    message = load_error(
        tmp_path,
        """
instances:
  - url: http://10.0.0.5:5010
    auth:
      type: basic
      username: admin
      password_env: EASYUCS_PASSWORD
""",
    )

    assert "entry 1" in message
    assert "'basic'" in message
    assert "not supported yet" in message
    assert "'none'" in message


def test_a_literal_password_is_always_rejected_pointing_to_password_env(tmp_path: Path) -> None:
    message = load_error(
        tmp_path,
        "instances:\n  - url: http://10.0.0.5:5010\n    auth:\n      type: none\n      password: hunter2\n",
    )

    assert "entry 1" in message
    assert "password_env" in message
    assert "hunter2" not in message


def test_a_literal_password_next_to_the_url_is_also_rejected_pointing_to_password_env(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://10.0.0.5:5010\n    password: hunter2\n")

    assert "entry 1" in message
    assert "password_env" in message
    assert "hunter2" not in message


def test_a_yaml_syntax_error_does_not_echo_the_offending_line(tmp_path: Path) -> None:
    message = load_error(
        tmp_path, 'instances:\n  - url: http://10.0.0.5:5010\n    auth:\n      password: "hunter2\n'
    )

    assert "hunter2" not in message
    assert re.search(r"line \d+", message)


def test_an_unknown_auth_field_is_rejected(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://10.0.0.5:5010\n    auth:\n      type: none\n      token: x\n")

    assert "'auth.token'" in message


@pytest.mark.parametrize(
    ("entry", "field"),
    [
        ("verify_tls: 'no'", "verify_tls"),
        ("ca_bundle: 42", "ca_bundle"),
        ("name: 42", "name"),
        ("name: ''", "name"),
        ("auth: none", "auth"),
    ],
)
def test_fields_of_the_wrong_type_are_rejected(tmp_path: Path, entry: str, field: str) -> None:
    message = load_error(tmp_path, f"instances:\n  - url: https://easyucs.example.com\n    {entry}\n")

    assert "entry 1" in message
    assert f"'{field}'" in message


def test_a_ca_bundle_with_tls_verification_disabled_is_contradictory(tmp_path: Path) -> None:
    message = load_error(
        tmp_path,
        "instances:\n  - url: https://easyucs.example.com\n    verify_tls: false\n    ca_bundle: ca.pem\n",
    )

    assert "entry 1" in message
    assert "ca_bundle" in message
    assert "verify_tls" in message


def test_an_invalid_url_in_the_file_is_rejected_naming_the_entry(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://10.0.0.5\n  - url: ftp://10.0.0.6\n")

    assert "entry 2" in message
    assert "'url'" in message
    assert "ftp://10.0.0.6" in message


def test_a_url_with_credentials_in_the_file_is_rejected_without_echoing_them(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://admin:hunter2@10.0.0.5\n")

    assert "entry 1" in message
    assert "hunter2" not in message


def test_the_entry_is_also_named_by_its_name_when_it_has_one(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://10.0.0.5\n  - name: paris\n    verify_tls: 1\n")

    assert "entry 2 ('paris')" in message


def test_a_yaml_syntax_error_is_reported_with_its_line(tmp_path: Path) -> None:
    message = load_error(tmp_path, "instances:\n  - url: http://10.0.0.5\n    name: [lab\n")

    assert "instances.yaml" in message
    assert re.search(r"line \d+", message)


def test_a_json_syntax_error_is_reported_with_its_line(tmp_path: Path) -> None:
    message = load_error(tmp_path, '{"instances": [\n  {"url": "http://10.0.0.5",}\n]}\n', "instances.json")

    assert "instances.json" in message
    assert "line 2" in message


def test_a_missing_file_is_reported(tmp_path: Path) -> None:
    message = resolve_error(tmp_path / "missing.yaml", [])

    assert "missing.yaml" in message


@pytest.mark.parametrize("url", ["admin:hunter2@10.0.0.5:5010", "http://admin:hunter2@10.0.0.5", "http://:hunter2@h"])
def test_a_url_option_with_credentials_is_rejected_without_echoing_them(url: str) -> None:
    message = resolve_error(None, [url])

    assert "--url" in message
    assert "credentials" in message
    assert "hunter2" not in message


def test_an_invalid_url_option_is_rejected() -> None:
    message = resolve_error(None, ["10.0.0.5:5010"])

    assert "--url" in message
    assert "10.0.0.5:5010" in message
