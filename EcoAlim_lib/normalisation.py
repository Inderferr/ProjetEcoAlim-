from EcoAlim_lib.ProblemFormalisation import ProblemFormalisation

def normalisationCrolard(data: ProblemFormalisation) -> ProblemFormalisation:
    """
    Normalise les données selon la méthode de Crolard.
    
    Cette méthode normalise chaque objectif par sa valeur maximale pour obtenir
    des valeurs comprises entre 0 et 1.
    
    Paramètres :
    - data (ProblemFormalisation) : Instance contenant les données à normaliser.
    
    Retourne :
    - ProblemFormalisation : Instance avec les objectifs normalisés.
    """
    # Copie des données originales
    data_norm = ProblemFormalisation(
        incorporationConstraints=data._incorporationConstraints.copy(),
        nutritionalConstraints=data._nutritionalConstraints.copy(),
        objectifsValues=data._objectifsValues.copy(),
        nutritionalValues=data._nutritionalValues.copy(),
        price_index=data._price_index,
        phase=data._phase
    )
    
    # Normalisation des objectifs par leur maximum
    for obj in data._objectifsValues.columns:
        max_val = data._objectifsValues[obj].max()
        if max_val != 0:  # Éviter la division par zéro
            data_norm._objectifsValues[obj] = data._objectifsValues[obj] / max_val
        else:
            # Si max = 0, on garde la valeur originale
            data_norm._objectifsValues[obj] = data._objectifsValues[obj]
    
    return data_norm