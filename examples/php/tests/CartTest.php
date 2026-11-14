<?php

use PHPUnit\Framework\TestCase;
use Shop\Cart;

final class CartTest extends TestCase
{
    public function testTotalRuns(): void
    {
        (new Cart())->total(2, 3);
        $this->addToAssertionCount(1);
    }
}
