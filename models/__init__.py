from .base import MatchModel
from .global_rate import GlobalRateModel
from .season_rate import SeasonRateModel
from .poisson import PoissonModel
from .dixon_coles import DixonColesModel
from .elo import EloModel
from .elo_poisson import EloPoissonModel
from .negbin import NegBinModel

MODELS = {
    "global": GlobalRateModel,
    "season": SeasonRateModel,
    "poisson": PoissonModel,
    "dixoncoles": DixonColesModel,
    "negbin": NegBinModel,
    "elo": EloModel,
    "elopoisson": EloPoissonModel,
}
