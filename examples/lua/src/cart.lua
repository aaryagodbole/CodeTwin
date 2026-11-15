local calc = require("src.calc")

local M = {}

function M.total(price, qty)
  return calc.mul(price, qty)
end

return M
