import streamlit as st
import pandas as pd
from EcoAlim_lib.tools import display_data
from EcoAlim_lib.ProblemFormalisation import ProblemFormalisation

# ===== CONSTANTES =====
DEFAULT_CATEGORIES = ['Co_prod_ble', 'Co_prod_mais', 'Graine Prot.', 'Corps gras', 'Autre', 'Cereales', 'Tourteaux']
PHASE_PLACEHOLDER = "Choisir une phase"
PRICE_PLACEHOLDER = "Choisir un contexte de prix"

# ===== FONCTIONS UTILITAIRES =====

def extract_phases_from_columns(columns):
    """Extrait les noms de phases à partir des colonnes Min/Max"""
    return [col.replace("Min", "").strip() for col in columns if "Min" in col]

def create_multiindex_if_needed(category, mp_code, reference_index):
    """Crée un index approprié selon la structure de référence"""
    if isinstance(reference_index, pd.MultiIndex):
        return pd.MultiIndex.from_tuples([(category, mp_code)], names=reference_index.names)
    else:
        return pd.Index([mp_code], name=reference_index.name or 'MPCode')

def filter_dataframe_by_mps(df, selected_mps):
    """Filtre un DataFrame par les MPs sélectionnées"""
    if isinstance(df.index, pd.MultiIndex) and "MPCode" in df.index.names:
        return df[df.index.get_level_values("MPCode").isin(selected_mps)]
    else:
        return df[df.index.isin(selected_mps)]

# ===== COMPOSANTS D'INTERFACE =====

def create_raw_material_selector(mp_codes):
    """Crée l'interface de sélection des matières premières"""
    st.write("Sélectionnez les matières premières à inclure dans le modèle :")
    selected_mps = []
    cols = st.columns(5)
    
    for i, mp_code in enumerate(mp_codes):
        with cols[i % 5]:
            if st.checkbox(label=mp_code, value=True, key=mp_code):
                selected_mps.append(mp_code)
    
    return selected_mps

def create_phase_uploader(label, file_type="xlsx"):
    """Crée un uploader de fichier avec extraction des phases"""
    uploaded_file = st.file_uploader(label, type=[file_type])
    selected_phase = PHASE_PLACEHOLDER
    phase_df = None
    
    if uploaded_file is not None:
        phase_df = pd.read_excel(uploaded_file, index_col=0)
        phases = extract_phases_from_columns(phase_df.columns.tolist())
        selected_phase = st.selectbox(f"Sélectionnez la phase {label.lower()} :", 
                                    [PHASE_PLACEHOLDER] + phases)
    
    return uploaded_file, phase_df, selected_phase

# ===== TRAITEMENT DES DONNÉES =====

def filter_data_by_selection(data, selected_mps, selected_price):
    """Filtre les données selon la sélection de MPs et le contexte de prix"""
    objectives_env = data["df_obj_env"]
    objectives_price = data["df_obj_price"]
    nutritional_values = data["df_nutritionnal"]
    scores_pef = data["df_PEF"]
    
    # Filtrage par MPs sélectionnées
    filtered_env = filter_dataframe_by_mps(objectives_env, selected_mps)
    filtered_price = filter_dataframe_by_mps(objectives_price, selected_mps)
    filtered_nutritional = filter_dataframe_by_mps(nutritional_values, selected_mps)
    filtered_pef = filter_dataframe_by_mps(scores_pef, selected_mps)
    
    # Combinaison objectifs environnementaux + prix
    combined_objectives = pd.concat([filtered_env, filtered_price[[selected_price]]], axis=1).astype(float)
    
    return {
        'objectives': combined_objectives,
        'nutritional': filtered_nutritional,
        'pef_scores': filtered_pef,
        'env_filtered': filtered_env,
        'price_filtered': filtered_price
    }

def create_phase_constraints(phase_df, phase_name, selected_mps):
    """Crée les contraintes pour une phase donnée"""
    min_col = f"{phase_name} Min"
    max_col = f"{phase_name} Max"
    phase_columns = [min_col, max_col]
    
    # Gestion index simple vs MultiIndex
    filtered_constraints = filter_dataframe_by_mps(phase_df, selected_mps)[phase_columns]
    
    # Renommage standard
    filtered_constraints.columns = ["Min", "Max"]
    return filtered_constraints

