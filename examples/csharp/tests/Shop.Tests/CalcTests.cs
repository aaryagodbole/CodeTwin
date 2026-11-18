using Shop;
using Xunit;

namespace Shop.Tests;

public class CalcTests
{
    [Fact]
    public void Add() => Assert.Equal(3, new Calc().Add(1, 2));
}
