require_relative "calc"

module Cart
  def self.total(price, qty)
    Calc.mul(price, qty)
  end
end