# ===== VALIDATION DES DONNÉES =====

def validate_nutrition_file(nutrition_file, nutrition_df):
    """Valide le fichier de contraintes nutritionnelles"""
    errors = []
    
    if nutrition_file is not None:
        st.write("📊 Vérification du fichier de contraintes nutritionnelles...")
        
        # Vérifier l'index
        if nutrition_df.index.name != 'NutCode':
            errors.append("⚠️ Fichier nutrition : L'index doit être 'NutCode'")
        
        # Vérifier les colonnes Min/Max avec phases
        columns = nutrition_df.columns.tolist()
        detected_phases = set()
        
        for col in columns:
            if " Min" in col:
                phase_name = col.replace(" Min", "").strip()
                detected_phases.add(phase_name)
                max_col = f"{phase_name} Max"
                if max_col not in columns:
                    errors.append(f"⚠️ Fichier nutrition : Colonne '{max_col}' manquante pour la phase '{phase_name}'")
            elif " Max" in col:
                phase_name = col.replace(" Max", "").strip()
                detected_phases.add(phase_name)
                min_col = f"{phase_name} Min"
                if min_col not in columns:
                    errors.append(f"⚠️ Fichier nutrition : Colonne '{min_col}' manquante pour la phase '{phase_name}'")
        
        if not detected_phases:
            errors.append("⚠️ Fichier nutrition : Aucune phase détectée (format attendu: 'Phase Min', 'Phase Max')")
        else:
            st.info(f"✅ Phases détectées dans le fichier nutrition : {list(detected_phases)}")
    
    return errors

def validate_incorporation_file(incorporation_file, incorporation_df):
    """Valide le fichier de contraintes d'incorporation"""
    errors = []
    
    if incorporation_file is not None:
        st.write("📊 Vérification du fichier de contraintes d'incorporation...")
        
        # Vérifier l'index
        if isinstance(incorporation_df.index, pd.MultiIndex):
            errors.append("⚠️ Fichier incorporation : L'index doit être simple (MPCode), pas un MultiIndex")
        elif incorporation_df.index.name != 'MPCode':
            errors.append("⚠️ Fichier incorporation : L'index doit être 'MPCode'")
        
        # Vérifier les colonnes Min/Max avec phases
        columns = incorporation_df.columns.tolist()
        detected_phases = set()
        
        for col in columns:
            if " Min" in col:
                phase_name = col.replace(" Min", "").strip()
                detected_phases.add(phase_name)
                max_col = f"{phase_name} Max"
                if max_col not in columns:
                    errors.append(f"⚠️ Fichier incorporation : Colonne '{max_col}' manquante pour la phase '{phase_name}'")
            elif " Max" in col:
                phase_name = col.replace(" Max", "").strip()
                detected_phases.add(phase_name)
                min_col = f"{phase_name} Min"
                if min_col not in columns:
                    errors.append(f"⚠️ Fichier incorporation : Colonne '{min_col}' manquante pour la phase '{phase_name}'")
        
        if not detected_phases:
            errors.append("⚠️ Fichier incorporation : Aucune phase détectée (format attendu: 'Phase Min', 'Phase Max')")
        else:
            st.info(f"✅ Phases détectées dans le fichier incorporation : {list(detected_phases)}")
    
    return errors

