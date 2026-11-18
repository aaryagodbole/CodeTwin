require "minitest/autorun"
require_relative "../lib/calc"

class TestCalc < Minitest::Test
  def test_add
    assert_equal 3, Calc.add(1, 2)
  end
end
