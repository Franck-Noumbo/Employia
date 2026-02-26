import sqlite3

class EmployiaMatching:
    def __init__(self, db_path="employia.db"):
        """Initialise la connexion à la base de données"""
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
    def get_all_metiers_with_competences(self):
        """Récupère tous les métiers avec leurs compétences associées"""
        self.cursor.execute("""
            SELECT m.id, m.nom, m.secteur_id, s.nom as secteur_nom,
                   m.diplome_minimum, m.niveau_math, m.niveau_info,
                   m.demande_afrique, m.reconversion_facile
            FROM metiers m
            JOIN secteurs s ON m.secteur_id = s.id
        """)
        metiers = self.cursor.fetchall()
        
        metiers_complets = []
        for m in metiers:
            self.cursor.execute("""
                SELECT c.id, c.nom, c.type
                FROM competences c
                JOIN metier_competences mc ON c.id = mc.competence_id
                WHERE mc.metier_id = ?
            """, (m[0],))
            competences = self.cursor.fetchall()
            
            hard_skills = [c[1] for c in competences if c[2] == 'Hard Skill']
            soft_skills = [c[1] for c in competences if c[2] == 'Soft Skill']
            tools = [c[1] for c in competences if c[2] == 'Tools']
            
            metiers_complets.append({
                'id': m[0],
                'nom': m[1],
                'secteur_id': m[2],
                'secteur': m[3],
                'diplome_minimum': m[4],
                'niveau_math': m[5],
                'niveau_info': m[6],
                'demande_afrique': m[7],
                'reconversion_facile': m[8],
                'hard_skills': hard_skills,
                'soft_skills': soft_skills,
                'tools': tools,
                'toutes_competences': hard_skills + soft_skills + tools
            })
        
        return metiers_complets
    
    def check_diplome_compatible(self, diplome_utilisateur, diplome_requis):
        """Vérifie si le diplôme de l'utilisateur est compatible avec le diplôme requis"""
        niveaux = {
            'CAP': 1,
            'BEP': 1,
            'Bac': 2,
            'BTS': 3,
            'Licence': 4,
            'Master': 5,
            'Doctorat': 6
        }
        
        diplome_requis_min = diplome_requis.split(' / ')[0]
        
        niveau_user = niveaux.get(diplome_utilisateur, 0)
        niveau_requis = niveaux.get(diplome_requis_min, 0)
        
        return 1 if niveau_user >= niveau_requis else 0
    
    def calculer_score_metier(self, utilisateur, metier):
        """
        Calcule le score d'adéquation pour un métier
        Score = (compétences × 50%) + (diplôme × 30%) + (logiciels × 20%)
        """
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
        competences_cles = ['Python', 'SQL', 'JavaScript', 'Gestion de Projet', 'Excel']
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
        
        score_total = score_competences + score_diplome + score_logiciels
        
        return round(score_total, 2)
    
    def recommander_metiers(self, utilisateur, top_n=5):
        """Recommande les meilleurs métiers pour un utilisateur"""
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
    
    def get_competences_manquantes(self, utilisateur, metier):
        """Identifie les compétences manquantes pour un métier"""
        competences_user = set(utilisateur.get('competences', []))
        logiciels_user = set(utilisateur.get('logiciels', []))
        
        competences_requises = set(metier['hard_skills'])
        logiciels_requis = set(metier['tools'])
        soft_skills_requis = set(metier['soft_skills'])
        
        competences_manquantes = competences_requises - competences_user
        logiciels_manquants = logiciels_requis - logiciels_user
        soft_skills_manquants = soft_skills_requis - set(utilisateur.get('competences', []))
        
        competences_priorisees = []
        
        for comp in competences_manquantes:
            competences_priorisees.append({
                'nom': comp,
                'type': 'Hard Skill',
                'priorite': 'Haute'
            })
        
        for logiciel in logiciels_manquants:
            competences_priorisees.append({
                'nom': logiciel,
                'type': 'Outil',
                'priorite': 'Moyenne'
            })
        
        for soft in soft_skills_manquants:
            competences_priorisees.append({
                'nom': soft,
                'type': 'Soft Skill',
                'priorite': 'Basse'
            })
        
        return competences_priorisees
    
    def filtrer_par_secteur(self, utilisateur, secteur_nom):
        """Filtre les recommandations par secteur d'intérêt"""
        metiers = self.get_all_metiers_with_competences()
        metiers_secteur = [m for m in metiers if m['secteur'].lower() == secteur_nom.lower()]
        
        scores = []
        for metier in metiers_secteur:
            score = self.calculer_score_metier(utilisateur, metier)
            scores.append((metier, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [{
            'metier': m['nom'],
            'secteur': m['secteur'],
            'score': s,
            'competences_manquantes': self.get_competences_manquantes(utilisateur, m)[:3]
        } for m, s in scores[:5]]
    
    def analyser_profil_complet(self, utilisateur):
        """Analyse complète du profil utilisateur"""
        recommandations = self.recommander_metiers(utilisateur, top_n=5)
        
        competences_user = set(utilisateur.get('competences', []))
        logiciels_user = set(utilisateur.get('logiciels', []))
        
        competences_recherchees = []
        for rec in recommandations:
            metier = next(m for m in self.get_all_metiers_with_competences() 
                         if m['nom'] == rec['metier'])
            competences_recherchees.extend(metier['hard_skills'])
        
        from collections import Counter
        competences_tendances = Counter(competences_recherchees).most_common(5)
        
        return {
            'profil': {
                'diplome': utilisateur.get('diplome', 'Non spécifié'),
                'nombre_competences': len(competences_user),
                'nombre_logiciels': len(logiciels_user),
                'secteurs_interet': utilisateur.get('interets', [])
            },
            'top_recommandations': recommandations,
            'competences_tendances': [comp for comp, count in competences_tendances],
            'conseils': self.generer_conseils(utilisateur, recommandations)
        }
    
    def generer_conseils(self, utilisateur, recommandations):
        """Génère des conseils personnalisés pour l'utilisateur"""
        conseils = []
        
        if recommandations:
            meilleur_metier = recommandations[0]
            competences_manquantes = meilleur_metier['competences_manquantes']
            
            hard_skills_manquantes = [c for c in competences_manquantes if c['type'] == 'Hard Skill']
            if hard_skills_manquantes:
                conseils.append({
                    'type': 'formation',
                    'message': f"Pour devenir {meilleur_metier['metier']}, apprenez : {', '.join([c['nom'] for c in hard_skills_manquantes[:3]])}"
                })
            
            if meilleur_metier['score'] < 30 and meilleur_metier['diplome_requis']:
                conseils.append({
                    'type': 'diplome',
                    'message': f"Envisagez une formation pour atteindre le niveau {meilleur_metier['diplome_requis']}"
                })
            
            if meilleur_metier['demande_afrique'] >= 4:
                conseils.append({
                    'type': 'opportunite',
                    'message': f"Le métier de {meilleur_metier['metier']} est très demandé en Afrique !"
                })
        
        return conseils
    
    def fermer_connexion(self):
        """Ferme la connexion à la base de données"""
        self.conn.close()


def creer_profil_utilisateur(diplome, competences, logiciels, interets=None):
    """Crée un profil utilisateur structuré"""
    if interets is None:
        interets = []
    
    return {
        'diplome': diplome,
        'competences': competences,
        'logiciels': logiciels,
        'interets': interets
    }