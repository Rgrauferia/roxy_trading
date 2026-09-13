"""Synthetic request/env cases only; no network, real credentials, or accounts."""
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from roxy_os.home_client_identity import (
    HomeClientIdentityConfigError,
    HomeClientIdentityError,
    HomeClientIdentityHeaderError,
    client_ip_identity,
)


HOST = "roxy-home.onrender.com"
ENV_KEYS = ("ROXY_HOME_CLIENT_IP_SOURCE", "RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def render_env(monkeypatch):
    for key, value in zip(ENV_KEYS, ("render_cf", "true", "srv-synthetic", "https://" + HOST)):
        monkeypatch.setenv(key, value)


def request(ip="10.0.0.7", cf="8.8.8.8", host=HOST, extra=(), *, scheme="http"):
    headers = []
    for name, value in (("host", host), ("cf-connecting-ip", cf), *extra):
        if value is not None:
            headers.append((name.encode("ascii"), value.encode("latin-1")))
    return Request({"type": "http", "method": "GET", "path": "/health", "scheme": scheme,
                    "server": ("127.0.0.1", 10000), "client": (ip, 12345) if ip is not None else None,
                    "query_string": b"", "headers": headers})


@pytest.mark.parametrize("ip,expected", [
    ("testclient", "testclient"), (None, "unknown"), ("10.0.0.7", "10.0.0.7"),
    ("127.0.0.1", "127.0.0.1"), ("::1", "::1"), ("::ffff:192.0.2.1", "192.0.2.1"),
    ("2001:4860:4860:0:0:0:0:8888", "2001:4860:4860::8888"),
])
def test_default_socket_preserves_legacy_names_and_normalizes_addresses(ip, expected):
    assert client_ip_identity(request(ip)) == expected


@pytest.mark.parametrize("mode", [None, "socket"])
def test_socket_ignores_all_spoofed_headers_and_render_metadata(monkeypatch, mode):
    if mode is not None:
        monkeypatch.setenv("ROXY_HOME_CLIENT_IP_SOURCE", mode)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "not-a-url")
    forged = (("cf-connecting-ip", "1.1.1.1"), ("x-forwarded-for", "9.9.9.9"),
              ("x-forwarded-host", "evil.test"), ("x-forwarded-proto", "https"),
              ("true-client-ip", "4.4.4.4"))
    assert client_ip_identity(request(cf="not-an-ip", host="evil.test", extra=forged)) == "10.0.0.7"


@pytest.mark.parametrize("mode", ["", "*", "cf", "forwarded", "RENDER_CF", "render_cf ", " socket"])
def test_unknown_modes_fail_closed_without_echo(monkeypatch, mode):
    monkeypatch.setenv("ROXY_HOME_CLIENT_IP_SOURCE", mode)
    with pytest.raises(HomeClientIdentityConfigError) as failure:
        client_ip_identity(request())
    assert str(failure.value) == "No se pudo verificar la conexión de Roxy Home."


@pytest.mark.parametrize("key,value", [
    ("RENDER", None), ("RENDER", "false"), ("RENDER", "TRUE"), ("RENDER", "1"),
    ("RENDER_SERVICE_ID", None), ("RENDER_SERVICE_ID", ""), ("RENDER_SERVICE_ID", " \n"),
    ("RENDER_EXTERNAL_URL", None), ("RENDER_EXTERNAL_URL", ""),
])
def test_render_requires_explicit_runtime_metadata(render_env, monkeypatch, key, value):
    if value is None:
        monkeypatch.delenv(key)
    else:
        monkeypatch.setenv(key, value)
    with pytest.raises(HomeClientIdentityConfigError):
        client_ip_identity(request())


@pytest.mark.parametrize("url", [
    "http://" + HOST, "https://" + HOST + ":80", "https://" + HOST + ":444",
    "https://" + HOST + ":", "https://" + HOST + ":0443", "https://" + HOST + ":bad",
    "https://" + HOST + ":65536", "https://" + HOST + "/path", "https://" + HOST + "//",
    "https://" + HOST + "?", "https://" + HOST + "?secret=synthetic", "https://" + HOST + "#",
    "https://" + HOST + "#synthetic", "https://synthetic-user@" + HOST,
    "https://synthetic-user:synthetic-password@" + HOST, "https://localhost",
    "https://127.0.0.1", "https://8.8.8.8", "https://[2606:4700:4700::1111]",
    "https://" + HOST + ".", " https://" + HOST, "https://" + HOST + " ",
    "https://roxy-home.\nonrender.com", "https://roxy-home.\tonrender.com", "https://roxy_h.onrender.com",
    "https://-roxy.onrender.com", "https://roxy-.onrender.com", "https://" + "a" * 64 + ".test",
    "https://roxy..onrender.com", "https://roxy-homé.onrender.com", "https://[malformed",
    "\\https://" + HOST, "https:\\\\" + HOST, "https://" + HOST + "\\",
    "https://" + HOST + "\\path", "https://evil.test\\@" + HOST,
])
def test_invalid_render_url_is_rejected_without_echo(render_env, monkeypatch, url):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", url)
    with pytest.raises(HomeClientIdentityConfigError) as failure:
        client_ip_identity(request())
    assert str(failure.value) == "No se pudo verificar la conexión de Roxy Home."
    assert failure.value.__suppress_context__ or failure.value.__context__ is None


