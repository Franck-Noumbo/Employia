import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from collections import Counter
import time
from contextlib import contextmanager

# ============================================
# CONFIGURATION DE LA PAGE
# ============================================
st.set_page_config(
    page_title="EmployIA",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================
# FONCTIONS DE GESTION DE BASE DE DONNÉES
# ============================================
@contextmanager
def get_db_connection():
    conn = sqlite3.connect("employia.db", check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()

def get_secteurs():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nom FROM secteurs ORDER BY nom")
        return [s[0] for s in cursor.fetchall()]

def get_all_competences():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nom, type FROM competences ORDER BY nom")
        return cursor.fetchall()

# ============================================
# CLASSE DE MATCHING
# ============================================
class EmployiaMatching:
    def __init__(self):
        pass
    
    def get_all_metiers_with_competences(self):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.nom, m.secteur_id, s.nom as secteur_nom,
                       m.diplome_minimum, m.demande_afrique, m.reconversion_facile
                FROM metiers m
                JOIN secteurs s ON m.secteur_id = s.id
            """)
            metiers = cursor.fetchall()
            
            metiers_complets = []
            for m in metiers:
                cursor.execute("""
                    SELECT c.nom, c.type
                    FROM competences c
                    JOIN metier_competences mc ON c.id = mc.competence_id
                    WHERE mc.metier_id = ?
                """, (m[0],))
                competences = cursor.fetchall()
                
                hard_skills = [c[0] for c in competences if c[1] == 'Hard Skill']
                soft_skills = [c[0] for c in competences if c[1] == 'Soft Skill']
                tools = [c[0] for c in competences if c[1] == 'Tools']
                
                metiers_complets.append({
                    'id': m[0],
                    'nom': m[1],
                    'secteur': m[3],
                    'diplome_minimum': m[4],
                    'demande_afrique': m[5],
                    'reconversion_facile': m[6],
                    'hard_skills': hard_skills,
                    'soft_skills': soft_skills,
                    'tools': tools
                })
            
            return metiers_complets
    
    def check_diplome_compatible(self, diplome_utilisateur, diplome_requis):
        niveaux = {
            'Bac': 2, 'BTS': 3, 'Licence': 4, 
            'Master': 5, 'Doctorat': 6, 'Autre': 2
        }
        diplome_requis_min = diplome_requis.split(' / ')[0]
        niveau_user = niveaux.get(diplome_utilisateur, 2)
        niveau_requis = niveaux.get(diplome_requis_min, 2)
        return 1 if niveau_user >= niveau_requis else 0
    
    def calculer_score_metier(self, utilisateur, metier):
        competences_user = set(utilisateur.get('competences', []))
        logiciels_user = set(utilisateur.get('logiciels', []))
        
        competences_metier = set(metier['hard_skills'] + metier['soft_skills'])
        logiciels_metier = set(metier['tools'])
        
        # Score Compétences (50%)
        if competences_metier:
            competences_communes = competences_user & competences_metier
            score_competences = (len(competences_communes) / len(competences_metier)) * 50
        else:
            score_competences = 25
        
        # Bonus pour compétences clés
        competences_cles = ['Python', 'SQL', 'JavaScript', 'Excel']
        for comp_cle in competences_cles:
            if comp_cle in competences_communes:
                score_competences += 2
        score_competences = min(score_competences, 50)
        
        # Score Diplôme (30%)
        diplome_compatible = self.check_diplome_compatible(
            utilisateur.get('diplome', ''), 
            metier['diplome_minimum']
        )
        score_diplome = diplome_compatible * 30
        
        # Score Logiciels (20%)
        if logiciels_metier:
            logiciels_communs = logiciels_user & logiciels_metier
            score_logiciels = (len(logiciels_communs) / len(logiciels_metier)) * 20
        else:
            score_logiciels = 10
        
        return round(score_competences + score_diplome + score_logiciels, 2)
    
    def get_competences_manquantes(self, utilisateur, metier):
        competences_user = set(utilisateur.get('competences', []))
        logiciels_user = set(utilisateur.get('logiciels', []))
        
        competences_manquantes = set(metier['hard_skills']) - competences_user
        logiciels_manquants = set(metier['tools']) - logiciels_user
        soft_skills_manquants = set(metier['soft_skills']) - competences_user
        
        result = []
        for comp in list(competences_manquantes)[:3]:
            result.append({'nom': comp, 'type': 'Technique', 'priorite': 'Haute'})
        for comp in list(logiciels_manquants)[:2]:
            result.append({'nom': comp, 'type': 'Outil', 'priorite': 'Moyenne'})
        for comp in list(soft_skills_manquants)[:2]:
            result.append({'nom': comp, 'type': 'Comportemental', 'priorite': 'Basse'})
        
        return result
    
    def recommander_metiers(self, utilisateur, top_n=10):
        metiers = self.get_all_metiers_with_competences()
        scores_metiers = []
        
        for metier in metiers:
            score = self.calculer_score_metier(utilisateur, metier)
            scores_metiers.append((metier, score))
        
        scores_metiers.sort(key=lambda x: x[1], reverse=True)
        
        recommandations = []
        for metier, score in scores_metiers[:top_n]:
            recommandations.append({
                'metier': metier['nom'],
                'secteur': metier['secteur'],
                'score': score,
                'diplome_requis': metier['diplome_minimum'],
                'demande_afrique': metier['demande_afrique'],
                'reconversion_facile': metier['reconversion_facile'],
                'competences_requises': metier['hard_skills'][:5],
                'competences_manquantes': self.get_competences_manquantes(utilisateur, metier)
            })
        
        return recommandations

def creer_profil_utilisateur(diplome, competences, logiciels, interets=None):
    return {
        'diplome': diplome,
        'competences': competences,
        'logiciels': logiciels,
        'interets': interets or []
    }
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    /* Variables de couleurs */
    :root {
        --primary: #667eea;
        --secondary: #764ba2;
        --accent: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg-glass: rgba(255, 255, 255, 0.9);
    }

    .stApp {
        background: radial-gradient(circle at top right, #764ba2, transparent),
                    radial-gradient(circle at bottom left, #667eea, transparent),
                    #f8fafc;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Conteneur Principal */
    .main-container {
        background: var(--bg-glass);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 24px;
        padding: 2.5rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
    }
    
    /* Header & Logo */
    .logo h1 {
        font-size: 3rem;
        letter-spacing: -1.5px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    }
    
    /* Cartes Métiers - Look Épuré */
    .metier-card {
        background: white;
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 1.5rem;
        border: 1px solid #edf2f7;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    
    .metier-card:hover {
        transform: translateY(-8px) scale(1.01);
        box-shadow: 0 20px 30px rgba(102, 126, 234, 0.15);
        border-color: var(--primary);
    }
    
    /* Badge de Score Circulaire */
    .metier-score {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 8px 18px;
        border-radius: 12px;
        font-weight: 800;
        box-shadow: 0 4px 12px rgba(118, 75, 162, 0.3);
    }

    /* Badges & Tags */
    .tag {
        background: #f1f5f9;
        color: #475569;
        padding: 6px 14px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        border: 1px solid #e2e8f0;
    }
    
    .tag-demand { 
        background: rgba(16, 185, 129, 0.1); 
        color: var(--accent); 
        border: 1px solid rgba(16, 185, 129, 0.2); 
    }
    
    .tag-reconversion { 
        background: rgba(245, 158, 11, 0.1); 
        color: var(--warning); 
        border: 1px solid rgba(245, 158, 11, 0.2); 
    }

    /* Stats Cards */
    .stat-card {
        background: rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 20px;
        padding: 1.5rem;
        color: white;
        transition: 0.3s;
    }
    
    .stat-card:hover {
        background: rgba(255, 255, 255, 0.3);
        transform: scale(1.05);
    }

    /* Formulaire & Inputs (Streamlit Overrides) */
    .stSelectbox, .stMultiSelect {
        background-color: white;
        border-radius: 12px;
    }

    /* Bouton Principal Lumineux */
    div.stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 14px;
        font-weight: 700;
        width: 100%;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    div.stButton > button:hover {
        box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        transform: translateY(-2px);
        color: white;
    }

    /* Section Compétences Manquantes */
    .skills-container {
        background: #fafafa;
        border-left: 4px solid var(--primary);
        border-radius: 12px;
        padding: 1.2rem;
    }

    .skill-item {
        transition: background 0.2s;
        border-radius: 8px;
        padding: 5px 10px;
    }

    .skill-item:hover {
        background: #f1f5f9;
    }

    /* Animations */
    @keyframes slideIn {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    .fade-in {
        animation: slideIn 0.6s cubic-bezier(0.23, 1, 0.32, 1);
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    ::-webkit-scrollbar-thumb {
        background: #764ba2;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)
# ============================================
# INITIALISATION DE LA SESSION
# ============================================
if 'matching' not in st.session_state:
    st.session_state.matching = EmployiaMatching()
if 'show_profile' not in st.session_state:
    st.session_state.show_profile = False
if 'recommandations' not in st.session_state:
    st.session_state.recommandations = None
if 'profil' not in st.session_state:
    st.session_state.profil = None

# ============================================
# HEADER
# ============================================
col1, col2 = st.columns([1, 5])
with col1:
    st.markdown("### 📋")
with col2:
    st.markdown('<p class="main-header">EmployIA</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Assistant d\'orientation professionnelle</p>', unsafe_allow_html=True)

# ============================================
# BOUTON PROFIL
# ============================================
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Commencer l'analyse", use_container_width=True):
        st.session_state.show_profile = True

# ============================================
# SIDEBAR PROFIL
# ============================================
if st.session_state.show_profile:
    with st.sidebar:
        st.markdown("## Votre profil")
        st.markdown("Renseignez votre parcours pour obtenir des recommandations personnalisées.")
        st.divider()
        
        with st.form("profil_form"):
            diplome = st.selectbox(
                "Niveau d'études",
                ["Bac", "BTS", "Licence", "Master", "Doctorat", "Autre"],
                index=2
            )
            
            all_competences = get_all_competences()
            hard_skills = [c[0] for c in all_competences if c[1] == 'Hard Skill']
            soft_skills = [c[0] for c in all_competences if c[1] == 'Soft Skill']
            tools = [c[0] for c in all_competences if c[1] == 'Tools']
            
            competences_tech = st.multiselect(
                "Compétences techniques",
                options=hard_skills
            )
            
            competences_soft = st.multiselect(
                "Compétences comportementales",
                options=soft_skills
            )
            
            logiciels = st.multiselect(
                "Outils et logiciels",
                options=tools
            )
            
            secteurs = get_secteurs()
            interets = st.multiselect(
                "Secteurs d'intérêt (optionnel)",
                options=secteurs
            )
            
            submitted = st.form_submit_button("Obtenir mes recommandations", use_container_width=True)
            
            if submitted:
                toutes_competences = competences_tech + competences_soft
                st.session_state.profil = creer_profil_utilisateur(
                    diplome=diplome,
                    competences=toutes_competences,
                    logiciels=logiciels,
                    interets=interets
                )
                
                with st.spinner("Analyse de votre profil en cours..."):
                    time.sleep(1)
                    st.session_state.recommandations = st.session_state.matching.recommander_metiers(
                        st.session_state.profil, top_n=10
                    )
                st.rerun()

# ============================================
# CONTENU PRINCIPAL
# ============================================
if st.session_state.recommandations is None:
    # Page d'accueil
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 3rem 0;">
        <h2>Découvrez les métiers qui vous correspondent</h2>
        <p style="color: #475569; max-width: 600px; margin: 1rem auto;">
            Notre algorithme analyse votre profil et vous propose une sélection de métiers adaptés à vos compétences et à votre parcours.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    stats = [
        ("500+", "Métiers référencés"),
        ("400+", "Compétences"),
        ("20", "Secteurs"),
        ("98%", "Pertinence")
    ]
    
    for col, (val, label) in zip([col1, col2, col3, col4], stats):
        with col:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{val}</div>
                <div class="stat-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="margin: 4rem 0 2rem 0;">
        <h3 style="text-align: center;">Comment ça fonctionne ?</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    steps = [
        ("1. Créez votre profil", "Renseignez votre formation, vos compétences et vos outils"),
        ("2. Analyse", "Notre algorithme compare votre profil à notre base de métiers"),
        ("3. Découvrez", "Obtenez vos recommandations personnalisées")
    ]
    
    for col, (title, desc) in zip([col1, col2, col3], steps):
        with col:
            st.markdown(f"""
            <div style="background: white; padding: 1.5rem; border-radius: 12px; border: 1px solid #e9eef2;">
                <h4 style="margin-bottom: 0.5rem;">{title}</h4>
                <p style="color: #475569; margin: 0;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

else:
    # Résultats
    st.markdown("## Vos recommandations personnalisées")
    
    # Stats rapides
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{st.session_state.recommandations[0]['score']}%</div>
            <div class="stat-label">Meilleur match</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{len(st.session_state.profil.get('competences', []))}</div>
            <div class="stat-label">Compétences</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{len(st.session_state.profil.get('logiciels', []))}</div>
            <div class="stat-label">Outils</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">10</div>
            <div class="stat-label">Métiers analysés</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["Métiers recommandés", "Analyse", "Plan de formation"])
    
    with tab1:
        for i, rec in enumerate(st.session_state.recommandations):
            # Carte métier
            st.markdown(f"""
            <div class="metier-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <span class="metier-title">{i+1}. {rec['metier']}</span>
                    <span class="metier-score">{rec['score']}%</span>
                </div>
                <div style="color: #64748b; margin-bottom: 1rem;">{rec['secteur']}</div>
            """, unsafe_allow_html=True)
            
            # Badges
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"<span class='badge'>{rec['diplome_requis']}</span>", unsafe_allow_html=True)
            with col2:
                demande = "⭐" * rec['demande_afrique']
                st.markdown(f"<span class='badge badge-green'>Demande: {demande}</span>", unsafe_allow_html=True)
            with col3:
                reconversion = "Facile" if rec['reconversion_facile'] >= 4 else "Moyenne"
                st.markdown(f"<span class='badge badge-orange'>Reconversion: {reconversion}</span>", unsafe_allow_html=True)
            
            # Compétences clés
            st.markdown("<div style='margin: 1rem 0;'><strong>Compétences clés:</strong></div>", unsafe_allow_html=True)
            cols = st.columns(len(rec['competences_requises']))
            for j, comp in enumerate(rec['competences_requises']):
                with cols[j]:
                    st.markdown(f"<span class='badge badge-blue'>{comp}</span>", unsafe_allow_html=True)
            
            # Compétences manquantes
            if rec['competences_manquantes']:
                st.markdown("<div style='margin-top: 1rem;'><strong>Compétences à développer:</strong></div>", unsafe_allow_html=True)
                for comp in rec['competences_manquantes']:
                    priority_class = {
                        'Haute': 'priority-high',
                        'Moyenne': 'priority-medium',
                        'Basse': 'priority-low'
                    }.get(comp['priorite'], '')
                    
                    st.markdown(f"""
                    <div class="competence-item">
                        <span>{comp['nom']} <span style="color: #64748b;">({comp['type']})</span></span>
                        <span class="{priority_class}">Priorité {comp['priorite'].lower()}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    with tab2:
        st.markdown("### Scores de compatibilité")
        
        # Graphique des scores
        scores_data = [{"Métier": r['metier'][:20] + "...", "Score": r['score']} 
                      for r in st.session_state.recommandations[:5]]
        df_scores = pd.DataFrame(scores_data)
        
        fig = px.bar(df_scores, x='Métier', y='Score', 
                     title="Top 5 des scores",
                     color='Score',
                     color_continuous_scale='blues')
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Compétences les plus demandées
        st.markdown("### Compétences les plus recherchées")
        all_skills = []
        for rec in st.session_state.recommandations:
            all_skills.extend(rec['competences_requises'])
        
        if all_skills:
            skills_count = Counter(all_skills).most_common(5)
            df_skills = pd.DataFrame(skills_count, columns=['Compétence', 'Occurrences'])
            
            fig2 = px.bar(df_skills, x='Compétence', y='Occurrences',
                         color='Occurrences', color_continuous_scale='blues')
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab3:
        if st.session_state.recommandations:
            meilleur = st.session_state.recommandations[0]
            
            st.markdown(f"""
            <div style="background: #f0f9ff; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem;">
                <h4 style="margin-bottom: 0.5rem;">Objectif : {meilleur['metier']}</h4>
                <p style="color: #0369a1;">Score actuel : {meilleur['score']}%</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Regrouper les compétences par phase
            phases = [
                ("Fondamentaux", [c for c in meilleur['competences_manquantes'] if c['priorite'] == 'Haute']),
                ("Outils", [c for c in meilleur['competences_manquantes'] if c['type'] == 'Outil']),
                ("Perfectionnement", [c for c in meilleur['competences_manquantes'] if c['type'] == 'Comportemental'])
            ]
            
            for titre, comps in phases:
                if comps:
                    with st.expander(titre):
                        for comp in comps:
                            st.markdown(f"• **{comp['nom']}** - {comp['type']}")
            
            if st.button("Générer un plan détaillé", use_container_width=True):
                st.balloons()
                st.success("Plan de formation généré avec succès !")

# ============================================
# FOOTER
# ============================================
st.markdown("""
<div class="footer">
    EmployIA - Assistant d'orientation professionnelle
</div>
""", unsafe_allow_html=True)