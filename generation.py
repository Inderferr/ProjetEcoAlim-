import streamlit as st
import pandas as pd
import numpy as np
import time
from EcoAlim_lib.normalisation import normalisationCrolard
from EcoAlim_lib.methods import ponderation_multiObj_limit, aliment_by_demande
from EcoAlim_lib.tools import ideal, nadir, greedy_reduction
from EcoAlim_lib.FrontPareto import FrontPareto

# ===== CONSTANTES =====
DEFAULT_GRANULARITY = 8
MAX_GRANULARITY = 50
MIN_GRANULARITY = 2
DEFAULT_WEIGHT = 1.0
EPSILON_PRECISION = 6

# ===== FONCTIONS UTILITAIRES =====

def validate_problem_instance():
    """Vérifie qu'une instance de problème active existe"""
    return ('instance_active' in st.session_state and 
            st.session_state.instance_active is not None)

def calculate_reference_points(problem, objectives):
    """Calcule les points idéal et nadir pour les objectifs donnés"""
    try:
        with st.spinner("Calcul des points de référence (idéal et nadir)..."):
            ideal_points = ideal(problem)
            nadir_points = nadir(problem)
        
        # Validation des objectifs
        valid_objectives = []
        reference_data = []
        
        for obj in objectives:
            if obj in ideal_points.index and obj in nadir_points.index:
                valid_objectives.append(obj)
                reference_data.append({
                    "Objectif": obj,
                    "Idéal (min)": f"{ideal_points[obj]:.{EPSILON_PRECISION}f}",
                    "Nadir (max)": f"{nadir_points[obj]:.{EPSILON_PRECISION}f}"
                })
            else:
                st.warning(f"⚠️ Objectif '{obj}' ignoré : non trouvé dans les points de référence")
        
        return ideal_points, nadir_points, valid_objectives, reference_data
        
    except Exception as e:
        st.error(f"Erreur lors du calcul des points de référence : {e}")
        return None, None, [], []

def create_epsilon_constraints(objectives, ideal_points, nadir_points):
    """Crée les contraintes epsilon initiales"""
    epsilon_data = {}
    
    for obj in objectives:
        if obj in ideal_points.index and obj in nadir_points.index:
            # Utiliser la valeur nadir comme défaut (plus permissive)
            default_val = nadir_points[obj]
            epsilon_data[obj] = [default_val]
    
    if epsilon_data:
        df_epsilon = pd.DataFrame(epsilon_data).T
        df_epsilon.columns = ["Epsilon"]
        return df_epsilon
    
    return None

def validate_epsilon_constraints(epsilon_objectives, df_edited, ideal_points):
    """Valide les contraintes epsilon"""
    errors = []
    
    for obj in epsilon_objectives:
        try:
            if obj not in df_edited.index:
                errors.append(f"⚠️ **{obj}** : Objectif non trouvé dans les contraintes epsilon")
                continue
                
            if obj not in ideal_points.index:
                errors.append(f"⚠️ **{obj}** : Objectif non trouvé dans les points idéaux")
                continue
            
            epsilon_val = df_edited.loc[obj, "Epsilon"]
            ideal_val = ideal_points[obj]
            
            if epsilon_val < ideal_val:
                errors.append(f"⚠️ **{obj}** : Epsilon ({epsilon_val:.{EPSILON_PRECISION}f}) < Idéal ({ideal_val:.{EPSILON_PRECISION}f})")
                
        except Exception as e:
            errors.append(f"⚠️ **{obj}** : Erreur de validation ({str(e)})")
    
    return errors

