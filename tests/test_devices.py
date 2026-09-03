from app.api.devices import check_device


def test_check_device_iphone_17():
    ok, matched = check_device("iPhone 17")
    assert ok is True
    assert matched == "iphone 17"


def test_check_device_iphone_17_pro():
    ok, matched = check_device("iPhone 17 Pro")
    assert ok is True
    assert matched == "iphone 17"


def test_check_device_iphone_air():
    ok, matched = check_device("iPhone Air")
    assert ok is True
    assert matched == "iphone air"


def test_check_device_unknown():
    ok, matched = check_device("Nokia 3310")
    assert ok is False
    assert matched is None