def validate_data_consistency(filtered_data, incorporation_constraints):
    """Valide la cohérence des données filtrées"""
    errors = []
    
    # Données à vérifier (MultiIndex)
    multiindex_data = {
        "Objectifs environnementaux": filtered_data['env_filtered'],
        "Objectifs de prix": filtered_data['price_filtered'], 
        "Valeurs nutritionnelles": filtered_data['nutritional'],
        "Scores PEF": filtered_data['pef_scores']
    }
    
    # Vérifier les MultiIndex
    for name, df in multiindex_data.items():
        if not isinstance(df.index, pd.MultiIndex):
            errors.append(f"⚠️ {name} n'a pas un MultiIndex")
        elif df.index.names != ['Categorie', 'MPCode']:
            errors.append(f"⚠️ {name} - Noms des niveaux d'index incorrects: {df.index.names}")
    
    # Vérifier la cohérence des index
    reference_index = filtered_data['env_filtered'].index
    for name, df in multiindex_data.items():
        if name != "Objectifs environnementaux" and not df.index.equals(reference_index):
            errors.append(f"⚠️ {name} n'a pas le même index que les objectifs environnementaux")
    
    # Vérifier incorporation_constraints (index simple)
    if isinstance(incorporation_constraints.index, pd.MultiIndex):
        errors.append("⚠️ Phase & Incorporation : L'index ne devrait pas être un MultiIndex")
    elif incorporation_constraints.index.name != 'MPCode':
        errors.append(f"⚠️ Phase & Incorporation : L'index devrait être 'MPCode'")
    else:
        # Vérifier cohérence des MPCodes
        if isinstance(reference_index, pd.MultiIndex) and "MPCode" in reference_index.names:
            mp_ref = set(reference_index.get_level_values("MPCode"))
            mp_inc = set(incorporation_constraints.index)
            if mp_ref != mp_inc:
                missing = mp_ref - mp_inc
                extra = mp_inc - mp_ref
                if missing:
                    errors.append(f"⚠️ Phase & Incorporation : MP manquantes: {missing}")
                if extra:
                    errors.append(f"⚠️ Phase & Incorporation : MP en trop: {extra}")
    
    # Vérifier les valeurs manquantes
    if filtered_data['objectives'].isnull().values.any():
        errors.append("⚠️ Des valeurs manquantes dans les objectifs.")
    if incorporation_constraints.isnull().values.any():
        errors.append("⚠️ Des valeurs manquantes dans les contraintes d'incorporation.")
    
    return errors

# ===== INTERFACE PRINCIPALE =====