# ===== COMPOSANTS D'INTERFACE =====
def create_max_cost(problem):
    """Crée l'interface pour choisir une borne budgétaire"""
    # Checkbox pour activer la borne
    use_budget_constraint = st.checkbox(
        "Activer la borne budgétaire", 
        value=False, 
        key="activate_budget_constraint"
    )
    
    if use_budget_constraint:
        # Obtenir l'objectif de coût
        price_objective = problem._price_index
        
        # Calculer les points de référence pour l'objectif de coût
        ideal_points, nadir_points, valid_objectives, reference_data = calculate_reference_points(
            problem, [price_objective]
        )
        
        if not valid_objectives or price_objective not in valid_objectives:
            st.error(f"❌ Impossible de calculer les points de référence pour l'objectif de coût : {price_objective}")
            return None
        
        # Petit DataFrame avec min/max
        cost_min = ideal_points[price_objective]
        cost_max = nadir_points[price_objective]
        
        budget_info = pd.DataFrame({
            "Valeur": [cost_min, cost_max]
        }, index=["Min", "Max"])
        
        st.markdown("**📊 Points de référence pour la borne budgétaire :**")
        st.dataframe(budget_info, use_container_width=True)
        
        # L'utilisateur rentre à la main une borne
        budget_limit = st.number_input(
            f"Borne budgétaire maximum :",
            min_value=0.0,
            value=float(cost_max),
            step=0.0001,
            format="%.4f",
            help=f"Entrez une valeur libre (Idéal: {cost_min:.4f} | Nadir: {cost_max:.4f})",
            key="manual_budget_limit"
        )
        
        return budget_limit
    
    return None



def create_weight_configuration(objectives, equal_weights_default=True, key_prefix=""):
    """Crée l'interface de configuration des poids"""
    use_equal_weights = st.checkbox(f"Utiliser des poids égaux", value=equal_weights_default, key=f"{key_prefix}_equal_weights")
    
    if use_equal_weights:
        weights = {obj: DEFAULT_WEIGHT for obj in objectives}
        st.success(f"Poids égaux appliqués à {len(objectives)} objectifs")
    else:
        st.markdown("**Ajustez les poids :**")
        weights = {}
        for obj in objectives:
            weights[obj] = st.slider(
                f"{obj}", 
                0.1, 10.0, DEFAULT_WEIGHT, 0.1, 
                key=f"{key_prefix}_{obj}"
            )
        
        # Affichage des pourcentages
        total = sum(weights.values())
        if total > 0:
            st.markdown("**Répartition en pourcentages :**")
            for obj, weight in weights.items():
                percentage = (weight / total) * 100
                st.text(f"{obj}: {percentage:.1f}%")
    
    return weights

def create_epsilon_editor(objectives, problem):
    """Crée l'éditeur de contraintes epsilon"""
    epsilon_objectives = st.multiselect(
        "Sélectionner les objectifs à contraindre", 
        objectives, 
        key="epsilon_selector"
    )
    
    if not epsilon_objectives:
        return [], None, None, None
    
    # Calcul des points de référence
    ideal_points, nadir_points, valid_objectives, reference_data = calculate_reference_points(
        problem, epsilon_objectives
    )
    
    if not valid_objectives:
        st.error("Aucun objectif valide pour les contraintes epsilon")
        return [], None, None, None
    
    # Affichage des points de référence
    if reference_data:
        st.markdown("**Points de référence calculés :**")
        st.dataframe(pd.DataFrame(reference_data), use_container_width=True)
    
    # Création des contraintes epsilon
    df_epsilon = create_epsilon_constraints(valid_objectives, ideal_points, nadir_points)
    if df_epsilon is None:
        return [], None, None, None
    
    # Interface d'édition
    if "epsilon_editor_state" not in st.session_state:
        st.session_state.epsilon_editor_state = df_epsilon.copy()
        st.session_state.epsilon_editor_key = 0
    
    if st.button("Réinitialiser les valeurs epsilon", key="reset_epsilon_btn"):
        st.session_state.epsilon_editor_state = df_epsilon.copy()
        st.session_state.epsilon_editor_key += 1
    
    # Éditeur de données
    df_edited = st.data_editor(
        st.session_state.epsilon_editor_state,
        num_rows="fixed",
        key=f"epsilon_editor_{st.session_state.epsilon_editor_key}"
    )
    
    # Validation
    if df_edited is not None and ideal_points is not None:
        errors = validate_epsilon_constraints(valid_objectives, df_edited, ideal_points)
        
        if errors:
            st.error("**Contraintes epsilon invalides :**")
            for error in errors:
                st.markdown(error)
            st.info("Les valeurs epsilon doivent être supérieures ou égales aux points idéaux.")
            return valid_objectives, df_edited, ideal_points, False
        else:
            st.success("Toutes les contraintes epsilon sont valides.")
    
    return valid_objectives, df_edited, ideal_points, True

