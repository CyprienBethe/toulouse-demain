"""Tests of the pure functions of deploy/bootstrap.sh (no root, no network).

Run: python -m unittest discover -s scripts/tests -v

The script is sourced in bash: its main() only runs when it is executed.
The firewall sample below is representative of the iptables rules shipped in
Oracle's Ubuntu images (SSH only, then REJECT), written for this test.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "deploy" / "bootstrap.sh"

ORACLE_LIKE_RULES = """\
# iptables configuration (test sample)
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:InstanceServices - [0:0]
-A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
-A INPUT -p icmp -j ACCEPT
-A INPUT -i lo -j ACCEPT
-A INPUT -p udp --sport 123 -j ACCEPT
-A INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT
-A INPUT -j REJECT --reject-with icmp-host-prohibited
-A FORWARD -j REJECT --reject-with icmp-host-prohibited
-A OUTPUT -d 169.254.0.0/16 -j InstanceServices
COMMIT
"""


def bash(snippet: str, *args: str) -> subprocess.CompletedProcess:
    """Run `snippet` in bash after sourcing bootstrap.sh; args are $1, $2..."""
    script = f'source "{BOOTSTRAP}"\n{snippet}\n'
    return subprocess.run(["bash", "-c", script, "test", *args], capture_output=True, text=True, timeout=30)


class SourcingTest(unittest.TestCase):
    def test_sourcing_does_not_run_main(self):
        result = bash('echo sourced')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "sourced\n")

    def test_syntax(self):
        result = subprocess.run(["bash", "-n", str(BOOTSTRAP)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_xtrace_and_hidden_token_input(self):
        text = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertNotIn("set -x", text)
        # The token is read with -s (not echoed), from the terminal.
        self.assertIn("read -r -s reply </dev/tty", text)
        self.assertIn('ask_secret "    Jeton DuckDNS', text)


class EnvFileTest(unittest.TestCase):
    def test_set_env_value_replaces_appends_and_keeps_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("# comment\nAPI_DOMAIN=old.duckdns.org\nDUCKDNS_TOKEN=\nDUCKDNS_TOKEN=dup\nOTHER=1\n")
            os.chmod(env, 0o644)
            secret = 'a7c4d0ad-114e-40ef-ba1d-d217904a50f2'
            result = bash('set_env_value "$1" API_DOMAIN new.duckdns.org\n'
                          'set_env_value "$1" DUCKDNS_TOKEN "$2"\n'
                          'set_env_value "$1" OTP_JAVA_OPTS \'"-Xms3g -Xmx3g -XX:+AlwaysPreTouch"\'\n'
                          'env_value "$1" OTP_JAVA_OPTS', str(env), secret)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "-Xms3g -Xmx3g -XX:+AlwaysPreTouch\n")
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertEqual(env.read_text(), "# comment\nAPI_DOMAIN=new.duckdns.org\n"
                                              f"DUCKDNS_TOKEN={secret}\nOTHER=1\n"
                                              'OTP_JAVA_OPTS="-Xms3g -Xmx3g -XX:+AlwaysPreTouch"\n')
            self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [".env"])  # no temp file left

    def test_values_are_written_literally(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("A=1")  # no final newline
            result = bash('set_env_value "$1" B "$2"', str(env), "x$(id)`id`\\n'\"")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(env.read_text(), "A=1\nB=x$(id)`id`\\n'\"\n")

    def test_env_example_has_the_keys_bootstrap_sets(self):
        example = (ROOT / "deploy" / ".env.example").read_text(encoding="utf-8")
        for key in ("API_DOMAIN", "SITE_ORIGIN", "GRAPH_REPOSITORY", "OTP_JAVA_OPTS", "OTP_MEM_LIMIT",
                    "DUCKDNS_SUBDOMAIN", "DUCKDNS_TOKEN"):
            self.assertRegex(example, rf"(?m)^{key}=", key)
        self.assertRegex(example, r"(?m)^SITE_ORIGIN=https://cyprienbethe\.github\.io$")


class InputTest(unittest.TestCase):
    def test_normalize_and_validate_subdomain(self):
        cases = {"toulouse-demain": "toulouse-demain", " Toulouse-Demain.duckdns.org ": "toulouse-demain",
                 "https://abc.duckdns.org/": "abc", "abc def": "abcdef"}
        for typed, expected in cases.items():
            result = bash('normalize_subdomain "$1"', typed)
            self.assertEqual(result.stdout, expected, typed)
        for name, ok in {"abc": True, "a-1": True, "-abc": False, "abc-": False, "a_b": False,
                         "a.b": False, "": False, "a" * 63: True, "a" * 64: False}.items():
            self.assertEqual(bash('valid_subdomain "$1"', name).returncode == 0, ok, name)

    def test_validate_token(self):
        for token, ok in {"a7c4d0ad-114e-40ef-ba1d-d217904a50f2": True, "short": False,
                          'a7c4d0ad-114e-40ef-ba1d-d217904a50f2"': False, "a7c4d0ad 114e": False,
                          "a7c4d0ad-114e-40ef-ba1d-d217904a50f2&ip=1": False}.items():
            self.assertEqual(bash('valid_token "$1"', token).returncode == 0, ok, token)


class FirewallFileTest(unittest.TestCase):
    RULE = "-A INPUT -p tcp -m state --state NEW -m tcp --dport {} -j ACCEPT"

    def insert(self, content: str, port: int) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            rules = Path(tmp) / "rules.v4"
            rules.write_text(content)
            result = bash('grep -qxF -- "$2" "$1" || insert_rule_in_file "$1" "$2"', str(rules),
                          self.RULE.format(port))
            return result.returncode, rules.read_text()

    def test_inserted_before_reject_and_idempotent(self):
        code, text = self.insert(ORACLE_LIKE_RULES, 80)
        self.assertEqual(code, 0)
        code, text = self.insert(text, 443)
        code, again = self.insert(text, 443)
        self.assertEqual(again, text)
        lines = text.splitlines()
        reject = lines.index("-A INPUT -j REJECT --reject-with icmp-host-prohibited")
        self.assertEqual(lines[reject - 2:reject], [self.RULE.format(80), self.RULE.format(443)])
        self.assertEqual(lines.count(self.RULE.format(443)), 1)
        # Nothing else changed.
        self.assertEqual([l for l in lines if "dport 80 " not in l and "dport 443 " not in l],
                         ORACLE_LIKE_RULES.splitlines())

    def test_filter_table_only_and_commit_fallback(self):
        content = "*nat\n:PREROUTING ACCEPT [0:0]\n-A INPUT -j DROP\nCOMMIT\n*filter\n:INPUT ACCEPT [0:0]\nCOMMIT\n"
        code, text = self.insert(content, 80)
        self.assertEqual(code, 0)
        self.assertEqual(text, content.replace("*filter\n:INPUT ACCEPT [0:0]\nCOMMIT",
                                               f"*filter\n:INPUT ACCEPT [0:0]\n{self.RULE.format(80)}\nCOMMIT"))

    def test_no_filter_table_fails(self):
        code, text = self.insert("*nat\nCOMMIT\n", 80)
        self.assertNotEqual(code, 0)
        self.assertEqual(text, "*nat\nCOMMIT\n")


class MemoryTest(unittest.TestCase):
    def test_memory_settings(self):
        # MemTotal in kB as reported by /proc/meminfo, slightly below the nominal size.
        for kib, expected in {12_000_000: "6g 8g", 11_700_000: "6g 8g", 5_900_000: "3g 4g",
                              3_800_000: "2g 3g"}.items():
            self.assertEqual(bash('memory_settings "$1"', str(kib)).stdout, expected, kib)


if __name__ == "__main__":
    unittest.main()
