# ProjetEcoAlim-
Calculateur multicritère pour la formulation porcine : pondération, ε‑contrainte, normalisation, métriques avancées (DCI, Riesz). Analyse des compromis économiques et environnementaux via fronts de Pareto.
# 🥗 ECOALIM - Optimisation de l'Alimentation Porcine

**Outil d'aide à la décision pour une formulation d'aliments conciliant performance économique et durabilité environnementale.**

Ce projet a été développé par **Cyprien Quettier** dans le cadre du Master **Recherche Opérationnelle et Aide à la Décision (ROAD)** de l'Université de Bordeaux, en collaboration avec l'**IFIP-Institut du porc**.

---

## 🚀 Accès direct à l'application
L'outil est hébergé sur Streamlit Cloud et accessible ici :
👉 **[https://ecoalim.streamlit.app/](https://ecoalim.streamlit.app/)**

---

## 🧐 Problématique
La formulation classique d'aliments pour bétail se base presque exclusivement sur le **moindre coût**. Le projet **ECOALIM** propose d'intégrer des objectifs environnementaux (issus de l'Analyse de Cycle de Vie - ACV) pour trouver un équilibre entre rentabilité et écologie.

### Fonctionnalités de l'outil :
* **Sélection de la phase d'élevage** : *Growing* (Croissance) ou *Finishing* (Finition).
* **Optimisation Multicritère** : Choix entre la méthode de la **Somme Pondérée** (pour explorer les compromis) et la méthode **$\epsilon$-contrainte** (pour fixer des limites strictes sur un impact).
* **Visualisation des Fronts de Pareto** : Graphiques interactifs permettant de visualiser la perte économique nécessaire pour gagner en performance environnementale.
* **Solveur Puissant** : Utilisation de `highspy` (solveur HiGHS) pour garantir des solutions optimales exactes.

## 🛠️ Installation et Utilisation Locale
Si vous souhaitez exécuter ce projet sur votre machine :

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/Inderferr/ProjetEcoAlim-.git
   cd ECOALIM-main