def create_objective_selector(all_objectives, epsilon_objectives):
    """Crée l'interface de sélection des objectifs à optimiser"""
    available_objectives = list(set(all_objectives) - set(epsilon_objectives))
    
    optimization_mode = st.selectbox(
        "Souhaitez-vous minimiser un ou plusieurs objectifs ?", 
        ["Un", "Plusieurs"]
    )
    
    if optimization_mode == "Un":
        objective = st.selectbox(
            "Sélectionner l'objectif à minimiser", 
            available_objectives, 
            key="single_objective"
        )
        return [objective], {objective: DEFAULT_WEIGHT}, None
    else:
        objectives = st.multiselect(
            "Sélectionner les objectifs à minimiser", 
            available_objectives, 
            key="multi_objectives"
        )
        
        if not objectives:
            return [], {}, None
        
        weights = create_weight_configuration(objectives, key_prefix="optimization")
        normalized_data = normalisationCrolard(st.session_state.instance_active)
        
        return objectives, weights, normalized_data

# ===== AFFICHAGE DES RÉSULTATS =====

def display_pareto_results(front_pareto):
    """Affiche les résultats du front de Pareto"""
    st.markdown("### 📊 Résultats du Front de Pareto")
    
    pareto_points = front_pareto._paretofront.loc[:, front_pareto._paretofront.loc[("", "Pareto")] == True]
    
    # Préparation des données d'affichage
    df_display = pareto_points.T.round(4)
    display_names = [f"Solution {i+1}" for i in range(len(df_display))]
    df_display.index = display_names
    
    st.dataframe(df_display.T, use_container_width=True)
    
    return pareto_points, df_display

def display_greedy_reduction_interface(front_pareto, problem):
    """Interface de réduction gloutonne du front de Pareto"""
    st.markdown("### 🎯 Réduction Gloutonne du Front de Pareto")
    st.info("Sélectionnez un sous-ensemble optimal du front de Pareto")
    
    pareto_points = front_pareto._paretofront.loc[:, front_pareto._paretofront.loc[("", "Pareto")] == True]
    df_for_reduction = pareto_points.T.round(4)
    objectives = problem._objectifsValues.columns.tolist()
    
    n_solutions = st.number_input(
        "Nombre de solutions à extraire :",
        min_value=1,
        max_value=len(df_for_reduction),
        value=min(5, len(df_for_reduction)),
        key="n_solutions_greedy"
    )
    
    st.markdown("**Pondération pour la réduction :**")
    reduction_weights = create_weight_configuration(
        objectives, 
        key_prefix="reduction"
    )
    
    st.markdown("**Borne budgétaire :**")
    # Utilisation de la fonction create_max_cost pour gérer la borne budgétaire
    budget_limit = create_max_cost(problem)


    # Application de la réduction
    if st.button("Appliquer la Réduction Gloutonne", key="apply_greedy"):
        try:
            with st.spinner("Application de la réduction gloutonne..."):
                # Si une contrainte budgétaire est définie, filtrer les solutions
                if budget_limit is not None:
                    # Identifier l'objectif de coût dans les colonnes du DataFrame
                    price_objective = problem._price_index
                    
                    # Correction pour le nom de colonne si nécessaire
                    if price_objective not in df_for_reduction.columns:
                        if "Contexte prix" in price_objective:
                            price_objective = price_objective.replace("Contexte prix", "Coût")
                    
                    # Chercher la colonne correspondante dans le MultiIndex
                    matching_column = None
                    for col in df_for_reduction.columns:
                        if isinstance(col, tuple) and len(col) == 2:
                            if col[1] == price_objective:  # Chercher dans le deuxième niveau
                                matching_column = col
                                break
                        elif col == price_objective:  # Si c'est un index simple
                            matching_column = col
                            break
                    
                    if matching_column is not None:
                        # Filtrer les solutions qui respectent la contrainte budgétaire
                        filtered_solutions = df_for_reduction[df_for_reduction[matching_column] <= budget_limit]
                        n_filtered = len(filtered_solutions)
                        
                        if n_filtered == 0:
                            st.error("⚠️ Aucune solution ne respecte la contrainte budgétaire. Veuillez augmenter la borne.")
                            return
                        elif n_filtered < n_solutions:
                            st.warning(f"⚠️ Seulement {n_filtered} solution(s) respectent la contrainte budgétaire (< {n_solutions} demandées)")
                            n_solutions = min(n_solutions, n_filtered)
                        
                        # Appliquer l'algorithme glouton sur les solutions filtrées
                        reduced_solutions = greedy_reduction(filtered_solutions, reduction_weights, n_solutions)
                        st.session_state.budget_limit = budget_limit
                    else:
                        st.error(f"⚠️ Objectif de coût '{price_objective}' non trouvé dans les solutions")
                        return
                else:
                    # Pas de contrainte budgétaire, appliquer sur toutes les solutions
                    reduced_solutions = greedy_reduction(df_for_reduction, reduction_weights, n_solutions)
                    if 'budget_limit' in st.session_state:
                        del st.session_state.budget_limit
            
            # Stockage dans session_state
            st.session_state.reduced_solutions = reduced_solutions
            st.session_state.reduction_weights = reduction_weights
            
            success_msg = f"{len(reduced_solutions)} solutions optimales sélectionnées"
            if budget_limit is not None:
                success_msg += f" avec contrainte budgétaire ≤ {budget_limit:.4f}"
            st.success(success_msg + " !")
            
        except Exception as e:
            st.error(f"Erreur lors de la réduction : {str(e)}")
    
    # Affichage des résultats de réduction
    display_reduction_results(front_pareto, problem)

