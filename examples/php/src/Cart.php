<?php

namespace Shop;

use Shop\Calc;

class Cart
{
    public function total(int $price, int $qty): int
    {
        return (new Calc())->mul($price, $qty);
    }
}