def display_manual_mp_addition(data, selected_price, nutrition_phase, incorporation_phase):
    """Interface complète d'ajout manuel de matières premières"""
    with st.expander("➕ Ajouter une nouvelle MP manuellement"):
        if 'mps_ajoutees' not in st.session_state:
            st.session_state.mps_ajoutees = []
        
        st.markdown("### 🆕 Nouvelle matière première")
        
        # Informations de base
        col1, col2 = st.columns(2)
        
        with col1:
            mp_category = st.selectbox(
                "Catégorie :",
                DEFAULT_CATEGORIES,
                key="new_mp_category"
            )
        
        with col2:
            mp_code = st.text_input(
                "Code MP (unique) :",
                placeholder="Ex: NOUVEAU_MP",
                key="new_mp_code"
            ).upper().strip()
        
        if mp_code:
            # Vérifier l'unicité du code
            existing_codes = data["df_obj_env"].index.get_level_values("MPCode").tolist()
            added_codes = [mp['code'] for mp in st.session_state.mps_ajoutees]
            
            if mp_code in existing_codes or mp_code in added_codes:
                st.error(f"❌ Le code '{mp_code}' existe déjà. Choisissez un code unique.")
                return
            
            # Interface de saisie des données
            st.markdown("### 📊 Saisie des données")
            
            # Onglets pour organiser la saisie
            data_tabs = st.tabs([
                "🌱 Objectifs environnementaux", 
                "💰 Prix", 
                "🧪 Valeurs nutritionnelles",
                "🌍 Scores PEF",
                "📏 Contraintes d'incorporation"
            ])
            
            # === OBJECTIFS ENVIRONNEMENTAUX ===
            with data_tabs[0]:
                st.markdown("#### Objectifs environnementaux")
                from EcoAlim_lib.constants import OBJECTIFS_ENV
                
                obj_env_values = {}
                env_columns = data["df_obj_env"].columns.tolist()
                
                cols = st.columns(2)
                for i, col_name in enumerate(env_columns):
                    with cols[i % 2]:
                        obj_env_values[col_name] = st.number_input(
                            f"{col_name}",
                            value=0.0,
                            step=0.001,
                            format="%.6f",
                            key=f"env_{col_name}"
                        )
            
            # === PRIX ===
            with data_tabs[1]:
                st.markdown(f"#### Prix ({selected_price})")
                price_value = st.number_input(
                    f"Valeur pour {selected_price}",
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="new_mp_price"
                )
            
            # === VALEURS NUTRITIONNELLES ===
            with data_tabs[2]:
                st.markdown("#### Valeurs nutritionnelles")
                from EcoAlim_lib.constants import NUTRITIONALELEMENTS
                
                nutritional_values = {}
                
                # Grouper par catégories pour l'affichage
                nutritional_groups = {
                    "Composition générale": ['MS', 'CB', 'NDF', 'ADF', 'ADL', 'MG', 'Amidon', 'Sucres', 'MAT', 'MM'],
                    "Acides aminés totaux": ['Lys', 'Met', 'Cys', 'Trp', 'Thr', 'Phe', 'Tyr', 'Leu', 'Ile', 'Val', 'His'],
                    "Acides aminés digestibles": ['Lys dig.', 'Met dig.', 'Cys dig.', 'METCYSD', 'Thr dig.', 'Trp dig.', 'Ile dig.', 'Val dig.', 'Leu dig.', 'Phe dig.', 'Tyr dig.', 'His dig.'],
                    "Minéraux": ['Ca', 'P', 'P dig. (granules)', 'P dig. (farine)', 'Na', 'K', 'Cl'],
                    "Énergie": ['EN C', 'ED C'],
                    "Totaux spécifiques": ['TOTISSUES', 'TOTTOUR', 'TOTCOPDT', 'TOTHUILE']
                }
                
                for group_name, elements in nutritional_groups.items():
                    with st.expander(f"📋 {group_name}"):
                        cols = st.columns(3)
                        for i, element in enumerate(elements):
                            if element in NUTRITIONALELEMENTS:
                                with cols[i % 3]:
                                    nutritional_values[element] = st.number_input(
                                        element,
                                        value=0.0,
                                        step=0.01,
                                        format="%.3f",
                                        key=f"nut_{element}"
                                    )
            
            # === SCORES PEF ===
            with data_tabs[3]:
                st.markdown("#### Scores PEF")
                from EcoAlim_lib.constants import SCORE_PREF
                
                pef_values = {}
                pef_columns = data["df_PEF"].columns.tolist()
                
                # Interface simplifiée avec expandeurs
                st.info("💡 Vous pouvez laisser à 0 pour les indicateurs non renseignés")
                
                with st.expander("📊 Saisir tous les scores PEF"):
                    cols = st.columns(2)
                    for i, col_name in enumerate(pef_columns):
                        with cols[i % 2]:
                            pef_values[col_name] = st.number_input(
                                f"{col_name}",
                                value=0.0,
                                step=0.001,
                                format="%.6f",
                                key=f"pef_{i}_{col_name}"
                            )
            
            # === CONTRAINTES D'INCORPORATION ===
            with data_tabs[4]:
                st.markdown(f"#### Contraintes d'incorporation ({incorporation_phase})")
                
                col1, col2 = st.columns(2)
                with col1:
                    incorp_min = st.number_input(
                        "Minimum (%)",
                        value=0.0,
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        key="incorp_min"
                    )
                
                with col2:
                    incorp_max = st.number_input(
                        "Maximum (%)",
                        value=100.0,
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        key="incorp_max"
                    )
                
                if incorp_min > incorp_max:
                    st.error("⚠️ Le minimum ne peut pas être supérieur au maximum")
            
            # === BOUTON D'AJOUT ===
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col2:
                if st.button("✅ Ajouter cette matière première", type="primary", use_container_width=True):
                    if incorp_min <= incorp_max:
                        # Créer les DataFrames pour la nouvelle MP
                        mp_index = pd.MultiIndex.from_tuples([(mp_category, mp_code)], names=['Categorie', 'MPCode'])
                        mp_index_simple = pd.Index([mp_code], name='MPCode')
                        
                        # Objectifs environnementaux + prix
                        obj_data = {**obj_env_values, selected_price: price_value}
                        mp_objectives = pd.DataFrame([obj_data], index=mp_index)
                        
                        # Valeurs nutritionnelles
                        mp_nutritional = pd.DataFrame([nutritional_values], index=mp_index)
                        
                        # Scores PEF
                        mp_pef = pd.DataFrame([pef_values], index=mp_index)
                        
                        # Contraintes d'incorporation
                        mp_incorporation = pd.DataFrame(
                            [[incorp_min, incorp_max]], 
                            index=mp_index_simple,
                            columns=["Min", "Max"]
                        )
                        
                        # Ajouter à la session
                        new_mp_data = {
                            'code': mp_code,
                            'categorie': mp_category,
                            'objectifs': mp_objectives,
                            'nutritionnel': mp_nutritional,
                            'pef': mp_pef,
                            'incorporation': mp_incorporation
                        }
                        
                        st.session_state.mps_ajoutees.append(new_mp_data)
                        st.success(f"✅ Matière première '{mp_code}' ajoutée avec succès !")
                        
                        # Vider les champs pour le prochain ajout
                        for key in st.session_state.keys():
                            if key.startswith(('env_', 'nut_', 'pef_', 'new_mp_')):
                                del st.session_state[key]
                        
                        st.rerun()
                    else:
                        st.error("❌ Veuillez corriger les contraintes d'incorporation")
        
        # === AFFICHAGE DES MPs AJOUTÉES ===
        if st.session_state.mps_ajoutees:
            st.markdown("---")
            st.markdown("### 📋 Matières premières ajoutées")
            
            for i, mp_data in enumerate(st.session_state.mps_ajoutees):
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.write(f"**{mp_data['code']}** ({mp_data['categorie']})")
                    
                    with col2:
                        # Afficher quelques détails
                        incorp_min = mp_data['incorporation']['Min'].iloc[0]
                        incorp_max = mp_data['incorporation']['Max'].iloc[0]
                        st.write(f"Incorporation: {incorp_min:.1f}% - {incorp_max:.1f}%")
                    
                    with col3:
                        if st.button("🗑️", key=f"del_{i}", help=f"Supprimer {mp_data['code']}"):
                            st.session_state.mps_ajoutees.pop(i)
                            st.success(f"🗑️ {mp_data['code']} supprimée")
                            st.rerun()
                    
                    # Détails en expandeur
                    with st.expander(f"🔍 Détails de {mp_data['code']}"):
                        detail_tabs = st.tabs(["Objectifs", "Nutrition", "PEF", "Incorporation"])
                        
                        with detail_tabs[0]:
                            st.dataframe(mp_data['objectifs'].round(6), use_container_width=True)
                        
                        with detail_tabs[1]:
                            st.dataframe(mp_data['nutritionnel'].round(3), use_container_width=True)
                        
                        with detail_tabs[2]:
                            st.dataframe(mp_data['pef'].round(6), use_container_width=True)
                        
                        with detail_tabs[3]:
                            st.dataframe(mp_data['incorporation'], use_container_width=True)

