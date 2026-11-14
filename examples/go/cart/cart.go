package cart

import "example.com/shop/calc"

func Total(price, qty int) int {
	return calc.Mul(price, qty)
}
