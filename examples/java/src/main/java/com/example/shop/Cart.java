package com.example.shop;

public class Cart {
    private final Calc calc = new Calc();

    public int total(int price, int qty) {
        return calc.mul(price, qty);
    }
}
