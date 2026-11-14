package com.example.shop;

import org.junit.jupiter.api.Test;

class CartTest {
    @Test
    void totalRuns() {
        new Cart().total(2, 3);
    }
}