def display_reduction_results(front_pareto, problem):
    """Affiche les résultats de la réduction gloutonne"""
    if 'reduced_solutions' not in st.session_state:
        return
    
    st.markdown("#### 🏆 Solutions Optimales Sélectionnées")
    
    # Affichage des solutions réduites
    reduced_display = st.session_state.reduced_solutions.copy()
    display_names = [f"Solution {i+1}" for i in range(len(reduced_display))]
    reduced_display.index = display_names
    
    # Affichage de la contrainte budgétaire si elle existe
    if 'budget_limit' in st.session_state:
        st.info(f"🎯 **Contrainte budgétaire appliquée :** {st.session_state.budget_limit:.4f}")
    
    st.markdown("**Solutions avec score de qualité :**")
    st.dataframe(reduced_display.round(4).T, use_container_width=True)
    
    # Calcul et affichage des scores PEF
    display_pef_scores_for_solutions(front_pareto, problem, st.session_state.reduced_solutions)
    
    # Bouton de réinitialisation
    if st.button("Réinitialiser la réduction", key="reset_reduction_btn"):
        for key in ['reduced_solutions', 'reduction_weights', 'budget_limit']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def display_pef_scores_for_solutions(front_pareto, problem, reduced_solutions):
    """Calcule et affiche les scores PEF pour les solutions sélectionnées"""
    st.markdown("#### 📊 Scores PEF des Solutions Sélectionnées")
    
    try:
        all_scores = {}
        
        for idx, (solution_idx, _) in enumerate(reduced_solutions.iterrows()):
            try:
                if solution_idx in front_pareto._solution_points.columns:
                    solution_vars = front_pareto._solution_points.loc[:, solution_idx]
                    scores = problem.calculate_solution_scores(solution_vars)
                    
                    if 'PEF' in scores:
                        solution_name = f"Sol. {idx+1}"
                        all_scores[solution_name] = scores['PEF']
                else:
                    st.warning(f"⚠️ Solution {solution_idx} non trouvée")
                    continue
            except Exception as e:
                st.warning(f"⚠️ Erreur pour la solution {idx+1}: {str(e)}")
                continue
        
        if all_scores:
            df_pef_scores = pd.DataFrame(all_scores)
            
            st.markdown("**Tableau des Scores PEF (20 indicateurs) :**")
            st.dataframe(df_pef_scores.round(EPSILON_PRECISION), use_container_width=True)
        else:
            st.warning("⚠️ Aucun score PEF calculé")
            
    except Exception as e:
        st.error(f"Erreur lors du calcul des scores PEF : {str(e)}")

