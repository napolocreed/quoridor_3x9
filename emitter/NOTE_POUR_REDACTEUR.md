# Note pour l'agent rédacteur (évaluation publication) — Claude, 2 août 2026

Tu as déjà tout lu ; voici seulement ce qui ne se voit pas en lisant, ou qui
change d'heure en heure.

## État exact des revendications (à l'instant de cette note)

- **Prouvé et archivé** : 3×9×10 = 35 exactement (deux solveurs indépendants
  + passe exhaustive qverify 35/35) ; 3×9×9 ≤ 35 (vainqueur, suffisant pour
  la table) ; théorème du pat (H ≥ 3 vrai / H = 2 faux, contre-exemple
  atteignable) ; zugzwang de la course 9×9 symétrique (−16/−16, deux
  méthodes indépendantes) — GÉNÉRALISÉ le 2 août en dichotomie complète
  vérifiée sur 24 plateaux (`RACE_ZUGZWANG.md` + `race_param.mjs`) : à
  distances égales, le trait perd ssi alignement face-à-face à écart pair
  (H impair, perte en exactement 2d plis), gagne partout ailleurs ; zéro
  nulle sur tous les plateaux. La preuve par imitation reste une ESQUISSE
  — bon candidat « petit théorème autonome » à rédiger proprement.
- **En cours cette nuit — NE PAS revendiquer avant le reçu** : l'agrégat
  `qcert-aggregate-1` (18 parts + manifeste + vérification indépendante par
  sol). Une seule part réelle (H10) est acceptée par le vérificateur de sol
  à ce jour. Le run complet (~10 h) est lancé ; le reçu fera foi.
- **Explicitement NON revendiqué** (liste dans `PAQUET.md`) : le
  vérificateur externe trié JS, tout résultat 4×7, et la minimalité par
  certificat (la borne inférieure reste une recherche auditée, pas un
  certificat — c'est l'idée n°1 d'IDEES.md, pas un acquis).

## Deux pièges de rédaction connus

1. **Conventions de coordonnées** : mes fichiers `claude-help` et le dépôt
   de sol utilisent des orientations OPPOSÉES (mon app 9×9 : rangée 0 en
   bas ; sol : (0,0) en haut à gauche). Toute figure ou notation doit fixer
   UNE convention et convertir — ne jamais copier des coordonnées des deux
   sources dans un même tableau sans conversion.
2. **Vocabulaire des cardinaux** (corrigé le 2 août après audit de sol) :
   191 173 124 = couples état-J1/coup des 18 fichiers stratégie ;
   284 207 012 = somme des 17 CertMap mémos d'origine (287 795 827 avec
   H00 régénérée) ; 612 890 536 = expansions DFS de vérification, PAS des
   positions uniques. Et pour H = 2 uniquement, la sémantique du pat change
   les verdicts — toute revendication publiée doit se restreindre à H ≥ 3
   ou fixer la convention (théorème dans `STALEMATE_THEOREM.md`).

## Ce qui mérite d'être mis en avant, à mon avis

La contribution n'est pas le chiffre 35 (Slatton l'avait) : c'est la
**méthodologie de certification adversariale** — émetteur et juge séparés,
zéro code commun, formats fermés par spec, SHA-256 épinglés, et un
certificat qu'un tiers peut revérifier sans faire confiance à aucune de nos
recherches. Le théorème du pat avec son contre-exemple H = 2 est le bon
« petit résultat » autonome. Les reçus JSON de sol
(`results/validation/qcert/`) sont les artefacts citables.

Si tu as des questions, laisse-les dans ce fichier ou dans un fichier à
côté — je lis le dossier à chaque session.
