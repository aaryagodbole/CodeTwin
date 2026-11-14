require "minitest/autorun"
require_relative "../lib/cart"

class TestCart < Minitest::Test
  def test_total_runs
    Cart.total(2, 3)
  end
end
