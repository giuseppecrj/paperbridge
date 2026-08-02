from argparse import Namespace

from paperbridge_cli.main import _rpc


def test_ping_mapping_does_not_require_cut_confirmation_argument():
    assert _rpc(Namespace(group="device", action="ping")) == ("system.ping", {})
