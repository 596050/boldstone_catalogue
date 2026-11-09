from utils.ibkr.singleton import plan


def test_launch_when_none_running_and_not_halted():
    assert plan([], port_up=False, halted=False, keeper=None)["action"] == "launch"


def test_no_launch_when_halted():
    d = plan([], port_up=False, halted=True, keeper=None)
    assert d["action"] == "halted_no_launch" and d["kill"] == []


def test_healthy_single_with_port_up():
    d = plan([100], port_up=True, halted=False, keeper=100)
    assert d["action"] == "healthy" and d["kill"] == [] and d["keep"] == 100


def test_kills_surplus_keeps_listener():
    d = plan([100, 200, 300], port_up=True, halted=False, keeper=200)
    assert d["action"] == "kill_surplus"
    assert d["keep"] == 200 and sorted(d["kill"]) == [100, 300]


def test_kills_surplus_keeps_oldest_when_no_listener():
    d = plan([300, 100, 200], port_up=False, halted=False, keeper=None)
    # pids arrive sorted from gateway_pids(); keep oldest (lowest pid), kill rest
    assert d["keep"] == 300  # first element is "oldest" as passed
    assert set(d["kill"]) == {100, 200}


def test_single_starting_when_port_not_up_yet():
    d = plan([100], port_up=False, halted=False, keeper=None)
    assert d["action"] == "single_starting_or_stuck" and d["kill"] == []