@pytest.mark.parametrize("control", [chr(value) for value in (*range(32), 127)])
@pytest.mark.parametrize("position", ["prefix", "hostname", "suffix"])
def test_all_c0_and_del_controls_rejected_before_urlsplit(render_env, monkeypatch, control, position):
    urls = {"prefix": control + "https://" + HOST,
            "hostname": "https://roxy-home." + control + "onrender.com",
            "suffix": "https://" + HOST + control}
    # A real OS environment cannot contain NUL. A module-local synthetic getenv
    # exercises the parser guard too, without changing or exposing the process
    # environment (including in a failed-test traceback).
    values = dict(zip(ENV_KEYS, ("render_cf", "true", "srv-synthetic", urls[position])))
    monkeypatch.setattr("roxy_os.home_client_identity.os", SimpleNamespace(getenv=values.get))
    with pytest.raises(HomeClientIdentityConfigError):
        client_ip_identity(request())


@pytest.mark.parametrize("url", ["https://" + HOST, "https://" + HOST + "/", "https://" + HOST + ":443",
                                "https://" + HOST.upper() + ":443/"])
@pytest.mark.parametrize("host", [HOST, HOST.upper(), HOST + ":443"])
def test_render_public_https_authority_matches_dns_case_and_default_port(render_env, monkeypatch, url, host):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", url)
    # Render forwards HTTPS to the application over HTTP; no Origin is needed
    # for identity extraction on a GET, and the socket remains a private proxy.
    assert client_ip_identity(request(host=host, scheme="http")) == "8.8.8.8"


@pytest.mark.parametrize("host", [None, "", "evil.test", "localhost", "127.0.0.1:10000",
                                 HOST + ".", HOST + ":80", HOST + ":0443", HOST + ":",
                                 "https://" + HOST, HOST + "/", HOST + " ", HOST + ",evil.test",
                                 "synthetic-user@" + HOST, HOST + ":443:443"])
def test_render_host_must_match_exact_authority(render_env, host):
    with pytest.raises(HomeClientIdentityHeaderError):
        client_ip_identity(request(host=host, extra=(("x-forwarded-host", HOST),)))


@pytest.mark.parametrize("extra", [(("host", HOST),), (("HOST", HOST),),
                                  (("cf-connecting-ip", "8.8.8.8"),),
                                  (("CF-Connecting-IP", "1.1.1.1"),)])
def test_duplicate_host_or_cf_header_is_rejected_even_when_identical(render_env, extra):
    with pytest.raises(HomeClientIdentityHeaderError):
        client_ip_identity(request(extra=extra))


@pytest.mark.parametrize("value", [None, "", "unknown", " 8.8.8.8", "8.8.8.8 ", "8.8.8.8\n",
                                  "8.8.8.8, 1.1.1.1", "8.8.8.8,8.8.8.8", "8.8.8.8:443",
                                  "[2606:4700:4700::1111]:443", "[2606:4700:4700::1111]",
                                  "2606:4700:4700::1111%eth0", "8.8.8.8%eth0", "008.008.008.008",
                                  "8.8.8.8/32", "2606:4700:4700::1111/128", "invalíd"])
def test_render_rejects_missing_ambiguous_or_invalid_ip_without_fallback(render_env, value):
    with pytest.raises(HomeClientIdentityHeaderError) as failure:
        client_ip_identity(request(ip="1.1.1.1", cf=value,
                                   extra=(("x-forwarded-for", "8.8.8.8"), ("true-client-ip", "8.8.8.8"))))
    assert str(failure.value) == "No se pudo verificar la conexión de Roxy Home."


@pytest.mark.parametrize("value", ["0.0.0.0", "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.0.1",
                                  "169.254.0.1", "100.64.0.1", "192.0.2.1", "198.51.100.1",
                                  "203.0.113.1", "224.0.0.1", "240.0.0.1", "255.255.255.255",
                                  "::", "::1", "fe80::1", "fc00::1", "ff02::1", "2001:db8::1",
                                  "::ffff:127.0.0.1", "::ffff:192.0.2.1", "::ffff:10.0.0.1"])
def test_render_requires_a_public_unicast_address(render_env, value):
    with pytest.raises(HomeClientIdentityHeaderError):
        client_ip_identity(request(cf=value))


@pytest.mark.parametrize("value,expected", [
    ("8.8.8.8", "8.8.8.8"), ("1.1.1.1", "1.1.1.1"),
    ("2606:4700:4700:0:0:0:0:1111", "2606:4700:4700::1111"),
    ("2001:4860:4860::8888", "2001:4860:4860::8888"),
    ("::ffff:8.8.8.8", "8.8.8.8"), ("::FFFF:0808:0808", "8.8.8.8"),
])
def test_render_uses_canonical_cf_address_and_ignores_forwarded_alternatives(render_env, value, expected):
    forged = (("x-forwarded-for", "synthetic-spoof, 9.9.9.9"), ("true-client-ip", "9.9.9.9"),
              ("x-forwarded-proto", "http"), ("x-forwarded-host", "evil.test"))
    assert client_ip_identity(request(cf=value, extra=forged)) == expected


def test_public_clients_have_distinct_identities_behind_same_socket(render_env):
    assert client_ip_identity(request(cf="8.8.8.8")) != client_ip_identity(request(cf="1.1.1.1"))


def test_generic_base_error_supports_safe_http_integration(render_env):
    for bad_request in (request(cf="synthetic-secret"), request(host="synthetic-private-host")):
        with pytest.raises(HomeClientIdentityError) as failure:
            client_ip_identity(bad_request)
        assert failure.value.args == ("No se pudo verificar la conexión de Roxy Home.",)
