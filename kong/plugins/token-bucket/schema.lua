-- G4 (Student A): schema for the custom `token-bucket` plugin.
local typedefs = require "kong.db.schema.typedefs"

return {
  name = "token-bucket",
  fields = {
    { protocols = typedefs.protocols_http },
    { config = {
        type = "record",
        fields = {
          { capacity = {
              type = "number",
              required = true,
              default = 5,
              description = "Maximum number of tokens in the bucket.",
          } },
          { refill_rate = {
              type = "number",
              required = true,
              default = 1,
              description = "Tokens replenished per second.",
          } },
        },
    } },
  },
}
