from shop.cart import total


def test_total_runs():
    total(2, 3)          # executes the code but checks nothing (weakcheck finds this)
