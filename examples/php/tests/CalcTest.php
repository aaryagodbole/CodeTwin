<?php

use PHPUnit\Framework\TestCase;
use Shop\Calc;

final class CalcTest extends TestCase
{
    public function testAdd(): void
    {
        $this->assertSame(3, (new Calc())->add(1, 2));
    }
}
