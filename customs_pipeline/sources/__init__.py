from . import importyeti, us_census, un_comtrade, taiwan_mof

FETCHERS = {
    "us-census": us_census.fetch,
    "un-comtrade": un_comtrade.fetch,
    "taiwan-mof": taiwan_mof.fetch,
    "importyeti": importyeti.fetch,
}