def display_data_validation(filtered_data, nutrition_df, nutrition_file, 
                           incorporation_df, incorporation_file, 
                           nutrition_constraints, incorporation_constraints):
    """Interface de validation des données"""
    if st.button("🧪 Vérifier les données"):
        errors = []
        
        # Validation des fichiers
        errors.extend(validate_nutrition_file(nutrition_file, nutrition_df))
        errors.extend(validate_incorporation_file(incorporation_file, incorporation_df))
        
        # Validation de la cohérence
        errors.extend(validate_data_consistency(filtered_data, incorporation_constraints))
        
        # Vérification des contraintes nutritionnelles
        if nutrition_constraints.isnull().values.any():
            errors.append("⚠️ Des valeurs manquantes dans les contraintes nutritionnelles.")
        
        # Affichage des résultats
        if errors:
            st.error("Problèmes détectés :")
            for error in errors:
                st.write(error)
        else:
            st.success("Toutes les données semblent valides.")

def create_problem_instance(filtered_data, nutrition_constraints, incorporation_constraints,
                          selected_price, nutrition_phase, incorporation_phase):
    """Crée l'instance de problème et l'affiche"""
    if st.button("Créer l'instance de problème", type="primary"):
        try:
            # Intégration automatique des MPs ajoutées si nécessaire
            local_objectives = filtered_data['objectives'].copy()
            local_nutritional = filtered_data['nutritional'].copy()
            local_pef = filtered_data['pef_scores'].copy()
            local_incorporation = incorporation_constraints.copy()
            
            if st.session_state.mps_ajoutees:
                st.info("Intégration des matières premières ajoutées...")
                for mp_data in st.session_state.mps_ajoutees:
                    local_incorporation = pd.concat([local_incorporation, mp_data['incorporation']], ignore_index=False)
                    local_objectives = pd.concat([local_objectives, mp_data['objectifs']], ignore_index=False)
                    local_nutritional = pd.concat([local_nutritional, mp_data['nutritionnel']], ignore_index=False)
                    local_pef = pd.concat([local_pef, mp_data['pef']], ignore_index=False)
                
                st.session_state.mps_ajoutees = []
            
            # Création de l'instance
            problem = ProblemFormalisation(
                incorporationConstraints=local_incorporation.astype(float),
                nutritionalConstraints=nutrition_constraints.astype(float),
                objectifsValues=local_objectives.astype(float),
                nutritionalValues=local_nutritional.astype(float),
                price_index=selected_price,
                phase=nutrition_phase,
                score_pef=local_pef.astype(float)
            )
            
            st.success("✅ Instance de problème créée avec succès !")
            st.info("📊 Vous pouvez maintenant l'utiliser dans la section 'Générer'")
            
            # Sauvegarde dans session_state
            st.session_state.instance_active = problem
            
            # Résumé
            with st.expander("📋 Résumé de l'instance créée"):
                st.write(f"**Phase nutrition :** {nutrition_phase}")
                st.write(f"**Phase d'incorporation :** {incorporation_phase}")
                st.write(f"**Contexte de prix :** {selected_price}")
                st.write(f"**Nombre de matières premières :** {len(local_objectives)}")
                mp_codes = local_objectives.index.get_level_values("MPCode").tolist()
                st.write(f"**Matières premières :** {', '.join(mp_codes)}")
            
            return problem
            
        except Exception as e:
            st.error(f"❌ Erreur lors de la création du problème : {str(e)}")
            return None

