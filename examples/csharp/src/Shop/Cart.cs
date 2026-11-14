namespace Shop;

public class Cart
{
    private readonly Calc calc = new Calc();

    public int Total(int price, int qty)
    {
        return calc.Mul(price, qty);
    }
}