def display_single_solution_results(df_vars, df_obj, df_epsilon, problem, all_objectives, epsilon_objectives, optimization_weights):
    """Affiche les résultats d'une solution unique"""
    st.markdown("### 📊 Résultats de la Solution")
    
    # 1. Objectifs optimisés
    st.markdown("#### Valeurs des objectifs optimisés")
    st.dataframe(df_obj, use_container_width=True)
    
    # 2. Contraintes epsilon
    if df_epsilon is not None and len(df_epsilon) > 0:
        st.markdown("#### Valeurs des contraintes epsilon")
        st.dataframe(df_epsilon, use_container_width=True)
    
    # 3. Objectifs non considérés
    considered_objectives = set(optimization_weights.keys()) | set(epsilon_objectives)
    other_objectives = list(set(all_objectives) - considered_objectives)
    
    if other_objectives:
        st.markdown("#### 📈 Valeurs des objectifs non considérés")
        other_values = {}
        
        for obj in other_objectives:
            total_value = sum([
                problem._objectifsValues.loc[rm, obj] * df_vars.loc[rm, "Taux d'incorporation"] 
                for rm in problem._objectifsValues.index
            ])
            other_values[obj] = [total_value]
        
        df_other = pd.DataFrame(other_values).T
        df_other.columns = ["Valeurs objectives"]
        st.dataframe(df_other, use_container_width=True)
    
    # 4. Composition de l'aliment
    display_feed_composition(df_vars)
    
    # 5. Scores PEF
    display_pef_scores_single_solution(df_vars, problem)

def display_feed_composition(df_vars):
    """Affiche la composition de l'aliment formulé"""
    st.markdown("#### 🍽️ Composition de l'aliment formulé")
    
    # Composition détaillée
    st.markdown("**Composition détaillée par matière première :**")
    df_detailed = df_vars.copy()
    df_detailed['Taux d\'incorporation (%)'] = df_detailed['Taux d\'incorporation'] * 100
    df_detailed = df_detailed.drop('Taux d\'incorporation', axis=1).round(4)
    st.dataframe(df_detailed, use_container_width=True)
    
    # Composition par catégorie
    st.markdown("**Composition agrégée par catégorie :**")
    df_by_category = df_vars.groupby(level="Catégorie").sum()
    df_category_display = df_by_category.copy()
    df_category_display['Taux d\'incorporation (%)'] = df_category_display['Taux d\'incorporation'] * 100
    df_category_display = df_category_display.drop('Taux d\'incorporation', axis=1).round(4)
    
    st.dataframe(df_category_display, use_container_width=True)
    st.bar_chart(df_by_category['Taux d\'incorporation'])

def display_pef_scores_single_solution(df_vars, problem):
    """Affiche les scores PEF pour une solution unique"""
    st.markdown("#### 📊 Scores PEF de la Solution")
    
    try:
        solution_weights = df_vars['Taux d\'incorporation'].copy()
        scores = problem.calculate_solution_scores(solution_weights)
        
        if 'PEF' in scores:
            st.markdown("**Scores PEF (20 indicateurs environnementaux) :**")
            pef_df = scores['PEF'].to_frame('Score PEF')
            st.dataframe(pef_df.round(EPSILON_PRECISION), use_container_width=True)
        else:
            st.warning("Scores PEF non disponibles")
            
    except Exception as e:
        st.warning(f"Impossible de calculer les scores PEF : {str(e)}")

# ===== INTERFACES PRINCIPALES =====