def process_data_configuration(data, selected_mps, selected_price, 
                             nutrition_df, nutrition_phase, nutrition_file,
                             incorporation_df, incorporation_phase, incorporation_file):
    """Traite la configuration des données et gère l'interface"""
    
    # Filtrage des données
    filtered_data = filter_data_by_selection(data, selected_mps, selected_price)
    
    # Création des contraintes
    nutrition_constraints = nutrition_df.loc[:, [f"{nutrition_phase} Min", f"{nutrition_phase} Max"]]
    nutrition_constraints.columns = ["Min", "Max"]
    
    incorporation_constraints = create_phase_constraints(incorporation_df, incorporation_phase, selected_mps)
    
    # Interface d'ajout de nouvelles MPs
    display_manual_mp_addition(data, selected_price, nutrition_phase, incorporation_phase)
    
    # Validation et création d'instance
    display_data_validation(filtered_data, nutrition_df, nutrition_file, 
                           incorporation_df, incorporation_file, 
                           nutrition_constraints, incorporation_constraints)
    
    return create_problem_instance(filtered_data, nutrition_constraints, incorporation_constraints,
                                 selected_price, nutrition_phase, incorporation_phase)

def display_input_form():
    """Interface principale de configuration des paramètres d'entrée"""
    st.title("Paramètres d'entrée")
    
    # === 📂 Téléchargement du fichier de données principal ===
    st.markdown("### 📂 Fichier de données des matières premières")
    
    uploaded_main_file = st.file_uploader(
        "Téléchargez votre fichier Excel contenant les données des matières premières",
        type=["xlsx"],
        help="Le fichier doit contenir une feuille 'MP' avec les données des matières premières, objectifs et scores PEF"
    )
    
    # Note explicative des contraintes du fichier
    with st.expander("📋 Format et contraintes du fichier Excel"):
        st.markdown("""
        ### 🔧 Structure requise du fichier Excel
        
        Votre fichier Excel doit respecter la structure suivante :
        
        #### 📄 **Feuille "MP" obligatoire**
        - Le fichier doit contenir une feuille nommée **"MP"**
        - L'index doit être un **MultiIndex** avec 2 niveaux : `[Categorie, MPCode]`
        
        #### 🏷️ **1. Catégories des matières premières**
        - Chaque matière première doit avoir une **catégorie** (niveau 1 de l'index)
        - Exemples : "Cereales", "Tourteaux", "Corps gras", etc.
        
        #### 🔤 **2. Codes des matières premières (MPCode)**
        - Chaque matière première doit avoir un **code unique** (niveau 2 de l'index)
        - Exemples : "BLE", "MAIS", "TOURNESOL", etc.
        
        #### 💰 **3. Colonnes de contextes de prix**
        - Les colonnes de prix doivent contenir le mot **"prix"** dans leur nom
        - Exemples : "Contexte prix standard", "prix bio", "prix local", etc.
        
        #### 🌱 **4. Indicateurs environnementaux PEF (20 attendus)**
        """)
        
        with st.expander("🔍 Voir la liste complète des 20 indicateurs PEF"):
            from EcoAlim_lib.constants import SCORE_PREF
            st.markdown("**Liste des indicateurs PEF requis :**")
            for i, indicator in enumerate(SCORE_PREF, 1):
                st.write(f"{i}. {indicator}")
            st.info("⚠️ Si certains indicateurs manquent, l'application fonctionnera mais avec moins d'indicateurs disponibles.")
        
        st.markdown("""
        #### 🧪 **5. Valeurs nutritionnelles**
        - Le fichier doit contenir les colonnes nutritionnelles suivantes :
        """)
        
        with st.expander("🔍 Voir la liste complète des éléments nutritionnels"):
            from EcoAlim_lib.constants import NUTRITIONALELEMENTS
            st.markdown("**Éléments nutritionnels requis :**")
            
            # Grouper les éléments par catégorie pour une meilleure lisibilité
            nutritional_groups = {
                "**Composition générale**": ['MS', 'CB', 'NDF', 'ADF', 'ADL', 'MG', 'Amidon', 'Sucres', 'MAT', 'MM'],
                "**Acides aminés totaux**": ['Lys', 'Met', 'Cys', 'Trp', 'Thr', 'Phe', 'Tyr', 'Leu', 'Ile', 'Val', 'His'],
                "**Acides aminés digestibles**": ['Lys dig.', 'Met dig.', 'Cys dig.', 'METCYSD', 'Thr dig.', 'Trp dig.', 'Ile dig.', 'Val dig.', 'Leu dig.', 'Phe dig.', 'Tyr dig.', 'His dig.'],
                "**Minéraux**": ['Ca', 'P', 'P dig. (granules)', 'P dig. (farine)', 'Na', 'K', 'Cl'],
                "**Énergie**": ['EN C', 'ED C'],
                "**Totaux spécifiques**": ['TOTISSUES', 'TOTTOUR', 'TOTCOPDT', 'TOTHUILE']
            }
            
            for group_name, elements in nutritional_groups.items():
                st.markdown(f"{group_name}")
                cols = st.columns(3)
                for i, element in enumerate(elements):
                    with cols[i % 3]:
                        st.write(f"• {element}")
        
        st.markdown("""
        #### 🎯 **6. Objectifs environnementaux**
        - Les colonnes d'objectifs environnementaux doivent contenir un des mots-clés suivants **+ " ECOALIM"**
        """)
        
        with st.expander("🔍 Voir les mots-clés des objectifs environnementaux"):
            from EcoAlim_lib.constants import OBJECTIFS_ENV
            st.markdown("**Mots-clés pour les objectifs environnementaux :**")
            for obj in OBJECTIFS_ENV:
                st.write(f"• **{obj}** ECOALIM")
            st.info("Exemple : 'Changement climatique ECOALIM', 'Conso P ECOALIM', etc.")
        
        st.markdown("""
        ---
        
        ### ✅ **Conseils supplémentaires**
        
        1. **Format de données** : Assurez-vous que toutes les valeurs numériques sont bien formatées (pas de texte dans les colonnes numériques)
        2. **Valeurs manquantes** : Évitez les cellules vides dans les données numériques (utilisez 0 si nécessaire)
        3. **Encodage** : Sauvegardez votre fichier en UTF-8 pour éviter les problèmes d'accents
        4. **Noms exacts** : Respectez exactement l'orthographe et les espaces dans les noms des indicateurs PEF
        5. **Structure cohérente** : Toutes les matières premières doivent avoir les mêmes colonnes renseignées
        
        ### 🚨 **Points d'attention**
        
        - **Indicateurs PEF manquants** : L'application fonctionnera mais avec moins d'indicateurs disponibles
        - **Index incorrect** : Si l'index n'est pas un MultiIndex [Categorie, MPCode], l'application peut ne pas fonctionner
        - **Colonnes prix absentes** : Au moins une colonne contenant "prix" est nécessaire
        """)
        
    
    # Utiliser le fichier par défaut si aucun fichier n'est téléchargé
    if uploaded_main_file is None:
        st.info("💡 Utilisation du fichier par défaut : `data/MP_validation_methode.xlsx`")
        data_file = "data/MP_validation_methode.xlsx"
        # Chargement des données
        try:
            data = display_data(data_file)
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement du fichier par défaut : {e}")
            return None
    else:
        st.success(f"✅ Fichier téléchargé : {uploaded_main_file.name}")
        # Sauvegarder temporairement le fichier téléchargé
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(uploaded_main_file.getvalue())
            data_file = tmp_file.name
            
        # Chargement des données du fichier téléchargé
        try:
            data = display_data(data_file)
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement du fichier téléchargé : {e}")
            return None
        finally:
            # Nettoyer le fichier temporaire
            if uploaded_main_file is not None:
                try:
                    os.unlink(data_file)
                except:
                    pass
    
    objectives_env = data["df_obj_env"]
    objectives_price = data["df_obj_price"] 
    mp_codes = objectives_env.index.get_level_values("MPCode").tolist()
    price_contexts = objectives_price.columns.tolist()
    
    # Interface à onglets
    tabs = st.tabs(["🍽️ Matières premières", "📉 Contexte de prix", 
                   "🎯 Phase & Nutrition", "📊 Phase & Incorporation"])

    # Onglet 1: Sélection des matières premières
    with tabs[0]:
        selected_mps = create_raw_material_selector(mp_codes)

    # Onglet 2: Contexte de prix
    with tabs[1]:
        selected_price = st.selectbox("Choisissez le contexte de prix :", 
                                    [PRICE_PLACEHOLDER] + price_contexts)

    # Onglet 3: Phase nutrition
    with tabs[2]:
        nutrition_file, nutrition_df, nutrition_phase = create_phase_uploader(
            "Télécharger les contraintes de nutrition")

    # Onglet 4: Phase incorporation  
    with tabs[3]:
        incorporation_file, incorporation_df, incorporation_phase = create_phase_uploader(
            "Télécharger les contraintes d'incorporation")

    # Traitement principal si tous les paramètres sont sélectionnés
    if all([selected_price != PRICE_PLACEHOLDER, 
            nutrition_phase != PHASE_PLACEHOLDER,
            incorporation_phase != PHASE_PLACEHOLDER]):
        
        return process_data_configuration(
            data, selected_mps, selected_price, 
            nutrition_df, nutrition_phase, nutrition_file,
            incorporation_df, incorporation_phase, incorporation_file
        )
    
    return None
