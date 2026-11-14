using Shop;
using Xunit;

namespace Shop.Tests;

public class CartTests
{
    [Fact]
    public void TotalRuns() => new Cart().Total(2, 3);
}
