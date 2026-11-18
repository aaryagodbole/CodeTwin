# Sample repositories

One tiny repository per language (a `calc` module, a `cart` module that uses it, one test that checks `calc`
and one that runs `cart` without checking it), used by the `languages` CI job:

```bash
python scripts/language_smoke.py examples/go
```

copies the sample into a temporary git repository and runs every CodeTwin feature on it. `example.json` says
which file to edit, which test covers it and how to install the sample's dependencies. `lua` has no test
runner (static evidence only); `mixed` is a Python service with a TypeScript front end in one repository.
