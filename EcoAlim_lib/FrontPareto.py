from EcoAlim_lib.tools import is_pareto
from EcoAlim_lib.ProblemFormalisation import ProblemFormalisation
import pandas as pd


class FrontPareto : 
    # Class to formalize the solution
    # Initialization of the class
    def __init__(self, dict_results : dict, data : ProblemFormalisation, time : float, dict_pond : dict):	
        self._solution_points = dict_results["solutions"] * 100
        self._objective_value = dict_results["objectives"]
        self._data = data
        self._time = time
        self._dict_pond = dict_pond
        self._paretofront = self.extract_pareto_front()

    def extract_pareto_front(self) -> pd.DataFrame:
        print("-> Extraction du front de Pareto")

        col_names = self._solution_points.columns
        self._solution_points.columns = col_names
        self._objective_value.columns = col_names
        # Harmoniser : forcer un MultiIndex sur _objective_value
        self._objective_value.index = pd.MultiIndex.from_tuples([("", idx) for idx in self._objective_value.index])
        # Concaténer solution + objectifs
        df_full = pd.concat([self._solution_points, self._objective_value], axis=0)
        # Calculer le booléen pareto sur objectifs (transposé)
        pareto_bool = is_pareto(self._objective_value.T)
        # Ajouter ligne "Pareto" avec index MultiIndex
        df_full.loc[("", "Pareto"),df_full.columns] =  [float(i) for i in pareto_bool]

        return df_full
