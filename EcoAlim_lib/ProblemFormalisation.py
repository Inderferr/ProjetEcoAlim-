import pandas as pd

class ProblemFormalisation : 
    # Classe pour formaliser le problème d'optimisation
    # Initialisation de la classe
    def __init__(self, incorporationConstraints : pd.DataFrame, 
                 nutritionalConstraints : pd.DataFrame, 
                 objectifsValues : pd.DataFrame,  
                 nutritionalValues : pd.DataFrame, 
                 price_index : str,
                 phase : str,
                 score_pef : pd.DataFrame = None,
                 score_unique : pd.Series = None
                 ):
        """
        Constructeur de la classe ProblemFormalisation.

        Paramètres :
        - incorporationConstraints : DataFrame contenant les contraintes d'incorporation (min et max).
        - nutritionalConstraints : DataFrame contenant les contraintes nutritionnelles (min et max).
        - objectifsValues : DataFrame contenant les valeurs des objectifs environnementaux et économiques.
        - nutritionalValues : DataFrame contenant les valeurs nutritionnelles des matières premières.
        - price_index : Indice de prix utilisé pour l'optimisation.
        - phase : Phase de production (exemple : "Growing").

        """
        
        self._incorporationConstraints = incorporationConstraints
        self._nutritionalConstraints = nutritionalConstraints
        self._objectifsValues = objectifsValues
        self._nutritionalValues = nutritionalValues
        self._price_index = price_index
        self._phase = phase
        self._score_pef = score_pef
        self._score_unique = score_unique
    
    def print(self):
        """
        Méthode pour afficher une description formelle du problème d'optimisation.

        Cette méthode imprime :
        - La phase et l'indice de prix utilisés.
        - Les objectifs à minimiser.
        - Les variables de décision (matières premières et catégories).
        - Les contraintes nutritionnelles et d'incorporation.
        """
        print(f"""
Pour la phase {self._phase} et le prix indexé sur {self._price_index}, notre problème est formalisé comme suit :
-> Objectif :
    Il existe {len(self._objectifsValues.columns)} coûts à minimiser : 
    - {"\n    - ".join(self._objectifsValues.columns.tolist())}

-> Variables de Décision
    Nous avons {len(self._nutritionalValues.index)} matières premières réparties dans {len(self._nutritionalValues.index.get_level_values('Categorie').drop_duplicates())} catégories :
    - {"\n    - ".join(self._nutritionalValues.index.get_level_values('Categorie').drop_duplicates().tolist())}

-> Contraintes :
    Notre modèle est contraint par : 
    - {len(self._nutritionalConstraints.index)} x 2 contraintes nutritionnelles (min & max)
    - {len(self._incorporationConstraints.index)} x 2 contraintes d'incorporation (min & max)
    - 1 contrainte sur la somme des taux d'incorporation des matières premières qui doit être égale à 1
        """)
    
    def calculate_solution_scores(self, solution_weights):
        """
        Calcule les scores PEF pour une solution donnée.
        
        Paramètres :
        - solution_weights : Series contenant les poids/taux d'incorporation de la solution
        
        Retourne :
        - dict contenant les scores calculés
        """
        try:
            # Vérifier que nous avons les données nécessaires
            if not hasattr(self, '_score_pef') or self._score_pef is None:
                raise ValueError("Données PEF non disponibles dans l'instance du problème")
            
            # S'assurer que les index correspondent
            if not solution_weights.index.equals(self._score_pef.index):
                # Essayer de réaligner les index
                common_index = solution_weights.index.intersection(self._score_pef.index)
                if len(common_index) == 0:
                    raise ValueError("Aucun index commun entre la solution et les données PEF")
                
                solution_weights = solution_weights.loc[common_index]
                score_pef_aligned = self._score_pef.loc[common_index]
            else:
                score_pef_aligned = self._score_pef
            
            # Calculer les scores PEF (produit matriciel)
            # solution_weights est un vecteur, score_pef_aligned est une matrice
            pef_scores = score_pef_aligned.T.dot(solution_weights)
            
            return {
                'PEF': pef_scores
            }
            
        except Exception as e:
            print(f"Erreur dans calculate_solution_scores: {e}")
            return {
                'PEF': None
            }
        
        