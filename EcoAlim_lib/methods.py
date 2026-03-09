from EcoAlim_lib.ProblemFormalisation import ProblemFormalisation
from EcoAlim_lib.constants import OBJECTIFS_ENV, SCORE_PREF, NUTRITIONALELEMENTS
import pandas as pd
import highspy as hp
from tqdm import tqdm
from EcoAlim_lib.tools import generateWeightGrid, setup_model_limit

def ponderation_multiObj_limit(data: ProblemFormalisation, data_norm: ProblemFormalisation, granularity: int, weight: dict) -> dict:
    """
    Résout un problème d'optimisation multi-objectif avec une grille de poids et des contraintes supplémentaires.

    Cette méthode génère des solutions pour différentes combinaisons de poids appliqués
    aux objectifs, tout en respectant des contraintes supplémentaires, et retourne les
    solutions optimales ainsi que les valeurs des objectifs.

    Paramètres :
    - data (ProblemFormalisation) : Données nécessaires à l'optimisation.
    - data_norm (ProblemFormalisation) : Données normalisées.
    - granularity (int) : Nombre de pas pour la grille de poids.
    - weight (dict) : Poids associés aux objectifs.

    Retourne :
    - dict : Résultats des solutions et des objectifs.
    """
    # Récupération des indices des matières premières
    RM = data._objectifsValues.index

    # Génération de la grille de poids
    weightgrid = generateWeightGrid(granularity, len(data._objectifsValues.columns))

    # Initialisation des listes pour stocker les résultats
    solution_points = []  # Stocke les solutions (valeurs des variables de décision)
    objective_values = []  # Stocke les valeurs des objectifs

    # Configuration du modèle avec des contraintes supplémentaires
    model, x = setup_model_limit(data)
    # Résolution du modèle pour chaque combinaison de poids
    for pond in tqdm(weightgrid, desc="Résolution", unit="pond"):

        # Définition de la fonction objectif pondérée
        model.minimize(
            model.qsum(
                float(data_norm._objectifsValues.loc[rm, obj] * weight[obj] * pond[i]) * x[rm]
                for rm in RM for i, obj in enumerate(data_norm._objectifsValues.columns)
            )
        )

        # Résolution du modèle
        model.run()
        if model.getModelStatus() != hp.HighsModelStatus.kOptimal:
            # Vérification que le modèle a trouvé une solution optimale
            raise RuntimeError(f"❌ Modèle non optimal pour pond = {pond}")

        # Récupération des valeurs des variables de décision
        var_series = pd.Series({rm: model.variableValue(x[rm]) for rm in RM})
        solution_points.append(var_series)

        # Calcul des valeurs des objectifs (environnementaux + coût)
        env_vals = data._objectifsValues.T.dot(var_series)
        objective_values.append(env_vals)

    # Création des DataFrames pour les solutions et les objectifs
    # Créer des noms de colonnes simples pour les solutions
    solution_names = [f"Solution_{i+1}" for i in range(len(solution_points))]
    
    # DataFrame des solutions : matières premières en index, solutions en colonnes
    df_points = pd.DataFrame(solution_points).T
    df_points.columns = solution_names
    df_points.index = RM
    
    # DataFrame des objectifs : objectifs en index, solutions en colonnes
    df_obj = pd.DataFrame(objective_values, columns=data._objectifsValues.columns.tolist()).T
    df_obj.columns = solution_names

    return {
        "solutions": df_points,  # Solutions optimales
        "objectives": df_obj  # Valeurs des objectifs
    }

def aliment_by_demande(epsilon: pd.DataFrame, objectifs: list, ponderation: dict, data: ProblemFormalisation, data_norm: ProblemFormalisation):
    """
    Optimise la composition d'un aliment selon des contraintes epsilon personnalisées.

    Paramètres :
    - epsilon (pd.DataFrame) : Contraintes epsilon sur les objectifs environnementaux.
    - objectifs (list) : Liste des objectifs à minimiser.
    - ponderation (dict) : Poids pour chaque objectif.
    - data (ProblemFormalisation) : Données nécessaires à l'optimisation.
    - data_norm (ProblemFormalisation) : Données normalisées.

    Retourne :
    - df_vars : DataFrame contenant les taux d'incorporation des matières premières.
    - df_obj : DataFrame contenant les valeurs des objectifs.
    - df_epsilon : DataFrame contenant les valeurs des contraintes epsilon.
    """
    # Données
    RM = data._objectifsValues.index
    
    # Préparer le modèle
    model = hp.Highs()
    model.setOptionValue("output_flag", False)
    x = model.addVariables(RM, type=hp.HighsVarType.kContinuous, name_prefix="x", lb=0, ub=1)

    # Contraintes epsilon
    if epsilon is not None:
        for index, row in epsilon.iterrows():
            model.addConstr(
                model.qsum(x[rm] * float(data._objectifsValues.loc[rm, index]) for rm in RM) <= row.iloc[0]
            )
    # Contraintes d'incorporation
    for rm in RM:
        model.addConstr(x[rm] >= data._incorporationConstraints.loc[rm[1], "Min"] / 1000)
        model.addConstr(x[rm] <= data._incorporationConstraints.loc[rm[1], "Max"] / 1000)
    # Contraintes nutritionnelles
    nutriments = data._nutritionalConstraints.index
    for nut in nutriments:
        model.addConstr(
            model.qsum(x[rm] * float(data._nutritionalValues.loc[rm, nut]) for rm in RM)
            >= data._nutritionalConstraints.loc[nut, "Min"]
        )
        model.addConstr(
            model.qsum(x[rm] * float(data._nutritionalValues.loc[rm, nut]) for rm in RM)
            <= data._nutritionalConstraints.loc[nut, "Max"]
        )
    # Contrainte somme des taux
    model.addConstr(model.qsum(x[rm] for rm in RM) == 1)

    # Définition de la fonction objectif
    model.minimize(
        model.qsum(
            ponderation[obj] * data_norm._objectifsValues.loc[rm, obj] * x[rm]
            for rm in RM for obj in objectifs
        )
    )
    # Résolution du modèle
    model.run()
    if model.getModelStatus() != hp.HighsModelStatus.kOptimal:
        raise RuntimeError("❌ Modèle non optimal lors de la résolution.")

    # Récupération des solutions
    solution = model.getSolution()
    var_vals = solution.col_value

    # Construction du DataFrame des variables
    df_vars = pd.DataFrame({
        "Taux d'incorporation": [var_vals[i] for i in range(len(RM))]
    }, index=RM)

    # Calcul des valeurs epsilon
    df_epsilon = None
    if epsilon is not None:
        df_epsilon = pd.DataFrame(index=epsilon.index, columns=["Valeurs objectives"])
        for index, row in epsilon.iterrows():
            df_epsilon.loc[index, "Valeurs objectives"] = sum([
                data._objectifsValues.loc[rm, index] * var_vals[i] 
                for i, rm in enumerate(RM)
            ])

    # Calcul des valeurs des objectifs
    df_obj = pd.DataFrame(index=objectifs, columns=["Valeurs objectives"])
    for obj in objectifs:
        df_obj.loc[obj, "Valeurs objectives"] = sum([
            data._objectifsValues.loc[rm, obj] * var_vals[i] 
            for i, rm in enumerate(RM)
        ])

    return df_vars, df_obj, df_epsilon