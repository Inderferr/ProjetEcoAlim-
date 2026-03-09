from EcoAlim_lib.ProblemFormalisation import ProblemFormalisation
from EcoAlim_lib.constants import OBJECTIFS_ENV, SCORE_PREF, NUTRITIONALELEMENTS
import pandas as pd
import highspy as hp
import itertools
from tqdm import tqdm

def display_data(file_full):
    # Chargement des feuilles
    data = pd.read_excel(file_full, sheet_name=None, index_col=[0, 1])
    full_df = data["MP"] 
    # Filtrage des colonnes dont le nom contient un des mots-clés
    df_obj_env = full_df[[col for col in full_df.columns if any(mot +" ECOALIM" in col for mot in OBJECTIFS_ENV)]]
    # Renommer les colonnes pour enlever " ECOALIM"
    df_obj_env.columns = [col.replace(" ECOALIM", "") for col in df_obj_env.columns]
    df_obj_price = full_df[[col for col in full_df.columns if "prix" in col]]
    # Renommer les colonnes pour remplacer "Contexte prix" par "Coût"
    df_obj_price.columns = [col.replace("Contexte prix", "Coût") if "Contexte prix" in col else col for col in df_obj_price.columns]
    
    # S'assurer que les colonnes numériques sont bien en float
    df_obj_env = df_obj_env.astype(float)
    df_obj_price = df_obj_price.astype(float)
    df_PEF = full_df[[col for col in full_df.columns if any(mot in col for mot in SCORE_PREF)]]
    df_nutritionnal = full_df.loc[:, NUTRITIONALELEMENTS]
    return {
        "df_obj_env": df_obj_env,
        "df_obj_price": df_obj_price,
        "df_PEF": df_PEF,
        "df_nutritionnal": df_nutritionnal,
        "score_unique": full_df["Score unique EF3.1  (mPt)"]
    }

def generateWeightGrid(steps=10, num_objectives=7) -> list:
    grid = []
    # Générer toutes les combinaisons possibles où la somme des indices multipliée par l'incrément est égale à steps
    for comb in itertools.product(range(steps + 1), repeat=num_objectives):
        if sum(comb) == steps:
            # Convertir les indices en poids fractionnaires
            weights = [x / steps for x in comb]
            grid.append(weights)
    return grid

def setup_model(data: ProblemFormalisation) -> tuple:
    """
    Configure le modèle d'optimisation avec les variables de décision et les contraintes.

    Paramètres :
    - data (ProblemFormalisation) : Données nécessaires à l'optimisation.

    Retourne :
    - model : Le modèle d'optimisation configuré.
    - x : Les variables de décision ajoutées au modèle.
    """
    RM = data._objectifsValues.index  # Liste des matières premières
    NUTRIMENTS = data._nutritionalConstraints.index  # Liste des nutriments
    # Initialisation du modèle HiGHS
    model = hp.Highs()
    model.setOptionValue("output_flag", False)

    # Variables de décision [0,1]
    x = model.addVariables(RM, type=hp.HighsVarType.kContinuous, name_prefix="x", lb=0, ub=1)

    # Contraintes d'incorporation
    for rm in RM:
        model.addConstr(x[rm] >= data._incorporationConstraints.loc[rm[1], "Min"] / 1000)
        model.addConstr(x[rm] <= data._incorporationConstraints.loc[rm[1], "Max"] / 1000)

    # Contraintes nutritionnelles (min/max)
    for nut in NUTRIMENTS:
        model.addConstr(
            model.qsum(x[rm] * float(data._nutritionalValues.loc[rm, nut]) for rm in RM)
            >= data._nutritionalConstraints.loc[nut, "Min"]
        )
        model.addConstr(
            model.qsum(x[rm] * float(data._nutritionalValues.loc[rm, nut]) for rm in RM)
            <= data._nutritionalConstraints.loc[nut, "Max"]
        )

    # Contrainte de somme des taux = 1
    model.addConstr(model.qsum(x[rm] for rm in RM) == 1)


    # Retourner le modèle et les variables de décision
    return model, x

def evaluate_cost_min(data: ProblemFormalisation) -> pd.Series: 
    """
    Fonction pour évaluer le coût minimal d'un problème d'optimisation.

    Cette fonction configure un modèle d'optimisation, définit une fonction objectif
    pour minimiser le coût, résout le modèle, et calcule les impacts environnementaux.

    Paramètres :
    - data (ProblemFormalisation) : Une instance de la classe ProblemFormalisation contenant
      les données nécessaires à l'optimisation (contraintes, objectifs, valeurs nutritionnelles, etc.).

    Retourne :
    - pd.Series : Une série contenant les impacts environnementaux calculés après optimisation.
    """
    # Récupération des matières premières (indices)
    RM = data._objectifsValues.index

    # Initialisation du modèle HiGHS et des variables de décision
    model, x = setup_model(data)

    # Définition de la fonction objectif : minimisation du coût total
    # Chaque matière première est pondérée par son prix
    model.minimize(model.qsum(x[rm] * float(data._objectifsValues.loc[rm, data._price_index]) for rm in RM))
    # Résolution du modèle
    model.run()
    if model.getModelStatus() != hp.HighsModelStatus.kOptimal:
        # Vérification que le modèle a trouvé une solution optimale
        raise RuntimeError("❌ Modèle non optimal lors de la minimisation du coût.")

    # Récupération des valeurs optimales des variables de décision
    var_values = pd.Series({rm: model.variableValue(x[rm]) for rm in RM})

    # Calcul des impacts environnementaux en multipliant les variables optimales
    # par les coefficients des objectifs environnementaux
    impacts = pd.Series(data._objectifsValues.mul(var_values, axis=0).sum(axis=0))

    # Retourne les impacts environnementaux calculés
    return impacts

