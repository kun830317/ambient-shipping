"""customs_pipeline: fetch, normalize, and classify public customs trade data.

Data sources implemented:
  - US Census Bureau International Trade API (monthly imports/exports by HS code)
  - UN Comtrade+ API (monthly/annual trade by HS code, most countries)
  - Taiwan MOF / data.gov.tw customs trade statistics (monthly files)

See customs_pipeline/README.md for the full design document.
"""

__version__ = "0.1.0"