def display_pareto_front_interface(problem):
    """Interface du front de Pareto"""
    st.markdown("### 📈 Front de Pareto")
    st.info("Méthode : **pondération multi-objectif avec contraintes** + **normalisation Crolard**")
    
    # Configuration des paramètres
    col1, col2 = st.columns(2)
    
    with col1:
        granularity = st.number_input(
            "Granularité de l'échantillonnage :",
            min_value=MIN_GRANULARITY,
            max_value=MAX_GRANULARITY,
            value=DEFAULT_GRANULARITY,
            help="Nombre de points à générer pour le front de Pareto"
        )
    
    with col2:
        st.markdown("**Pondération des objectifs :**")
    
    # Configuration des poids
    objectives = problem._objectifsValues.columns.tolist()
    weights = create_weight_configuration(objectives, key_prefix="pareto")
    
    # Génération du front de Pareto
    if st.button("🚀 Générer le Front de Pareto", type="primary"):
        try:
            with st.spinner("Génération du front de Pareto en cours..."):
                start_time = time.time()
                
                # Normalisation et génération
                normalized_data = normalisationCrolard(problem)
                results = ponderation_multiObj_limit(problem, normalized_data, granularity, weights)
                
                elapsed_time = time.time() - start_time
                
                # Création et stockage du front de Pareto
                front_pareto = FrontPareto(results, normalized_data, elapsed_time, weights)
                st.session_state.pareto_front = front_pareto
                st.session_state.pareto_problem = problem
                
            pareto_points = front_pareto._paretofront.loc[:, front_pareto._paretofront.loc[("", "Pareto")] == True]
            st.success(f"Front de Pareto généré avec {len(pareto_points.T)} solutions !")
            
            # Affichage des résultats
            display_pareto_results(front_pareto)
            
        except Exception as e:
            st.error(f"Erreur lors de la génération : {str(e)}")
    
    # Interface de réduction gloutonne
    if 'pareto_front' in st.session_state and st.session_state.pareto_front is not None:
        display_greedy_reduction_interface(st.session_state.pareto_front, problem)

def display_single_solution_interface(problem):
    """Interface de solution unique"""
    st.markdown("### 🎯 Solution Unique")
    st.info("Méthode : **Aliment sur demande** avec contraintes epsilon personnalisées")
    
    all_objectives = problem._objectifsValues.columns.tolist()
    
    # Configuration des contraintes epsilon
    st.markdown("#### Configuration des contraintes epsilon")
    use_epsilon = st.selectbox("Souhaitez-vous des contraintes epsilon ?", ["Non", "Oui"])
    
    epsilon_objectives = []
    df_epsilon_edited = None
    epsilon_valid = True
    
    if use_epsilon == "Oui":
        epsilon_objectives, df_epsilon_edited, ideal_points, epsilon_valid = create_epsilon_editor(
            all_objectives, problem
        )
    
    # Configuration des objectifs à optimiser
    st.markdown("#### Objectifs à optimiser")
    optimization_objectives, optimization_weights, normalized_data = create_objective_selector(
        all_objectives, epsilon_objectives
    )
    
    # Génération de la solution
    if (st.button("🎯 Générer la Solution", type="primary") and 
        optimization_weights and epsilon_valid):
        
        try:
            with st.spinner("Génération de la solution en cours..."):
                # Génération
                df_vars, df_obj, df_epsilon = aliment_by_demande(
                    df_epsilon_edited,
                    optimization_objectives,
                    optimization_weights,
                    problem,
                    normalized_data or problem
                )
                
                # Adaptation de l'index si nécessaire
                if (hasattr(df_vars.index, 'names') and 
                    df_vars.index.names != ["Catégorie", "MPCode"]):
                    df_vars.index = pd.MultiIndex.from_tuples(
                        df_vars.index, names=["Catégorie", "MPCode"]
                    )
            
            st.success("Solution générée avec succès !")
            
            # Affichage des résultats
            display_single_solution_results(
                df_vars, df_obj, df_epsilon, problem, 
                all_objectives, epsilon_objectives, optimization_weights
            )
            
        except Exception as e:
            st.error(f"Erreur lors de la génération : {str(e)}")

def display_generation_form():
    """Interface principale de génération d'aliments"""
    st.title("⚡ Génération d'Aliments")
    
    # Vérification de l'instance active
    if not validate_problem_instance():
        st.error("Aucune instance de problème active. Veuillez d'abord créer une instance dans 'Paramètres d'entrée'.")
        return
    
    problem = st.session_state.instance_active
    
    # Choix du type de génération
    st.markdown("### Choisissez le type de génération")
    generation_type = st.radio(
        "Type d'optimisation :",
        ["📈 Front de Pareto", "🎯 Solution unique"],
        horizontal=True
    )
    
    # Interface selon le type sélectionné
    if generation_type == "📈 Front de Pareto":
        display_pareto_front_interface(problem)
    else:
        display_single_solution_interface(problem)

# ===== POINT D'ENTRÉE =====
if __name__ == "__main__":
    display_generation_form()