def is_pareto(objectives_values) -> list:
    n_points = objectives_values.shape[0]  # Nombre de points (lignes)
    is_pareto = [True] * n_points  # Initialiser tous les points comme Pareto

    # Identifier les doublons
    duplicates = objectives_values.duplicated(keep="last")  # Marquer les doublons sauf le premier
    for i, is_duplicate in enumerate(duplicates):
        if is_duplicate:
            is_pareto[i] = False  # Marquer les doublons (sauf le premier) comme non Pareto

    # Comparer les points restants
    for i in tqdm(range(n_points), desc="Comparatif des points 2 à 2", unit="points"):
        if not is_pareto[i]:
            continue  # Ignorer les points déjà marqués comme non Pareto
        point_i = objectives_values.iloc[i]
        for j in range(n_points):
            if i == j or not is_pareto[j]:
                continue  # Ne pas comparer un point avec lui-même ou un point déjà non Pareto
            # Récupérer les points i et j
            point_j = objectives_values.iloc[j]
            # Vérifier si j domine i (en minimisation)
            if all(point_j <= point_i) and any(point_j < point_i):
                is_pareto[i] = False  # i n'est pas Pareto
                break  # Pas besoin de continuer à vérifier pour ce point
    return is_pareto

def setup_model_limit(data: ProblemFormalisation) -> tuple:
    """
    Configure le modèle d'optimisation avec les variables de décision et les contraintes.

    Paramètres :
    - data (ProblemFormalisation) : Données nécessaires à l'optimisation.

    Retourne :
    - model : Le modèle d'optimisation configuré.
    - x : Les variables de décision ajoutées au modèle.
    """
    RM = data._objectifsValues.index  # Liste des matières premières
    NUTRIMENTS = data._nutritionalConstraints.index  # Liste des nutriments
    # Initialisation du modèle HiGHS
    model = hp.Highs()
    model.setOptionValue("output_flag", False)
    # Variables de décision [0,1]
    x = model.addVariables(RM, type=hp.HighsVarType.kContinuous, name_prefix="x", lb=0, ub=1)
    # Contraintes d'incorporation
    for rm in RM:
        model.addConstr(x[rm] >= data._incorporationConstraints.loc[rm[1], "Min"] / 1000)
        model.addConstr(x[rm] <= data._incorporationConstraints.loc[rm[1], "Max"] / 1000)
    # Contraintes nutritionnelles (min/max)
    for nut in NUTRIMENTS:
        model.addConstr(
            model.qsum(x[rm] * float(data._nutritionalValues.loc[rm, nut]) for rm in RM)
            >= data._nutritionalConstraints.loc[nut, "Min"]
        )
        model.addConstr(
            model.qsum(x[rm] * float(data._nutritionalValues.loc[rm, nut]) for rm in RM)
            <= data._nutritionalConstraints.loc[nut, "Max"]
        )
    # Contrainte de somme des taux = 1
    model.addConstr(model.qsum(x[rm] for rm in RM) == 1)
    # Ajout des contraintes spécifiques pour chaque objectif environnemental
    cout_min = evaluate_cost_min(data)  # Calcul du coût minimal
    for obj in OBJECTIFS_ENV:
        # Ajout d'une contrainte pour limiter chaque objectif à 105% de son minimum
        model.addConstr(model.qsum(
            data._objectifsValues.loc[rm, obj] * x[rm] for rm in RM
        ) <= 1.05 * cout_min[obj])

    # Retourner le modèle et les variables de décision
    return model, x

