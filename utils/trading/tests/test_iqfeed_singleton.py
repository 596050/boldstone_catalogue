from utils.iqfeed.singleton import keeper_pid
from utils.ibkr.singleton import plan  # shared, already tested


def test_keeper_is_oldest_or_none():
    assert keeper_pid([]) is None
    assert keeper_pid([500, 100, 300]) == 500  # first element = oldest as passed


def test_plan_reused_launch_and_singleton():
    assert plan([], port_up=False, halted=False, keeper=None)["action"] == "launch"
    assert plan([1, 2], port_up=True, halted=False, keeper=1)["action"] == "kill_surplus"
    assert plan([], port_up=False, halted=True, keeper=None)["action"] == "halted_no_launch"
