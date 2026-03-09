import streamlit as st
from streamlit_option_menu import option_menu
from param_updated import display_input_form
from generation import display_generation_form

# Initialiser le session state pour l'instance active
if 'instance_active' not in st.session_state:
    st.session_state.instance_active = None

with st.sidebar:
    choix = option_menu("Navigation", 
                        ["Accueil", 
                         "Paramètre d'entrée", 
                         "Générer"], 
                        icons=["house", "gear", "play"],
                        menu_icon="cast", 
                        default_index=0,
                        orientation="vertical"
)

if choix == "Accueil":
    st.title("🌱 EcoAlim – Optimisation de l'alimentation durable des porcs")
    st.markdown("""
    ## Bienvenue dans EcoAlim V3
    
    Cette application vous aide à formuler des aliments durables pour les porcs, en conciliant objectifs économiques et enjeux environnementaux, grâce à des techniques d'optimisation multiobjectif.
    
    ## 👣 Parcours utilisateur recommandé :
    
    ### 🛠️ Paramètres d'entrée
    
    - Sélectionnez vos matières premières.
    - Choisissez un contexte de prix.
    - Définissez les contraintes nutritionnelles et d'incorporation par phase (croissance, finition...).
    - Générez une instance de problème personnalisée.
    
    ### ⚙️ Génération
    
    Choisissez entre deux méthodes d'optimisation :
    - **Front de Pareto** (exploration de compromis)
    - **Solution unique** (résultat ciblé)
    
    ---
    
    ## ⚡ Deux méthodes complémentaires
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🔄 Front de Pareto
        
        **But :** Explorer un ensemble de solutions optimales où chaque solution représente un compromis différent entre les objectifs.
        
        **Méthode utilisée :** `ponderation_multiObj_limit`
        
        **Avantages :**
        - Permet de visualiser les compromis possibles (ex : entre coût et impact carbone).
        - L'utilisateur peut ensuite réduire ce front pour ne garder que quelques solutions clés.
        
        **Idéal pour :** Décideurs souhaitant analyser plusieurs scénarios avant de choisir.
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 Solution unique
        
        **But :** Obtenir une seule solution optimisée, selon des priorités définies par l'utilisateur (objectifs à minimiser, contraintes sur d'autres).
        
        **Méthode utilisée :** `aliment_by_demande` avec epsilon-contrainte
        
        **Avantages :**
        - Résultat rapide et directement exploitable.
        - Possibilité de fixer des seuils minimum/maximum sur certains critères.
        
        **Idéal pour :** Utilisateurs souhaitant une solution opérationnelle immédiate.
        """)
    
    st.markdown("""
    ---
    
    ## 💡 Pourquoi les deux ?
    
    → Le **Front de Pareto** permet d'explorer toute la diversité des solutions efficaces, tandis que la **Solution unique** vous donne une réponse concrète et rapide selon vos priorités.
    
    ---
    
    🚀 **Commencez dès maintenant par configurer vos paramètres d'entrée !**
    """)

elif choix == "Paramètre d'entrée":
    # Récupérer l'instance active ou créer une nouvelle
    problem = display_input_form()
    # Stocker l'instance active dans le session state
    if problem:
        st.session_state.instance_active = problem

elif choix == "Générer":
    # Utiliser la nouvelle interface de génération simplifiée
    display_generation_form()