def nadir(data: ProblemFormalisation) -> pd.Series:
    """
    Fonction pour calculer les points de nadir pour un problème d'optimisation.

    Le nadir est un vecteur contenant les pires valeurs possibles pour chaque objectif
    dans l'ensemble des solutions optimales. Cette fonction maximise chaque objectif
    indépendamment pour déterminer ces valeurs.

    Paramètres :
    - data (ProblemFormalisation) : Une instance de la classe ProblemFormalisation contenant
      les données nécessaires à l'optimisation (contraintes, objectifs, valeurs nutritionnelles, etc.).

    Retourne :
    - pd.Series : Une série contenant les valeurs de nadir pour chaque objectif.
    """
    # Récupération des indices et colonnes nécessaires
    RM = data._nutritionalValues.index  # Liste des matières premières (indices)
    IMPACTS = data._objectifsValues.columns.to_list()  # Liste des objectifs environnementaux et économiques
    
    # Initialisation du modèle HiGHS
    model, x = setup_model(data)

    # Initialisation de la série pour stocker les points de nadir
    nadir_points = pd.Series(dtype=float)

    # Maximisation de chaque objectif indépendamment
    for obj in IMPACTS:
        # Définir la fonction objectif pour maximiser l'impact actuel
        model.maximize(model.qsum(x[rm] * float(data._objectifsValues.loc[rm, obj]) for rm in RM))
        model.run()  # Résoudre le modèle

        # Vérifier si la solution est optimale
        if model.getModelStatus() != hp.HighsModelStatus.kOptimal:
            raise RuntimeError(f"❌ Modèle non optimal lors de la maximisation de {obj}.")

        # Stocker la valeur optimale de l'objectif dans les points de nadir
        nadir_points[obj] = model.getInfo().objective_function_value

    # Retourner les points de nadir pour tous les objectifs
    return nadir_points

def ideal(data: ProblemFormalisation) -> pd.Series:
    """
    Fonction pour calculer les points idéaux pour un problème d'optimisation.

    Le point idéal est un vecteur contenant les meilleures valeurs possibles pour chaque objectif
    dans l'ensemble des solutions optimales. Cette fonction minimise chaque objectif
    indépendamment pour déterminer ces valeurs.

    Paramètres :
    - data (ProblemFormalisation) : Une instance de la classe ProblemFormalisation contenant
      les données nécessaires à l'optimisation (contraintes, objectifs, valeurs nutritionnelles, etc.).

    Retourne :
    - pd.Series : Une série contenant les valeurs idéales pour chaque objectif.
    """

        # Récupération des indices et colonnes nécessaires
    RM = data._nutritionalValues.index  # Liste des matières premières (indices)
    IMPACTS = data._objectifsValues.columns.to_list()  # Liste des objectifs environnementaux et économiques

    # Initialisation du modèle HiGHS
    model, x = setup_model(data)

    # Initialisation de la série pour stocker les points idéaux
    ideal_points = pd.Series(dtype=float)

    # Minimisation de chaque objectif indépendamment
    for obj in IMPACTS:
        # Définir la fonction objectif pour minimiser l'impact actuel
        model.minimize(model.qsum(x[rm] * float(data._objectifsValues.loc[rm, obj]) for rm in RM))
        model.run()  # Résoudre le modèle

        # Vérifier si la solution est optimale
        if model.getModelStatus() != hp.HighsModelStatus.kOptimal:
            raise RuntimeError(f"❌ Modèle non optimal lors de la minimisation de {obj}.")

        # Stocker la valeur optimale de l'objectif dans les points idéaux
        ideal_points[obj] = model.getInfo().objective_function_value

    # Retourner les points de nadir pour tous les objectifs
    return ideal_points


def greedy_reduction(df: pd.DataFrame, weights: dict[str, float], n: int) -> pd.DataFrame:
    """
    Applique la méthode de réduction gloutonne sur un front de Pareto.
    
    Paramètres :
    - df : DataFrame contenant les colonnes d'objectifs (minimisation).
    - weights : dictionnaire des poids pour chaque objectif {colonne: poids}.
    - n : nombre de solutions à extraire.

    Retourne :
    - Un sous-ensemble de `n` solutions avec les meilleurs scores Q.
    """
    df_bis = df.copy()
    N = len(df)

    # Gérer le cas où le DataFrame a un MultiIndex en colonnes
    if isinstance(df.columns, pd.MultiIndex):
        # Mapper les noms des objectifs vers les colonnes du DataFrame
        column_mapping = {}
        for col in df.columns:
            if len(col) >= 2 and col[1] in weights:
                column_mapping[col[1]] = col
        available_cols = list(column_mapping.values())
        weights_mapped = {column_mapping[obj]: weights[obj] for obj in column_mapping.keys()}
    else:
        # Cas standard avec des colonnes simples
        available_cols = [col for col in weights.keys() if col in df.columns]
        weights_mapped = {col: weights[col] for col in available_cols}

    if not available_cols:
        raise ValueError(f"Aucune colonne du dictionnaire weights {list(weights.keys())} n'existe dans le DataFrame {list(df.columns)}")

    # Calcul des percentiles inversés (meilleur = plus petit rang = percentile élevé)
    percentiles = pd.DataFrame(index=df.index)

    for col in available_cols:  # Utiliser seulement les colonnes disponibles
        # rangs : le plus petit est 1 (meilleur pour la minimisation)
        ranks = df_bis[col].rank(method="min", ascending=True)
        percentiles[col] = (N - ranks + 1) / N  # convert to percentile

    # Score pondéré Q - utiliser seulement les colonnes disponibles avec leurs poids mappés
    df_bis["Q_score"] = sum(weights_mapped[col] * percentiles[col] for col in available_cols)

    # Retourne les n meilleures lignes selon Q_score décroissant
    return df_bis.sort_values("Q_score", ascending=False).head(n)
